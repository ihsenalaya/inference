# Module 7 - Santé et efficacité du GPU : lire, alerter, agir

**En une phrase.** Un GPU se juge sur trois axes qu'il ne faut pas confondre : est-il **sain**, est-il **saturé**, est-il **efficace** ? Ce module résume les idées clés avec les chiffres de ce cluster ; le détail, les sources et les diagrammes sont dans le [dossier docs/gpu](../gpu/README.md).

<!-- mots: méthode use, gpu_util, sm_active, raisons de bridage, ecc, xid, roofline, mfu -->
> **Mots à connaître**
> - **Méthode USE** : Pour chaque ressource, on regarde l'Utilisation (est-elle occupée ?), la Saturation (y a-t-il de la file ?) et les Erreurs.
> - **GPU_UTIL** : Part du temps où *au moins un* calcul tournait. **100 % ne veut pas dire saturé** (observé : le même GPU passe de 284 à 933 tokens/s à `GPU_UTIL` constant ou plus bas).
> - **SM_ACTIVE / TENSOR / DRAM_ACTIVE** : Compteurs plus fins : unités de calcul actives / tensor cores actifs / mémoire du GPU active.
> - **Raisons de bridage (clock event reasons)** : Les causes qui font baisser l'horloge : repos, plafond de puissance, ralentissement thermique ou matériel... Un masque de bits (`DCGM_FI_DEV_CLOCK_THROTTLE_REASONS`) à décoder.
> - **ECC / SBE / DBE** : Code qui détecte et corrige les erreurs de la mémoire du GPU. SBE = erreur simple, corrigée ; DBE = erreur double, non corrigeable (grave).
> - **XID** : Code d'erreur NVIDIA signalant un problème GPU (ex. 79 : GPU tombé du bus).
> - **Roofline** : Graphique qui dit si un calcul est limité par la mémoire ou par le calcul, selon le nombre d'opérations faites par octet lu.
> - **MFU / MBU** : Part du calcul (MFU) ou de la bande passante mémoire (MBU) réellement utilisée par rapport au maximum du GPU. Le MBU est le bon indicateur du décodage.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## 1. Trois idées à garder

1. **« 100 % utilisé » ne veut pas dire « saturé ».** `GPU_UTIL` mesure un temps d'occupation. Observé : le 1,5B affiche 100 % à 2 req/s (environ 40 % de sa capacité) et produit **933 tokens/s au lieu de 284** quand on le sature, avec un `GPU_UTIL` plus bas (83 %).
2. **Le décodage est limité par la mémoire, le prefill et les gros batchs par le calcul.** Le roofline du T4 (65 TFLOPS, 320 Go/s) place le point de bascule à environ **203 opérations par octet**. Un décodage à une requête fait ≈ 2,7 opérations par octet : on attend la mémoire, et le 7B AWQ y atteint **≈ 83 % du toit** (21,5 ms par token). Avec 200 requêtes en parallèle on passe de l'autre côté : `DRAM_ACTIVE` tombe à 0,27 et `SM_ACTIVE` monte à 0,97.
3. **Un GPU sain peut être mal utilisé, et un GPU utilisé à fond peut être malade.** D'où deux tableaux de bord : **07 - Santé du GPU** et **08 - Efficacité et goulot du GPU**.

## 2. Ce que disent les compteurs, en trois situations (observé)

| Situation (7B AWQ) | `SM_ACTIVE` | `TENSOR` | `DRAM_ACTIVE` | Puissance | Horloge SM | Lecture |
|---|---|---|---|---|---|---|
| Chat à 1 req/s | 0,89 | 0,28 | 0,51 | 66 W | 1 012 MHz | décodage : la mémoire travaille |
| RAG à 0,1 req/s | 0,48 | 0,10 | 0,08 | 50 W | 1 006 MHz | prefill : la mémoire se repose, le calcul domine |
| Lot saturé à 2,5 req/s | 0,97 | 0,32 | 0,27 | 68 W | 1 110 MHz | GPU saturé : calcul à fond, cache KV à 100 % |

