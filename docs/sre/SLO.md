# SLO par classe de charge (séance 2)

**En une phrase.** Pour chaque type d'usage (chat, RAG, multi-tour, lot), on fixe une promesse chiffrée, on la mesure sur le cluster réel et on dit si elle est tenue.

<!-- mots: slo, sli, budget d'erreur, classe de charge, goodput, ttft, rag -->
> **Mots à connaître**
> - **SLO** : Un objectif chiffré de qualité de service, par exemple « 95 % des réponses commencent en moins de 5 s ».
> - **SLI** : L'indicateur mesuré (par exemple : part de requêtes avec un TTFT ≤ 5 s).
> - **Budget d'erreur** : La marge autorisée : 100 % − objectif. SLO à 95 % → 5 % de requêtes lentes tolérées.
> - **Classe de charge** : Un type d'usage avec son propre SLO : interactive, RAG, multi-tour, lot (embeddings non couverte).
> - **Goodput** : Débit des requêtes **réussies et assez rapides** (qui respectent le SLO), pas le débit brut.
> - **TTFT** : *Time To First Token* : attente avant le premier token de la réponse. C'est ce que l'utilisateur ressent en premier.
> - **RAG** : Question accompagnée de longs documents retrouvés par ailleurs : prompt très long, réponse courte.
> - Tous les mots : [glossaire](GLOSSAIRE.md).
<!-- /mots -->

Date : 17/11/2026. Cluster AKS `eastus`, 1 x T4. Formation associée : [modules 2, 3 et 4](../formation/README.md). Marques de fiabilité : [le guide](../guide/README.md).

> **Statut : valeurs de départ retenues.** Les objectifs ci-dessous sont déduits de la baseline et des mesures de la séance 2 ; ce ne sont pas des engagements de service. Ils sont écrits à un seul endroit
> (`slo.classes` dans `gitops/observability/config/values.yaml`), lus par les règles Prometheus et par `tests/goodput.py` : on les change en une ligne si les besoins évoluent.

## 1. Classes, SLI, SLO

Comment lire ce tableau : chaque ligne est un **type d'usage** (une classe) avec **sa** promesse. « 95 % <= 5 s » veut dire : au moins 95 requêtes sur 100 doivent obtenir leur premier token en moins de 5 secondes ; les 5 % restants sont le **budget d'erreur**.

| Classe | Profil de charge | Disponibilité | TTFT | Durée de bout en bout |
|---|---|---|---|---|
| Interactive | `interactive` (prompts 64-512, sorties 32-256, streaming) | 99 % | 95 % <= 5 s | 95 % <= 30 s |
| RAG | `long-prompt` (prompts 2 000-3 500, sorties 16-64) | 99 % | 95 % <= 10 s | 95 % <= 30 s |
| Multi-tour | `multi-turn` (16 conversations, système de 256 tokens) | 99 % | 95 % <= 5 s | 95 % <= 30 s |
| Lot | `batch` (prompts 256-1 024, sorties 128-384) | 99 % | -- | 95 % <= 300 s |
| Embeddings | -- | **non définie : aucun modèle d'embeddings déployé** | | |

