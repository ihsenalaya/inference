# Module 4 - Burn rate : alerter sur la vitesse à laquelle on consomme le budget d'erreur

**Objectif** : comprendre pourquoi on remplace l'alerte « latence p95 > seuil » par une alerte de **taux de consommation du budget
(burn rate) à fenêtres multiples**, savoir **recalculer** les seuils pour une autre fenêtre de SLO, et lire/tester les règles du lab.
Vous connaissez déjà SLI, SLO et budget d'erreur : ce module ne les réexplique pas, il montre ce qui est propre à ce lab.

## 1. Le concept en dix lignes

1. Le **budget d'erreur** est la part de requêtes « mauvaises » que l'objectif tolère : 1 - objectif. Objectif 95 % de TTFT <= 5 s -> budget **5 %**.
2. Le **burn rate** est la vitesse de consommation : `part de requêtes mauvaises observée / budget`. Burn rate **1** : à ce rythme, le budget de
   la fenêtre du SLO (30 jours) s'épuise exactement au bout de 30 jours. Burn rate **14,4** : il s'épuise en 30 j / 14,4 = **50 heures**.
3. Une alerte à seuil fixe (« p95 > 5 s pendant 5 min ») réagit au bruit court **et** rate les dégradations lentes. Le burn rate règle les deux.
4. On exige **deux fenêtres à la fois** : une longue (la dégradation est réelle) et une courte (elle est **encore en cours**, pas déjà finie).
5. Seuils du SRE Workbook pour une fenêtre de 30 jours : **14,4x sur 1 h** (confirmé sur 5 min) = on consomme **2 %** du budget en une heure -> page ;
   **6x sur 6 h** (confirmé sur 30 min) = **5 %** du budget en 6 h -> ticket.

## 2. D'où viennent 14,4 et 6 (calcul)

`burn rate = part du budget consommée dans la fenêtre d'alerte x durée de la fenêtre du SLO / durée de la fenêtre d'alerte`

| Alerte | Part du budget | Fenêtre d'alerte | Fenêtre SLO 30 j (720 h) | Burn rate |
|---|---|---|---|---|
| Rapide (page) | 2 % | 1 h | 720 h | 0,02 x 720 / 1 = **14,4** |
| Lente (ticket) | 5 % | 6 h | 720 h | 0,05 x 720 / 6 = **6** |

Pour une **autre fenêtre de SLO**, on recalcule. Exemple pour **7 jours** (168 h), mêmes parts de budget : rapide = 0,02 x 168 / 1 = **3,36** ;
lente = 0,05 x 168 / 6 = **1,4**. Dans le dépôt, il suffit de changer `slo.windowDays` dans
`gitops/observability/config/values.yaml` : le chart (`templates/slo.yaml`) recalcule les seuils (**config**). Pourquoi c'est utile : avec une
fenêtre courte, le même 2 % de budget part plus vite, donc le seuil est plus bas.

