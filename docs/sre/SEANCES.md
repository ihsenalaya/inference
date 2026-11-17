# Compte rendu des séances SRE

Format imposé par le prompt : ce qui a été fait, ce qui a été appris, ce qui est adopté, heures GPU consommées, puis arrêt du cluster. Heures GPU = temps pendant lequel le nœud T4 a existé
(0,526 $/h, plus 0,182 $/h pour le nœud système).

## Séance 1 - Phase 0 : état des lieux, bruit de mesure, plan de campagne (17/11/2026) - TERMINÉE

**Fait**
- État des lieux et plan de campagne priorisé : [ETAT-DES-LIEUX.md](ETAT-DES-LIEUX.md) (la validation du plan par l'utilisateur est toujours attendue).
- Bruit de mesure du **7B AWQ** (3 répétitions à 1 req/s) **et du 1,5B FP16** (3 répétitions à 2 req/s, mesuré sur le second cluster).
- Instrumentation : CPU de vLLM, throttling, GPU alloué/utilisé, compteurs DCGM de profilage (`SM_ACTIVE`, `SM_OCCUPANCY`, `PIPE_TENSOR_ACTIVE`, `PIPE_FP16_ACTIVE`).
- Preuve des changements d'industrialisation par une réinstallation complète : GPU Operator en vague 1, pré-tirage de l'image, budget Azure.

**Appris**
- Bruit : débits CV <= 2,7 % (7B) et <= 0,7 % (1,5B) ; latences p95 CV 19-29 % (7B) et 2-7 % (1,5B) ([module 1](../formation/01-mesurer-sans-se-tromper.md)).
- **Correction d'une erreur de l'état des lieux** : les compteurs `SM_ACTIVE`, `SM_OCCUPANCY`, `PIPE_TENSOR_ACTIVE` **sont** exposés sur le T4 (cause probable de l'erreur initiale : exporteur resté sur l'ancienne liste de champs).
- Démarrage à froid : nœud GPU créé -> vLLM Ready en **721 s au lieu de 1 228 s** (-41 %), dont -487 s attribuables aux deux changements ([module 6](../formation/06-demarrage-a-froid.md)).
- Le CPU n'est pas le goulot : 0,16 à 0,36 coeur utilisé en moyenne par vLLM, y compris en saturation ([module 5](../formation/05-lire-un-gpu.md)).

**Adopté** : GPU Operator en vague 1 et pré-tirage d'image (prouvés), budget Azure de 40 $/mois (créé sans refus), règles de décision issues du bruit.

**Non fait / ouvert** : `lab.sh idle` et `lab.sh snapshot-metrics` restent non testés sur un cluster.

## Séance 2 - Phase 1 : classes de charge, SLI, SLO, burn rate (17/11/2026) - LIVRÉE, SLO À VALIDER

**Fait**
- 4 classes de charge, chacune avec un profil de bench et une clé virtuelle LiteLLM (classe Embeddings non couverte : aucun modèle déployé).
- SLI mesurés côté client (CSV par requête, goodput), passerelle (métriques LiteLLM par classe) et moteur (vLLM) : [module 2](../formation/02-classes-de-charge-et-sli.md).
- SLO proposés par classe : [SLO.md](SLO.md) ; budget d'erreur converti en minutes et en requêtes : [module 3](../formation/03-slo-et-budget-derreur.md).
- Alertes de burn rate multi-fenêtres (14,4x / 1 h confirmé 5 min ; 6x / 6 h confirmé 30 min), seuils recalculables selon la fenêtre, **10 tests `promtool`** dont 5 de burn rate ; anciennes alertes à seuil fixe sur la latence et le taux d'erreur **supprimées** ; dashboard « 06 - SLO par classe de charge » ; runbooks `LabSLOBurnFast` / `LabSLOBurnSlow`.
- Mesures par classe sur les **deux modèles** (8 runs de classe, dont le RAG nominal du 7B) et **essai réel d'alerte** : `LabSLOBurnSlow` déclenchée et reçue par le récepteur ([module 4](../formation/04-burn-rate-et-alertes.md)).

**Appris**
- Seule la classe interactive tient son SLO sur les deux modèles ; le RAG ne le tient sur aucun (91,3 % sur le 1,5B à 0,5 req/s, 88,3 % sur le 7B à 0,1 req/s) ; le lot s'effondre sur le 7B à 2,5 req/s (44 % de requêtes bonnes) alors que le 1,5B l'absorbe à 7 req/s.
- `GPU_UTIL` à 100 % n'est pas la saturation : le même GPU passe de 284 à 933 tokens/s avec un `GPU_UTIL` plus bas ([module 5](../formation/05-lire-un-gpu.md)).
- Un prefill long multiplie par dix le temps par token des autres requêtes (TPOT 0,020 s -> 0,20 s).
- Un SLI de disponibilité côté serveur ne voit pas les timeouts du client (282 timeouts du banc contre 3 erreurs 500 vues par LiteLLM sur le lot 7B).
- Les seaux des histogrammes LiteLLM n'ont pas de 3 s : un seuil de SLO doit être un seau ; un p95 d'histogramme n'est pas comparable à un p95 client (5,66 s mesuré contre 8,9 s annoncé).
- Le multi-tour simulé dépasse `max-model-len` à 2 req/s (76 % d'erreurs 400) : limite du générateur à connaître.

**Adopté** : clés par classe, seuils sur seaux, disponibilité = 5xx et 408, burn rates à la place des alertes à seuil fixe, multi-tour mesuré à 0,5 req/s ([D-30 à D-34](../DECISIONS.md)).

**Ouvert**
1. **Validation des SLO par l'utilisateur** (les valeurs sont des propositions).
2. **`LabSLOBurnFast` non déclenchée sur le cluster** (seulement validée par `promtool`) : le burn rate 1 h n'a pas dépassé 14,4.
3. **Un seul run par couple modèle/classe** : aucune dispersion, donc aucun gain déclaré ; le RAG 7B n'a que 60 requêtes.
4. Les 2 panneaux « budget consommé » de RAG et multi-tour sont vides quand la classe n'a pas eu de trafic récent (comportement normal, à ne pas confondre avec un bug).
5. Les SLI serveur par classe dépendent de la clé utilisée par le client.

**Bugs du banc trouvés et corrigés pendant la séance** (aucun n'était visible avant ce travail) : extraction des résultats sous WSL qui bloquait ~20 min ; profil `multi-turn` invalide pour inference-perf v0.7.0
(clé `max_model_len`) ; `lab.sh bench` qui attendait tout le délai quand le job avait échoué ; SLI de disponibilité vide quand aucune requête n'échoue.

**Heures GPU et coût (séances 1 et 2, second cluster)** : cluster actif de 08:38 à environ 12:30 (3 h 50 environ), dont ~3 h 45 de T4 ; coût estimé **≈ 2,7 $** (calcul : 3,8 h x 0,708 $/h). Estimation, pas une facture.
Cluster détruit en fin de séance ; les snapshots Azure n'ont pas été touchés.

## Séances suivantes (non commencées)

Séance 3 (goulot, lecture du GPU, CPU), 4 (attention, mémoire KV, concurrence, batching), 5 (quantization, taille, contexte, qualité), 6 (routage, passerelles), 7 (autoscaling, démarrage), 8 (opérations GPU), 9 (game days), 10 (capacité, coût, rapport final).
Chacune annonce son budget d'heures GPU avant de démarrer et attend la validation du plan ([ETAT-DES-LIEUX.md](ETAT-DES-LIEUX.md), section 5).