- **Fenêtre** : 30 jours glissants. **Disponibilité** : requêtes sans échec 5xx / 408 ; les 4xx ne comptent pas côté serveur.
- **Pourquoi 99 % et pas 99,9 %** : un seul réplica sur un seul GPU ; un nœud perdu coûte 721 s (observé), soit 27,8 % du budget mensuel d'un 99,9 % ([module 3](../formation/03-slo-et-budget-derreur.md)).
- **Seuils sur des seaux** : 5, 10, 30, 300 s sont des bornes de seaux des histogrammes LiteLLM (pas de seau à 3 s : [D-31](../DECISIONS.md)).
- **Goodput** : requêtes **par seconde** qui sont bonnes (pas d'échec, TTFT et durée sous seuil). Côté client : `tests/goodput.py` ; côté serveur : `rate(bucket{le=seuil})` par classe.

## 2. Mesures par classe (observé)

Protocole : boucle ouverte, via LiteLLM avec la clé de la classe, 60 s d'échauffement exclu, 300 s de mesure (RAG 7B : 600 s), mode par requête ;
un seul run par couple modèle/classe (**pas de répétition** : voir les limites). « Part bonne » = requêtes bonnes / requêtes envoyées dans la fenêtre, **les échecs du client (timeouts du banc inclus) comptent comme mauvaises**.
Ligne par run : `results/<date>-<scénario>-<profil>-class`, fichiers `goodput.json` et `server_window.json`.

### 2.1 Modèle Qwen2.5-1.5B FP16 (`small-fp16`) - débits : interactive 2, RAG 0,5, multi-tour 0,5, lot 7 req/s

| Classe | Run | Requêtes | Échecs | Part bonne | Objectif | Goodput req/s | Goodput tok/s | TTFT p50 / p95 (client) | TPOT p50 | Durée p95 (client) | GPU util | KV max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| interactive | `2026-11-17-small-fp16-interactive-class` | 600 | 0 | 100.0 % | 95 % (oui) | 2.0 | 283.6 | 0.121 / 0.205 s | 0.0197 s | 5.66 s | 100.0 | 0.0074 |
| rag | `2026-11-17-small-fp16-long-prompt-class` | 150 | 0 | 91.3 % | 95 % (**non**) | 0.457 | 18.0 | 3.13 / 8.81 s | 0.203 s | 30 s | 72.2222 | 0.1414 |
| multiturn | `2026-11-17-small-fp16-multi-turn-class` | 150 | 6 | 96.0 % | 95 % (oui) | 0.48 | 61.4 | 0.44 / 0.813 s | 0.0237 s | 6.41 s | 61.1111 | 0.0353 |
| batch | `2026-11-17-small-fp16-batch-class` | 1112 | 0 | 100.0 % | 95 % (oui) | 3.707 | 933.4 | 39.2 / 42.9 s | 0.273 s | 146 s | 83.3333 | 0.5175 |

### 2.2 Modèle Qwen2.5-7B AWQ (`baseline-7b`) - débits : interactive 1, RAG 0,1, multi-tour 0,5, lot 2,5 req/s

| Classe | Run | Requêtes | Échecs | Part bonne | Objectif | Goodput req/s | Goodput tok/s | TTFT p50 / p95 (client) | TPOT p50 | Durée p95 (client) | GPU util | KV max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| interactive | `2026-11-17-baseline-7b-interactive-class` | 300 | 0 | 100.0 % | 95 % (oui) | 1.0 | 129.8 | 0.315 / 0.574 s | 0.0343 s | 10.3 s | 94.4444 | 0.0353 |
| multiturn | `2026-11-17-baseline-7b-multi-turn-class` | 150 | 6 | 85.3 % | 95 % (**non**) | 0.427 | 54.5 | 1.03 / 4.26 s | 0.0703 s | 30.1 s | 77.7778 | 0.4337 |
| batch | `2026-11-17-baseline-7b-batch-class` | 431 | 238 | 44.3 % | 95 % (**non**) | 0.637 | 146.9 | 146 / 173 s | 0.424 s | 293 s | 100.0 | 0.999 |
| rag | `2026-11-17-baseline-7b-long-prompt-class-nominal` | 60 | 0 | 88.3 % | 95 % (**non**) | 0.088 | 3.0 | 4.59 / 13.2 s | 0.1 s | 28.7 s | 47.3684 | 0.1418 |

(Dernière ligne du tableau 7B : RAG nominal 0,1 req/s, 600 s ; résultats complets dans `results/2026-11-17-baseline-7b-long-prompt-class-nominal`.)

## 3. Ce que les mesures disent

1. **Seule la classe interactive tient son SLO à 100 %**, sur les deux modèles (1,5B à 2 req/s : TTFT p95 0,20 s ; 7B à 1 req/s : 0,57 s).
2. **RAG : aucun des deux modèles ne tient le SLO** (1,5B à 0,5 req/s : 91,3 % ; 7B à seulement 0,1 req/s : 88,3 %). Les requêtes mauvaises sont des TTFT > 10 s ou des durées > 30 s. Le prefill de prompts de
   ~2 750 tokens est le goulot ; le 7B ne tient pas même 0,1 req/s avec ce SLO. **La capacité RAG sous SLO est donc inférieure à ces débits** et reste à déterminer (balayage de débit, séance suivante).
3. **Multi-tour : le 7B manque son SLO à 0,5 req/s (85,3 %)** alors que le 1,5B le tient (96,0 %). Le 7B a un cache KV occupé à 43 % et un TPOT p50 de 0,070 s (1,5B : 0,024 s).
4. **Lot : le 7B s'effondre à 2,5 req/s** (44,3 % de requêtes bonnes ; cache KV à 99,9 %, 153 requêtes en cours et 93 en attente). Le 1,5B, lui, absorbe 7 req/s (933 tokens/s) en respectant son SLO de durée.
   Cela confirme la baseline (le 7B s'effondre au-delà de ~2 req/s) et montre que **la classe lot doit être limitée en débit** (limites LiteLLM) ou servie par le petit modèle.
5. **Ces résultats ne désignent pas encore une configuration cible** : un run par couple, pas de répétition, débits choisis à la main. Ils fixent des **hypothèses à tester** (séances suivantes) : interactive sur le 7B (qualité), RAG et lot sur un
   modèle plus léger ou avec un prefill amélioré (V1), débit du lot plafonné.

## 4. Deux écarts à connaître entre le client et le serveur (observé)

- **Les échecs invisibles du serveur.** Sur le lot 7B, le banc a enregistré **282 timeouts** (`TimeoutError` côté client) ; LiteLLM, sur la même période, n'a compté que **3 erreurs 500 sur 591 requêtes**
  (les autres sont comptées 200 ; **explication non vérifiée** : requête abandonnée par le client mais terminée côté serveur, ou fenêtres de comptage différentes). **Un SLI de disponibilité côté serveur ne voit pas ce que l'utilisateur subit** quand c'est lui
  qui abandonne : il faut compléter par une mesure de bout en bout (client ou sonde) et un SLI de latence.
- **Les quantiles d'histogramme sont grossiers** : sur l'interactive 1,5B, p95 de durée **5,66 s mesuré par le client** contre **8,9 s annoncé par LiteLLM et vLLM** (interpolation dans le seau (5 s, 10 s]). Ce n'est pas un écart réel.

## 5. Budget d'erreur et burn rate

Voir le [module 3](../formation/03-slo-et-budget-derreur.md) (conversion en minutes et requêtes) et le [module 4](../formation/04-burn-rate-et-alertes.md) (14,4x sur 1 h confirmé sur 5 min = page ;
6x sur 6 h confirmé sur 30 min = ticket ; seuils recalculés depuis `slo.windowDays`). Règles : `gitops/observability/config/templates/slo.yaml` ; dashboard : « 06 - SLO par classe de charge » ; runbooks : `LabSLOBurnFast`, `LabSLOBurnSlow`.
Tests `promtool` : 5 cas passent (voir `tests/promtool/lab_rules_test.yml`).

## 6. Alerte réelle (essai de bout en bout)

Surcharge volontaire de la classe **RAG** sur le 7B (`tests/slo_alert_test.sh`, journaux : `results/2026-11-17-slo-alert-test/`), après deux heures de mesures sur ce cluster.

| Étape | Résultat (observé) |
|---|---|
| Surcharge n° 1 : 0,5 req/s pendant 10 min | burn rate 5 min = **20** (le maximum : 100 % de requêtes mauvaises / budget de 5 %), burn rate 1 h = **11,3** (page à 14,4), burn rate 6 h = **5,3** (ticket à 6) : **aucune alerte**, conforme aux seuils |
| Surcharge n° 2 : 0,5 req/s, interrompue après ~4 min (demande de l'utilisateur) | **`LabSLOBurnSlow` en FIRING à 12:16:33**, classe `rag`, SLI `ttft` (12:17:33) et `e2e` (12:16:33) |
| Chaîne de notification | Alertmanager a émis l'alerte (`/api/v2/alerts` : `active`) et le récepteur du cluster (`alert-sink`) l'a reçue avec les labels `class=rag`, `sli=...`, `severity=warning`, l'annotation de description et l'URL du runbook `LabSLOBurnSlow.md` |
| `LabSLOBurnFast` | **non déclenchée** pendant les essais : le burn rate 1 h n'a pas dépassé 14,4 (maximum observé avant la surcharge n° 3 : 12,4) |

Lecture :
- **Une surcharge de 10 minutes ne justifie pas une page** : elle fait monter le burn 1 h à 11,3x, soit environ 1,6 % du budget mensuel du SLI. C'est le comportement voulu (module 4).
- Il faut **un peu moins de 20 minutes de surcharge cumulée** (deux essais) pour franchir le seuil du ticket (6x sur 6 h confirmé sur 30 min).
- Le chemin « règle -> Prometheus -> Alertmanager -> récepteur » est donc **prouvé sur le cluster pour l'alerte lente**. Pour l'alerte rapide, seuls les **tests `promtool`** (5 cas) la valident.
- Au démarrage de l'essai suivant, le burn rate de 5 min vaut `NaN` (aucun trafic) : une règle sans trafic ne déclenche rien (une classe silencieuse n'alerte pas ; limite à connaître).


## 7. Limites

- **Un seul run par couple modèle/classe** : aucune dispersion ; on ne déclare donc **aucun gain** à partir de ces tableaux. Le bruit mesuré en séance 1 (CV du TTFT p95 de 7 % pour le 1,5B, 29 % pour le 7B) s'applique : les parts « bonnes » proches de l'objectif (91 %, 88 %, 85 %, 96 %) sont à lire comme « autour de l'objectif », pas comme des mesures précises.
- **RAG 7B : 60 requêtes seulement** (0,1 req/s x 600 s) ; **RAG 1,5B, multi-tour : 150 requêtes** ; les parts bonnes ont une incertitude de plusieurs points.
- Le goodput client est calculé sur les `300 s` finales d'envoi ; le serveur compte les requêtes **terminées** dans sa fenêtre : ils diffèrent quand une file existe.
- Les SLI serveur par classe reposent sur les métriques de **LiteLLM** (clé = classe) : un client qui utiliserait la mauvaise clé fausserait sa classe.
- Les SLO sont des **valeurs de départ** déduites des mesures ; elles sont à resserrer ou à relâcher quand on connaîtra mieux l'usage réel.
- Embeddings : classe non mesurée.