**Seuil en part de requêtes mauvaises** (ce que l'alerte compare réellement) = burn rate x budget :

| Classe, SLI | Budget | Page (14,4x) | Ticket (6x) |
|---|---|---|---|
| Disponibilité (objectif 99 %) | 1 % | **14,4 %** d'échecs | **6 %** d'échecs |
| TTFT ou durée (objectif 95 %) | 5 % | **72 %** de requêtes trop lentes | **30 %** de requêtes trop lentes |

Lecture : pour un objectif de 95 %, la page ne part que si **72 %** des requêtes sont lentes pendant une heure. C'est la conséquence arithmétique
d'un budget de 5 % : on ne peut pas dépasser 100 %, donc 14,4 x 5 % = 72 % est déjà proche du maximum. **Un objectif plus lâche rend le seuil rapide
difficile à atteindre.** C'est une limite connue de la méthode, à garder en tête pour les SLO de latence à 95 %.

## 3. Ce qui est déployé (config)

- `gitops/observability/config/templates/slo.yaml` : règles d'enregistrement `slo:error_ratio:rate{5m,30m,1h,6h}` par classe et par SLI
  (`availability`, `ttft`, `e2e`), `slo:error_budget`, `slo:burn_rate:*`, et deux alertes `LabSLOBurnFast` (critique) et `LabSLOBurnSlow` (warning).
- **Source du SLI** : les métriques de **LiteLLM** par alias de clé virtuelle (une clé = une classe). Pour la latence on compte les requêtes **sous**
  le seuil à partir des **seaux d'histogramme** : `1 - rate(bucket{le="5.0"}) / rate(count)`.
- **Contrainte propre à ce lab (observé)** : les seaux de LiteLLM sont `0.005 ... 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 420, 600`. **Il n'y a pas de seau à 3 s** :
  un seuil de SLO doit tomber **exactement** sur un seau, sinon la règle ne renvoie rien. Le premier jet du lab fixait 3 s ; il a été changé en 5 s après lecture des
  vrais seaux sur le cluster.
- **Disponibilité** : échecs = `exception_status` 5xx ou 408 ; les 4xx (faute du client, par exemple un modèle inconnu) **ne consomment pas** le budget.

## 4. Tests (observé)

`promtool test rules` (`tests/promtool/lab_rules_test.yml`), qui tournent dans `tests/static.sh` :

| Test | Entrée | Résultat attendu et obtenu |
|---|---|---|
| Burn rapide, TTFT | 80 % de requêtes > 5 s pendant 1 h 10 | alerte `LabSLOBurnFast` (classe interactive, SLI ttft) |
| Pas de page à 10x | 50 % de requêtes lentes (10 x le budget) | aucune alerte |
| Pic court sur heure saine | 60 min saines, puis 5 min tout lent | aucune alerte (la fenêtre longue protège) |
| Burn rapide, disponibilité | 30 % d'échecs pendant 1 h 10 | alerte (classe batch, SLI availability) |
| Burn lent | 10 % d'échecs (10x le budget de 1 %) pendant 7 h | `LabSLOBurnSlow` seule, pas de page |

## 5. Essai sur le cluster

Surcharge de la classe RAG sur le 7B (détail : section 6 du [document SLO](../sre/SLO.md)) :

| Essai | burn 5 min | burn 1 h | burn 6 h | Alerte |
|---|---|---|---|---|
| 10 min à 0,5 req/s | 20 (maximum) | 11,3 (page à 14,4) | 5,3 (ticket à 6) | **aucune** |
| 4 min de plus | 20 | 12,4 | > 6 | **`LabSLOBurnSlow` FIRING**, reçue par le récepteur |

Trois leçons : (1) le burn 5 min atteint 20 tout de suite, la fenêtre longue est celle qui filtre ; (2) **dix minutes d'incident franc** n'atteignent
pas le seuil de page, car il représente environ 2 % du budget **mensuel** ; (3) l'alerte lente a mis environ vingt minutes de surcharge cumulée à partir.
L'alerte rapide n'a **pas** été déclenchée sur le cluster (seulement par `promtool`).

## 6. À retenir

1. Burn rate = (part de mauvaises requêtes) / (budget). Il dit en combien de temps le budget s'épuise, pas seulement « c'est lent ».
2. Deux fenêtres : la longue confirme que c'est réel, la courte confirme que c'est en cours. 14,4x/1 h pour la page, 6x/6 h pour le ticket (fenêtre de 30 jours).
3. Les seuils dépendent de la fenêtre du SLO : recalculez-les, ne les copiez pas. Et vérifiez que votre seuil de latence est un seau de l'histogramme.

## 7. Exercice (à faire vous-même)

Objectif : écrire la règle d'alerte pour une **nouvelle classe** et prouver qu'elle marche.
1. Choisissez un objectif et une fenêtre (par exemple 99 % de disponibilité sur 14 jours). Calculez à la main les seuils rapide et lent.
2. Ajoutez la classe dans `slo.classes` et un test `promtool` qui échoue **avant** votre changement et passe **après**.
3. Dites quelle part d'échecs déclenche la page, et si cette part est atteignable.
Vérification : pour 14 jours (336 h), le seuil rapide est 0,02 x 336 / 1 = 6,72 ; avec un budget de 1 %, la page part à 6,72 % d'échecs.
