# Module 1 - Mesurer sans se tromper : boucle ouverte, échauffement, répétitions, bruit

**En une phrase.** Avant de dire « c'est plus rapide », il faut savoir de combien le résultat varie quand on ne change **rien**. Ce module montre comment le mesurer, puis comment décider si un changement a un effet, avec les chiffres de ce cluster.

<!-- mots: boucle ouverte, échauffement, percentile, ttft, tpot, latence de bout en bout, bruit de mesure, débit, saturation -->
> **Mots à connaître**
> - **Boucle ouverte / fermée** : Ouverte : on impose un débit d'arrivée (comme de vrais utilisateurs) ; elle révèle les files. Fermée : N clients attendent chacun leur réponse ; elle masque la surcharge.
> - **Échauffement** : Début de run exclu de la mesure (caches vides, régime pas encore stable). Ici 60 s.
> - **Percentile (p50, p95, p99)** : p95 = 95 % des requêtes vont plus vite que cette valeur. Le p50 est la médiane. Le p95 montre les cas lents.
> - **TTFT** : *Time To First Token* : attente avant le premier token de la réponse. C'est ce que l'utilisateur ressent en premier.
> - **TPOT** : *Time Per Output Token* : durée moyenne entre deux tokens de la réponse. C'est la « fluidité » du texte qui s'affiche.
> - **Latence de bout en bout** : Durée entre l'envoi et le dernier token de la réponse.
> - **Bruit de mesure / CV** : Variation d'un run à l'autre. CV = écart-type / moyenne. Un écart plus petit que le bruit n'est pas un gain.
> - **Débit** : Quantité servie par seconde : **req/s** (requêtes) ou **tokens/s** (tokens de sortie).
> - **Saturation / plateau** : Point où le serveur ne peut plus servir davantage : le débit n'augmente plus et la file grossit.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

**Objectif** : savoir quand un écart de mesure est un **gain réel** et quand c'est du **bruit**. Tout le reste de la campagne d'optimisation
(quantization, `max-num-seqs`, routage, autoscaling) repose sur ce module. Marques de fiabilité : voir [le guide](../guide/README.md).

## 1. Le concept en dix lignes

1. Un serveur d'inférence se comporte comme une **file d'attente** : quand le débit demandé approche sa capacité, le temps d'attente
   n'augmente pas proportionnellement, il **explose**.
