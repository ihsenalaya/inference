# Formation : opérer l'inférence LLM sur ce cluster, avec les vrais chiffres

Parcours en modules courts. Chaque module donne : le concept (10 lignes), la configuration réelle du dépôt, **les chiffres mesurés sur ce cluster** (AKS, 1 x T4), une lecture guidée,
trois points à retenir et **un exercice à faire vous-même** (objectif et vérification, pas la solution). Marques de fiabilité : **(observé)**, **(config)**, **(doc)**, **(calcul)**, **(non vérifié)**
comme dans le [guide](../guide/README.md). Prérequis : savoir ce que sont un SLI, un SLO et un budget d'erreur ; on n'explique pas le SRE générique, seulement ce qui est propre à l'inférence.

| Module | Sujet | Ce que vous saurez faire |
|---|---|---|
| [1](01-mesurer-sans-se-tromper.md) | Mesurer sans se tromper | Distinguer un gain réel du bruit (CV mesurés : 7B et 1,5B) |
| [2](02-classes-de-charge-et-sli.md) | Classes de charge et SLI | Définir des classes, savoir où mesurer chaque SLI, éviter les pièges d'histogrammes |
| [3](03-slo-et-budget-derreur.md) | SLO et budget d'erreur | Proposer un SLO depuis une baseline, le convertir en minutes et en requêtes |
| [4](04-burn-rate-et-alertes.md) | Burn rate et alertes | Calculer et tester des alertes multi-fenêtres |
| [5](05-lire-un-gpu.md) | Lire un GPU | Ne plus confondre « 100 % utilisé » et « saturé » (compteurs DCGM réels du T4) |
| [6](06-demarrage-a-froid.md) | Démarrage à froid | Décomposer et comparer honnêtement un démarrage de cluster |

Compléments : [SLO par classe](../sre/SLO.md), [état des lieux de la séance 1](../sre/ETAT-DES-LIEUX.md), [compte rendu des séances](../sre/SEANCES.md), [guide technique](../guide/README.md), [fiches par service](../services/00-index.md).

Les exercices ne sont **pas corrigés** ici : la vérification indique ce qui doit être vrai si vous avez réussi. Les séances 3 à 10 de la campagne SRE (goulots, moteur, quantization, routage, autoscaling,
opérations GPU, game days, capacité) ajouteront leurs propres modules au fil des séances.