Aucune de ces situations n'atteint l'horloge maximale (1 590 MHz, relevé par `nvidia-smi -q`) alors que la puissance frôle 70 W : le T4 est **limité par sa puissance**. **Confirmé le 17/11/2026** : le masque de bridage vaut **4** (plafond de puissance, normal) pendant toutes les charges, jamais de ralentissement thermique ou matériel ; dès 0,5 req/s le GPU passe 75 % du temps au plafond, et à 1,5 req/s tout le temps, alors que la file est encore vide ([chapitre 07](../gpu/07-resultats-seance.md#5-escalier-de-charge)).

## 3. Santé : ce qui est surveillé

- **Marges** : température et puissance avant leur limite. **Bridage** : le masque de bits est décodé ; le plafond de puissance logiciel est **normal**, le ralentissement matériel ou thermique est **anormal**.
- **Erreurs** : ECC simple (corrigée) ou double (grave), pages retirées, codes XID, rejeux PCIe. Sur une VM, on ne répare pas : on **vide, redémarre ou remplace le nœud**. On a **vérifié** sur le cluster que l'outil `dcgmi` répond (état de santé « Healthy », diagnostics de niveau 1 et 2 réussis) et que l'alerte d'inactivité arrive jusqu'au récepteur ([chapitre 07](../gpu/07-resultats-seance.md)).
- AKS fournit des contrôles de santé GPU... **sauf** sur les pools sans pilote géré par AKS, comme le nôtre : on les a reconstruits avec Prometheus (6 alertes, 18 tests).

## 4. Efficacité : ce qui est mesuré

- **Tokens par joule** : 4,2 en chat et **15,6 en lot saturé** sur le 1,5B  ; de 1,0 (à 0,5 req/s) à **3,1 (à saturation)** sur le 7B AWQ : plus le GPU travaille, moins chaque token coûte en énergie (il consomme 31 W même à vide).
- Sur Azure, **le GPU se paie à l'heure, pas au joule** : ce qui fait baisser la facture, c'est de produire plus de tokens par heure (0,16 $ contre 0,52 $ par million de tokens sur le 1,5B).
- **MBU** (part de la bande passante utilisée) : le bon indicateur du décodage ; il demande `--enable-mfu-metrics` (scénario `gpu-health`). **Piège observé** : l'estimation de vLLM (≈ 0,10) est 7 fois plus basse que le calcul à partir du temps par token (≈ 0,7) et que `DRAM_ACTIVE ÷ 0,8` (0,77) : toujours recouper.
- **Régler la puissance** : sur ce T4, `nvidia-smi -pl 60` (limite de puissance) donne **+ 10 % de tokens par joule** pour − 6,5 % de débit, et verrouiller l'horloge à 900 MHz **+ 21 %** pour − 8 % de débit mais un premier token 3 fois plus lent au bord de la capacité ([chapitre 07, §6](../gpu/07-resultats-seance.md#6-limite-de-puissance-et-verrouillage-dhorloge)). C'est un choix de capacité, pas un gain gratuit.

## 5. À retenir

1. Pour juger la saturation : `SM_ACTIVE`, `DRAM_ACTIVE ÷ 0,8` et la **file**, jamais `GPU_UTIL` seul.
2. Le levier dépend du goulot : mémoire (quantization, batch, modèle plus petit), calcul (modèle plus petit, GPU en plus), mémoire de contexte (cache KV).
3. Santé et efficacité sont deux questions séparées, avec deux arbres de décision ([docs/gpu/04](../gpu/04-diagnostic-et-optimisation.md)).

## 6. Exercices (à faire vous-même)

1. Un GPU affiche `GPU_UTIL` 100 %, `SM_ACTIVE` 0,45, `DRAM_ACTIVE` 0,10 et une file vide. Est-il saturé ? Quel compteur vous trompe ?
2. Le masque de bridage vaut 68. Quels bits sont actifs, et faut-il s'inquiéter ?
3. Vous divisez la fréquence du GPU par deux. Prédisez le sens de variation du débit en décodage et de l'énergie par token, puis dites ce qu'il faudrait mesurer pour le vérifier.
Vérification : 1 = non saturé (file vide, `SM_ACTIVE` et `DRAM_ACTIVE` bas), c'est `GPU_UTIL` qui trompe ; 2 = 68 = 0x40 + 0x4 : ralentissement thermique matériel (grave) et plafond de puissance (normal) : inquiétant ; 3 = pas de réponse unique : la littérature montre des courbes en U avec un genou, et l'expérience S5 l'a retrouvé sur ce T4 (meilleur rendement à 900 MHz, moins bon à 750 MHz) : voir le [chapitre 07](../gpu/07-resultats-seance.md#6-limite-de-puissance-et-verrouillage-dhorloge).
