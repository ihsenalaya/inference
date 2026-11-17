# Parcours de lecture pour débutant

**En une phrase.** Cette documentation est grande (plus de quatre-vingts fichiers) ; ce parcours dit **dans quel ordre** la lire pour comprendre ce qu'est un cluster d'inférence, savoir l'optimiser, puis **raconter ce que vous avez appris**, avec le temps à prévoir pour chaque étape.

<!-- mots: inférence, token, gpu, vllm, sli, slo, gpu_util, méthode use -->
> **Mots à connaître**
> - **Inférence** : Faire répondre un modèle déjà entraîné (par opposition à l'entraîner). Ce cluster ne fait que ça.
> - **Token** : Le morceau de texte que le modèle lit et écrit (un mot courant fait environ 1 à 2 tokens). C'est l'unité de tous les calculs.
> - **GPU / VRAM** : Le processeur de calcul (ici un NVIDIA T4) et sa mémoire (16 Go). Le modèle et le cache KV doivent y tenir.
> - **vLLM** : Le programme qui charge le modèle sur le GPU et répond aux requêtes. Le « moteur ».
> - **SLI** : L'indicateur mesuré (par exemple : part de requêtes avec un TTFT ≤ 5 s).
> - **SLO** : Un objectif chiffré de qualité de service, par exemple « 95 % des réponses commencent en moins de 5 s ».
> - **GPU_UTIL** : Part du temps où *au moins un* calcul tournait. **100 % ne veut pas dire saturé** (observé : le même GPU passe de 284 à 933 tokens/s à `GPU_UTIL` constant ou plus bas).
> - **Méthode USE** : Pour chaque ressource, on regarde l'Utilisation (est-elle occupée ?), la Saturation (y a-t-il de la file ?) et les Erreurs.
> - Tous les mots : [glossaire](sre/GLOSSAIRE.md).
<!-- /mots -->

## Les trois questions, et où est la réponse

| Votre question | Réponse courte | Où la lire |
|---|---|---|
| **C'est quoi un cluster d'inférence ?** | Des machines (ici un GPU T4 sous Kubernetes) qui font **répondre** un modèle de langage déjà entraîné à des milliers de requêtes, avec une passerelle (clés, budgets), un routeur, un moteur (vLLM), de la supervision et de l'automatisation. | étapes 0 et 1 |
| **Comment l'optimiser ?** | 1) **mesurer sans se tromper**, 2) trouver le **goulot** (mémoire du GPU, calcul, cache KV, file d'attente), 3) choisir le **levier** qui correspond (quantization, taille de lot, modèle, puissance du GPU, nombre de GPU), 4) **remesurer**. | étapes 2 et 3 |
| **Comment mettre en valeur ce que j'ai appris ?** | Raconter **quatre histoires vraies** (situation, action, résultat chiffré, leçon), chacune appuyée sur une mesure du dépôt, et dire honnêtement ce que le lab ne prouve pas. | étape 5 |

## Les étapes

Les durées sont des **estimations** (calcul : lecture à 250 mots par minute, doublée pour prendre des notes et faire les exercices). Une étape par séance de travail est un bon rythme : **environ 8 heures en tout**, étalées sur plusieurs jours.

### Étape 0 : se repérer (15 minutes)

1. Le [README du dépôt](../README.md) : la phrase d'ouverture et le schéma d'architecture. Ne cherchez pas à tout comprendre.
2. Les **12 premiers mots** du [glossaire](sre/GLOSSAIRE.md). Gardez-le ouvert dans un onglet : chaque document commence aussi par une petite boîte « Mots à connaître ».

*Vous avez réussi si* vous pouvez expliquer à voix haute : « un token », « le GPU et sa VRAM », « vLLM ».

### Étape 1 : comprendre un cluster d'inférence (1 h 30)

