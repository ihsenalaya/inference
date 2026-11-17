# Formation : opérer l'inférence LLM sur ce cluster, avec les vrais chiffres

Sept modules courts, pensés pour un **débutant** : aucun prérequis en inférence ni en GPU. Chaque module commence par « En une phrase » et une petite boîte « Mots à connaître » (le [glossaire complet](../sre/GLOSSAIRE.md) réunit tous les mots).
Chaque module donne ensuite : le concept en quelques lignes, la configuration réelle du dépôt, **les chiffres mesurés sur ce cluster** (AKS, 1 x T4), une lecture guidée, trois points à retenir et **un exercice à faire vous-même**
(objectif et vérification, pas la solution).

Marques de fiabilité utilisées partout : **(observé)** vu sur le cluster · **(config)** écrit dans le dépôt · **(doc)** documentation officielle · **(calcul)** déduit d'un calcul · **(non vérifié)** plausible mais pas confirmé
(comme dans le [guide](../guide/README.md)).

## Par où commencer

1. Si vous n'avez jamais touché à un LLM : lisez d'abord le [guide 01 - L'inférence expliquée](../guide/01-inference-expliquee.md), puis revenez ici.
2. Suivez les modules **dans l'ordre** : chacun s'appuie sur le précédent.

| Module | Sujet | Ce que vous saurez faire |
|---|---|---|
| [1](01-mesurer-sans-se-tromper.md) | Mesurer sans se tromper | Distinguer un gain réel du bruit (écarts mesurés sur le 7B et le 1,5B) |
| [2](02-classes-de-charge-et-sli.md) | Classes de charge et SLI | Définir des types d'usage, savoir où mesurer chaque indicateur, éviter les pièges d'histogrammes |
| [3](03-slo-et-budget-derreur.md) | SLO et budget d'erreur | Poser un objectif à partir d'une mesure, le convertir en minutes et en requêtes |
| [4](04-burn-rate-et-alertes.md) | Burn rate et alertes | Calculer et tester des alertes qui réagissent à la vitesse de consommation de la marge d'erreur |
| [5](05-lire-un-gpu.md) | Lire un GPU | Ne plus confondre « 100 % utilisé » et « saturé » (compteurs réels du T4) |
| [6](06-demarrage-a-froid.md) | Démarrage à froid | Décomposer un démarrage de cluster et comparer honnêtement deux mesures |
| [7](07-sante-et-efficacite-du-gpu.md) | Santé et efficacité du GPU | Juger un GPU sur trois axes (santé, saturation, efficacité) ; détail dans le [dossier docs/gpu](../gpu/README.md) |

Compléments : [SLO par classe](../sre/SLO.md) · [état des lieux de la séance 1](../sre/ETAT-DES-LIEUX.md) · [compte rendu des séances](../sre/SEANCES.md) · [guide technique](../guide/README.md) · [fiches par service](../services/00-index.md).

Les exercices ne sont **pas corrigés** ici : la vérification indique ce qui doit être vrai si vous avez réussi. Les séances 3 à 10 de la campagne SRE (goulots, moteur, quantization, routage, autoscaling, opérations GPU, game days, capacité)
ajouteront leurs propres modules au fil de l'avancement.
