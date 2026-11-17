# Module 1 - Mesurer sans se tromper : boucle ouverte, échauffement, répétitions, bruit

**En une phrase.** Avant de dire « c'est plus rapide », il faut savoir de combien le résultat varie quand on ne change **rien**. Ce module montre comment le mesurer, avec les chiffres de ce cluster.

<!-- mots: boucle ouverte, échauffement, percentile, bruit de mesure, débit, saturation -->
> **Mots à connaître**
> - **Boucle ouverte / fermée** : Ouverte : on impose un débit d'arrivée (comme de vrais utilisateurs) ; elle révèle les files. Fermée : N clients attendent chacun leur réponse ; elle masque la surcharge.
> - **Échauffement** : Début de run exclu de la mesure (caches vides, régime pas encore stable). Ici 60 s.
> - **Percentile (p50, p95, p99)** : p95 = 95 % des requêtes vont plus vite que cette valeur. Le p50 est la médiane. Le p95 montre les cas lents.
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
   écart-type / moyenne) dit à partir de quel écart on peut parler d'un effet.

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

### Lecture

- **Les débits sont stables** (CV <= 2,7 %) pour les deux modèles : une amélioration de quelques pourcents du débit est détectable.
- **Les latences de queue (p95) sont bruyantes pour le 7B** (CV 19 à 29 %) et **beaucoup moins pour le 1,5B** (CV 2 à 7 %).
- Le 7B tourne plus près de sa capacité : son plateau est d'environ 1,5 à 2 req/s, on le sollicitait à 1 req/s (environ 50-67 % de la
  capacité). Le 1,5B plafonne vers 5 req/s et on le sollicitait à 2 req/s (environ 40 %). **Hypothèse (non vérifiée)** : près de la capacité,
  de petites variations d'arrivée sont amplifiées par la file, d'où un p95 plus instable. Les deux mesures n'ont pas la même charge relative,
  donc on ne peut pas attribuer l'écart de bruit au seul modèle.

### Seuils de décision pour la suite (calcul)

Règle retenue : un écart n'est un gain que s'il dépasse environ **deux écarts-types** (~2 x CV) de la métrique.

| Métrique | Seuil 7B (à ne pas franchir pour déclarer un gain) | Seuil 1,5B |
|---|---|---|
| Tokens/s, requêtes/s | ~5 % | ~1,5 % |
| TPOT p50 | ~5 % | ~1,5 % |
| TTFT p50 | ~20 % | ~4 % |
| TTFT p95, latence p95 | **~45-60 %** | ~5-14 % |

Limites de ce calcul : **trois répétitions seulement** (une estimation de dispersion à partir de trois points est fragile), un seul débit par
modèle, et un seul jeu de données synthétique. Ce sont des ordres de grandeur pour décider, pas des garanties statistiques.

## 4. Un piège rencontré (observé)

Une mesure antérieure du 7B (3 min, sans échauffement) donnait TPOT p50 = **0,049 s** ; la nouvelle (5 min, 60 s d'échauffement) donne
**0,070 s**, soit +43 %, bien au-delà du CV de 2,3 %. **La cause n'est pas élucidée** (durée du run, échauffement, état des caches du moteur :
plusieurs pistes). Conséquence : on ne compare **jamais** deux runs de durée ou d'échauffement différents. C'est exactement ce que le bruit
« à protocole égal » ne peut pas capturer.

## 5. À retenir

1. Imposez un débit d'arrivée (boucle ouverte) pour toute question de latence ; la boucle fermée sert à chercher un débit maximal.
2. Excluez l'échauffement, répétez au moins trois fois, calculez le CV : c'est lui qui fixe le plus petit gain que vous pouvez croire.
3. Un modèle plus proche de sa capacité est plus bruyant : comparez à **charge relative** égale, ou annoncez-le.

## 6. Exercice (à faire vous-même)

Objectif : déterminer si une réduction de `--max-num-seqs` (le nombre maximal de requêtes que vLLM traite ensemble) sur le 7B a un effet, **sans** que je vous donne le verdict.
1. Rédigez l'hypothèse, la métrique de décision et le critère de succès **avant** de lancer quoi que ce soit.
2. Dites combien de répétitions il vous faut et pourquoi, à partir du tableau du §3.
3. Dites quelle métrique ne peut pas servir de critère avec trois répétitions (indice : la dernière ligne du tableau de seuils).
Vérification : votre critère sur le TTFT p95 doit exiger un gain d'au moins ~45-60 %, ou davantage de répétitions.