2. **Boucle fermée** (N clients qui renvoient une requête dès qu'ils ont une réponse) : si le serveur ralentit, les clients ralentissent
   aussi, donc la charge **diminue toute seule** et la file ne grandit jamais. La latence paraît bonne. C'est utile pour chercher un
   débit maximal, trompeur pour juger une latence.
3. **Boucle ouverte** (un débit d'arrivée imposé, par exemple 2 req/s, quoi que fasse le serveur) : c'est ce que font de vrais utilisateurs.
   Si le serveur ne suit pas, la file grandit et on le voit.
4. Un moteur a un **régime transitoire** (caches vides, graphes CUDA, cache de préfixes) puis un régime établi. On exclut le transitoire :
   c'est l'**échauffement** (60 s ici).
5. Une mesure unique n'a pas de sens : on répète (3 fois ici) et on calcule la **dispersion**. Le **coefficient de variation** (CV =
   écart-type / moyenne) exprime ce bruit en pourcentage de la valeur.
6. Le **seuil de décision** est l'écart minimal entre une série de runs « avant » et une série « après » un changement, au-delà duquel
   le bruit seul n'explique plus l'écart. Il se déduit de l'écart-type par un test statistique (§4).

| | Boucle fermée | Boucle ouverte |
|---|---|---|
| Principe | N clients ; chacun renvoie une requête dès qu'il a sa réponse | Un débit d'arrivée imposé, indépendant du serveur |
| Si le serveur ralentit | Les clients ralentissent aussi : la charge baisse et la file ne grandit pas | Les requêtes continuent d'arriver : la file grandit et la latence monte |
| Usage | Chercher un débit maximal | Toute question de latence |

## 2. Ce que le lab fait (config)

- Générateur : `inference-perf` v0.7.0, profils dans `gitops/bench/profiles/` (`steady` : débit constant ; `sweep` : paliers de débit).
- Boucle **ouverte** pour toute mesure de latence ; l'échauffement est le premier stage (`WARMUP=60`), exclu des résultats
  (`stage_1_*`). Lancer : `WARMUP=60 DURATION=300 RATE=2 ./lab.sh bench steady`.
- Une seule variable change entre deux runs (D-29 dans [DECISIONS](../DECISIONS.md)).
- Les deux modèles sont mesurés au **même** type de charge (`steady`, entrées de 128 à 1 024 tokens, sorties de 64 à 256).

## 3. Les chiffres : le bruit du lab (observé)

Trois répétitions de 300 s de mesure (après 60 s d'échauffement), boucle ouverte, via LiteLLM. Calcul : `tests/noise.py`.

| Métrique | 7B AWQ à 1 req/s : médiane | **CV** | 1,5B FP16 à 2 req/s : médiane | **CV** |
|---|---|---|---|---|
| TTFT p50 (s) | 0,666 | **10,5 %** | 0,200 | **2,0 %** |
| TTFT p95 (s) | 1,95 | **29,1 %** | 0,416 | **6,9 %** |
| TPOT p50 (s) | 0,0696 | **2,3 %** | 0,0256 | **0,7 %** |
| TPOT p95 (s) | 0,131 | **18,7 %** | 0,0359 | **4,9 %** |
| Latence p95 (s) | 23,5 | **22,0 %** | 7,73 | **2,3 %** |
| Tokens de sortie / s | 146 | **2,7 %** | 283 | **0,7 %** |
| Requêtes / s servies | 0,979 | **0,2 %** | 1,975 | **0,2 %** |
| Échecs | 0 | | 0 | |

Runs : `results/2026-11-17-baseline-7b-steady-noise-r{1,2,3}` et `results/2026-11-17-small-fp16-steady-noise-r{1,2,3}`.

### Comment lire le tableau

**D'où vient un chiffre (calcul).** Chaque valeur est le résultat de trois niveaux :

1. **Par requête** : le générateur mesure le TTFT, le TPOT et la latence de chaque requête. Un run de 300 s de mesure à 1 req/s contient environ 300 requêtes ; à 2 req/s, environ 600.
2. **Par run** : on résume ces requêtes par un percentile (p50 ou p95). Chaque run donne donc **une valeur par métrique**.
3. **Sur les trois runs** : la colonne « médiane » est la valeur du milieu des trois valeurs ; le **CV** est l'écart-type de ces trois valeurs divisé par leur moyenne.

Deux médianes à ne pas confondre : le **p50** est le milieu des requêtes d'un run ; la colonne **médiane** est le milieu des trois runs. Le CV porte sur la valeur d'une métrique d'un run à l'autre, pas sur le nombre de requêtes.

**Pourquoi les p95 sont plus bruités que les p50 (calcul).** Le p50 est fixé par la masse des requêtes. Le p95 est fixé par les 5 % les plus lentes, soit une quinzaine de requêtes sur environ 300 à 1 req/s : quelques requêtes lentes de plus ou de moins d'un run à l'autre suffisent à le déplacer.

**Le débit est mesuré, pas calculé.** Les lignes « Tokens de sortie / s » et « Requêtes / s servies » sont relevées pendant la fenêtre de mesure. Les caractéristiques du GPU n'en donnent qu'un plafond théorique, jamais atteint tel quel : le débit réel dépend aussi du modèle, de la quantization, du moteur et de ses réglages.

**Le bruit.** C'est la variation de la mesure quand on ne change rien (même configuration, même protocole). Elle vient de facteurs non maîtrisés : instants d'arrivée des requêtes, état du GPU, du réseau et des caches (**non vérifié** : les causes exactes ne sont pas isolées sur ce cluster). Ce n'est pas une erreur de calcul : c'est la mesure qui varie.

**Validité des runs (observé).** Les requêtes servies par seconde sont proches du débit imposé (0,979 pour 1 req/s ; 1,975 pour 2 req/s) et il n'y a aucun échec : le serveur a suivi la charge, les runs sont exploitables.

### Lecture

- **Les débits sont stables** (CV <= 2,7 %) pour les deux modèles : une amélioration de quelques pourcents du débit est détectable.
- **Les latences de queue (p95) sont bruyantes pour le 7B** (CV 19 à 29 %) et **beaucoup moins pour le 1,5B** (CV 2 à 7 %).
- Le 7B tourne plus près de sa capacité : son plateau est d'environ 1,5 à 2 req/s, on le sollicitait à 1 req/s (environ 50-67 % de la
  capacité). Le 1,5B plafonne vers 5 req/s et on le sollicitait à 2 req/s (environ 40 %). **Hypothèse (non vérifiée)** : près de la capacité,
  de petites variations d'arrivée sont amplifiées par la file, d'où un p95 plus instable. Les deux mesures n'ont pas la même charge relative,
  donc on ne peut pas attribuer l'écart de bruit au seul modèle.

## 4. Décider si un changement a un effet (doc, calcul)

### Le protocole

1. **Référence** : 3 runs de la configuration actuelle (les runs du §3).
2. **Changement** : un seul réglage modifié, par exemple `--max-num-seqs`.
3. **Variante** : 3 runs avec ce réglage, au même protocole (même profil, même débit, 60 s d'échauffement, 300 s de mesure).
4. **Comparaison** : la moyenne des 3 runs de la variante est comparée à la moyenne des 3 runs de référence. L'écart doit dépasser le seuil de la métrique.

### La règle : le test t à deux échantillons (doc)

La question « deux séries de mesures ont-elles la même moyenne ? » se traite par un **test t à deux échantillons**
([NIST/SEMATECH e-Handbook, §7.3.1](https://itl.nist.gov/div898/handbook/prc/section3/prc31.htm)). En évaluation de performance,
la pratique recommandée est la même : des intervalles de confiance à 95 % sur la différence
([Georges, Buytaert, Eeckhout, OOPSLA 2007](https://dri.es/files/oopsla07-georges.pdf)).

```
écart minimal = t(0,975 ; 2n - 2) x racine(2 / n) x écart-type
n = 3 runs de chaque côté : 2,78 x 0,82 x écart-type = 2,27 x écart-type, soit 2,27 x CV en pourcentage
```

- **Pourquoi 95 %** : c'est la convention usuelle. Quand rien ne change, un écart supérieur au seuil n'apparaît qu'environ une fois sur vingt.
  Pour une seule valeur dont le bruit est parfaitement connu, le facteur serait 1,96 (règle 68-95-99,7,
  [NIST/SEMATECH e-Handbook, §7.2.6.1](https://itl.nist.gov/div898/handbook/prc/section2/prc261.htm)).
- **Pourquoi 2,27 et non 1,96** : on compare deux moyennes, chacune avec son propre bruit (facteur racine(2 / n)), et l'écart-type est
  estimé sur 3 runs seulement, ce qui impose la loi de Student (t = 2,78 pour 4 degrés de liberté) au lieu de 1,96.

### Les seuils du lab (calcul)

Seuil = 2,27 x écart-type des 3 runs du §3. La **zone du bruit** est l'intervalle autour de la moyenne de référence dans lequel la moyenne
de la variante ne permet pas de conclure. Latences : plus bas = mieux ; tokens/s : plus haut = mieux. La moyenne de référence diffère de la
médiane du §3 quand un des trois runs s'écarte des deux autres (7B, TTFT p50 : 0,653 à 0,786 s selon le run).

**7B AWQ à 1 req/s**

| Métrique | Moyenne de référence | CV | Seuil | Zone du bruit | Usage |
|---|---|---|---|---|---|
| TTFT p50 (s) | 0,702 | 10,5 % | ≈ 24 % | 0,535 à 0,868 | Critère, si l'effet attendu dépasse 24 % |
| TTFT p95 (s) | 2,15 | 29,1 % | ≈ 66 % | 0,73 à 3,57 | Garde-fou |
| TPOT p50 (s) | 0,0695 | 2,3 % | ≈ 5 % | 0,0658 à 0,0732 | **Critère de décision** |
| TPOT p95 (s) | 0,144 | 18,7 % | ≈ 42 % | 0,083 à 0,204 | Garde-fou |
| Latence p95 (s) | 26,5 | 22,0 % | ≈ 50 % | 13,3 à 39,6 | Garde-fou |
| Tokens de sortie / s | 145 | 2,7 % | ≈ 6 % | 136 à 154 | **Critère de décision** |
| Requêtes / s servies | 0,979 | 0,2 % | - | - | Contrôle de validité |
| Échecs | 0 | - | - | - | Contrôle de validité |

**1,5B FP16 à 2 req/s**

| Métrique | Moyenne de référence | CV | Seuil | Zone du bruit | Usage |
|---|---|---|---|---|---|
| TTFT p50 (s) | 0,200 | 2,0 % | ≈ 4,6 % | 0,191 à 0,209 | Critère de décision |
| TTFT p95 (s) | 0,406 | 6,9 % | ≈ 16 % | 0,343 à 0,470 | Critère de décision |
| TPOT p50 (s) | 0,0256 | 0,7 % | ≈ 1,6 % | 0,0252 à 0,0260 | Critère de décision |
| TPOT p95 (s) | 0,0359 | 4,9 % | ≈ 11 % | 0,0319 à 0,0399 | Critère de décision |
| Latence p95 (s) | 7,83 | 2,3 % | ≈ 5 % | 7,42 à 8,23 | Critère de décision |
| Tokens de sortie / s | 283 | 0,7 % | ≈ 1,5 % | 279 à 288 | Critère de décision |
| Requêtes / s servies | 1,972 | 0,2 % | - | - | Contrôle de validité |
| Échecs | 0 | - | - | - | Contrôle de validité |

- **Critère de décision** : seuil assez bas pour détecter un effet réaliste.
- **Garde-fou** : seuil trop élevé pour conclure à un gain avec 3 runs ; la métrique sert seulement à repérer une forte dégradation
  (moyenne de la variante au-dessus de la zone du bruit).
- **Contrôle de validité** : vérifie que le serveur a suivi la charge imposée ; ce n'est pas une mesure de performance.

### Le nombre de répétitions (calcul)

| Runs (référence / variante) | Seuil | 7B, TPOT p50 | 7B, TTFT p95 |
|---|---|---|---|
| 3 / 1 (à éviter) | ≈ 5,0 x CV | ≈ 11 % | ≈ 145 % |
| 3 / 3 | ≈ 2,3 x CV | ≈ 5 % | ≈ 66 % |
| 5 / 5 | ≈ 1,5 x CV | ≈ 3,4 % | ≈ 42 % |
| 10 / 10 | ≈ 0,9 x CV | ≈ 2,2 % | ≈ 27 % |
| 20 / 20 | ≈ 0,6 x CV | ≈ 1,5 % | ≈ 19 % |

Un seul run de variante garde tout son bruit : le seuil fait plus que doubler par rapport à 3 runs. Chaque répétition supplémentaire abaisse le seuil,
au prix du temps de mesure (un run complet dure 6 min).

### Quand le seuil est irréaliste (p95 du 7B)

1. **Garde-fou** : décider sur le TPOT p50 et les tokens/s ; vérifier seulement que les p95 ne sortent pas de la zone du bruit par le haut.
2. **Plus de répétitions** : voir le tableau ci-dessus ; 10 runs représentent environ 1 h de mesure par configuration.
3. **Runs plus longs** : davantage de requêtes par run devraient stabiliser le p95 (**non vérifié**). Le bruit doit alors être remesuré
   avec la nouvelle durée : on ne compare jamais des runs de durées différentes (§5).

### Limites

Trois répétitions seulement (une estimation d'écart-type à partir de trois points est fragile) ; le test suppose des dispersions égales et
des valeurs à peu près normalement distribuées d'un run à l'autre ; un seul débit par modèle ; un seul jeu de données synthétique. Ce sont
des ordres de grandeur pour décider, pas des garanties statistiques.

## 5. Un piège rencontré (observé)

Une mesure antérieure du 7B (3 min, sans échauffement) donnait TPOT p50 = **0,049 s** ; la nouvelle (5 min, 60 s d'échauffement) donne
**0,070 s**, soit +43 %, bien au-delà du CV de 2,3 %. **La cause n'est pas élucidée** (durée du run, échauffement, état des caches du moteur :
plusieurs pistes). Conséquence : on ne compare **jamais** deux runs de durée ou d'échauffement différents. C'est exactement ce que le bruit
« à protocole égal » ne peut pas capturer.

## 6. À retenir

1. Imposez un débit d'arrivée (boucle ouverte) pour toute question de latence ; la boucle fermée sert à chercher un débit maximal.
2. Excluez l'échauffement, faites au moins 3 runs avant et 3 runs après, au même protocole : un écart n'est crédible qu'au-delà
   d'environ 2,3 x CV (test t à deux échantillons).
3. Décidez sur les métriques stables (TPOT p50, tokens/s) ; avec 3 runs, les p95 du 7B ne servent que de garde-fou. Comparez deux modèles
   à charge relative égale, ou annoncez-le.

## 7. Exercice (à faire vous-même)

Objectif : déterminer si une réduction de `--max-num-seqs` (le nombre maximal de requêtes que vLLM traite ensemble) sur le 7B a un effet, **sans** que je vous donne le verdict.
1. Rédigez l'hypothèse, la métrique de décision et le critère de succès **avant** de lancer quoi que ce soit.
2. Dites combien de répétitions il vous faut et pourquoi, à partir des tableaux du §4.
3. Dites quelle métrique ne peut pas servir de critère avec trois répétitions (indice : colonne « Usage » du tableau du 7B, §4).
Vérification : votre critère sur le TTFT p95 doit exiger un écart d'au moins ~66 % avec 3 runs contre 3, ou davantage de répétitions.

## Sources

- NIST/SEMATECH e-Handbook of Statistical Methods, [§7.3.1 « Do two processes have the same mean? »](https://itl.nist.gov/div898/handbook/prc/section3/prc31.htm) (test t à deux échantillons).
- NIST/SEMATECH e-Handbook of Statistical Methods, [§7.2.6.1](https://itl.nist.gov/div898/handbook/prc/section2/prc261.htm) (part des valeurs à 1, 2 et 3 écarts-types).
- A. Georges, D. Buytaert, L. Eeckhout, [« Statistically Rigorous Java Performance Evaluation »](https://dri.es/files/oopsla07-georges.pdf), OOPSLA 2007, DOI 10.1145/1297105.1297033.