1. [Guide 01 - L'inférence expliquée](guide/01-inference-expliquee.md) : comment un modèle répond (tokens, prefill, decode, cache KV, batching, quantization). **C'est le chapitre le plus important du dépôt** : lisez-le lentement.
2. [Guide 02 - Architecture](guide/02-architecture.md) : le chemin d'une requête, de LiteLLM jusqu'au GPU.
3. [Guide 05 - Le GPU T4](guide/05-gpu-t4.md) : ce que le matériel permet et interdit.
4. Facultatif : une [fiche de service](services/00-index.md) quand un nom vous intrigue (vLLM, KServe, Istio...). Ne les lisez pas toutes.

*Vous avez réussi si* vous pouvez dessiner de mémoire le trajet d'une requête (client, passerelle, routeur, moteur, GPU) et dire **ce que chaque pièce apporte**.

### Étape 2 : mesurer sans se tromper (2 heures)

Les modules 1 à 4 de la [formation](formation/README.md), dans l'ordre. Chacun finit par **un exercice** : faites-le avant de lire la suite.

1. [Mesurer sans se tromper](formation/01-mesurer-sans-se-tromper.md) : distinguer un vrai gain du bruit.
2. [Classes de charge et SLI](formation/02-classes-de-charge-et-sli.md) : mesurer ce qui compte pour l'utilisateur.
3. [SLO et budget d'erreur](formation/03-slo-et-budget-derreur.md) : poser un objectif.
4. [Burn rate et alertes](formation/04-burn-rate-et-alertes.md) : être prévenu au bon moment.

*Vous avez réussi si* vous savez répondre à : « mon test est 5 % plus rapide : est-ce un gain ? »

### Étape 3 : lire un GPU et l'optimiser (3 heures)

1. [Formation, module 5 - Lire un GPU](formation/05-lire-un-gpu.md) : pourquoi « 100 % utilisé » ne veut pas dire « saturé ».
2. [Formation, module 7 - Santé et efficacité du GPU](formation/07-sante-et-efficacite-du-gpu.md) : le résumé du dossier GPU.
3. [Dossier GPU, README](gpu/README.md), puis [04 - Diagnostic et optimisation](gpu/04-diagnostic-et-optimisation.md) : les arbres de décision (« que changer ? »).
4. [Résultats de la séance GPU](gpu/07-resultats-seance.md) : **lisez seulement les sections 4, 5 et 6** (decode contre prefill, escalier de charge, limite de puissance). Les autres sont de la référence.
5. Pour plus tard : [01 - Les signaux du GPU](gpu/01-signaux-du-gpu.md) (chaque compteur expliqué) et [02 - KPI](gpu/02-kpi.md).

*Vous avez réussi si* vous pouvez, devant ces trois chiffres (`GPU_UTIL` 100 %, `SM_ACTIVE` 0,45, `DRAM_ACTIVE` 0,10, file vide), dire si le GPU est saturé, et quel levier vous essaieriez ensuite selon le goulot.

### Étape 4 : exploiter, à la demande (au fil des besoins)

À lire **quand le sujet se présente**, pas avant :

- [Guide 04 - Observabilité](guide/04-observabilite.md) : quoi regarder dans Grafana.
- [Guide 06 - Cycle de vie et coûts](guide/06-cycle-de-vie-et-couts.md) et [Formation 06 - Démarrage à froid](formation/06-demarrage-a-froid.md) : combien ça coûte, combien de temps ça démarre.
- [Runbooks](runbooks/) : une fiche par alerte (« que vérifier, que faire »).
- [DECISIONS](DECISIONS.md) : **pourquoi** chaque choix a été fait (très utile en entretien).
- [Compte rendu des séances](sre/SEANCES.md) : l'histoire du projet, avec les heures et les coûts.

### Étape 5 : mettre en valeur vos compétences (1 heure)

1. Lisez [Correspondance avec le référentiel NCP-AIO](gpu/06-competences-ncp-aio.md), **sections 2, 3 et 4** : ce que le travail démontre, **quatre histoires** prêtes à raconter, et ce qu'il ne prouve pas.
2. Choisissez **deux histoires** et préparez chacune en 90 secondes (situation, action, résultat chiffré, leçon). L'exercice de la fin du chapitre sert à cela.
3. Préparez **une page** à montrer : une figure (par exemple [l'escalier de charge](gpu/img/escalier-gpu.svg) ou [la limite de puissance](gpu/img/puissance-horloge-s5.svg)), trois chiffres, une leçon, et le lien vers le dépôt.

**Règles pour rester crédible**

- Parlez de ce que **vous avez fait et mesuré** (« j'ai mesuré 3,06 tokens par joule à saturation contre 1,03 à 0,5 req/s »), pas de ce que l'outil sait faire.
- Dites les limites : un seul GPU, un run par mesure, pas de production, pas de BCM, de Slurm, de MIG ni de NVLink (le chapitre 06 en donne la liste).
- Montrez **une erreur corrigée** : par exemple « l'estimation MBU de vLLM était 7 fois trop basse, je l'ai recoupée avec un calcul » ou « le label `hostname` vide dans les alertes, trouvé grâce à une alerte réelle ». Cela prouve que vous vérifiez au lieu de recopier.
- Le chapitre 06 ne dit **rien** sur votre situation personnelle (certification, poste) : c'est à vous de faire le lien avec votre parcours.

## Comment lire un document du dépôt

1. Lisez **« En une phrase »** et la boîte « Mots à connaître ».
2. Repérez les marques de fiabilité : **(observé)** = vu sur le cluster, **(config)** = écrit dans le dépôt, **(doc)** = documentation officielle, **(calcul)** = déduit, **(non vérifié)** = plausible seulement. Fiez-vous d'abord aux deux premières.
3. Parcourez les titres de section, **sautez** ce qui est tableau de référence au premier passage.
4. Faites l'exercice final **sans regarder la vérification**, puis comparez.

## Ce qui n'est pas dans ce parcours (volontairement)

- Le détail de **Terraform, Argo CD et des fiches de services** : utile pour reproduire le lab, pas pour comprendre l'inférence.
- Les 183 métriques ([METRIQUES](METRIQUES.md)), le [RUNBOOK](RUNBOOK.md) et les [captures brutes](reference/README.md) : à ouvrir pour vérifier un détail.
- Le cluster est **détruit** : vous ne pouvez pas rejouer les mesures sans le redéployer, mais les sorties brutes sont conservées dans `results/session-gpu-2026-11-17/`.
