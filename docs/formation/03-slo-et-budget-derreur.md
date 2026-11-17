# Module 3 - Poser un SLO et lire le budget d'erreur : de la baseline aux objectifs

**Objectif** : savoir proposer un SLO défendable **à partir de mesures**, convertir un objectif en budget (requêtes et minutes), et dire ce que ce budget
autorise réellement sur un cluster à un seul GPU. Marques de fiabilité : voir [le guide](../guide/README.md). Les SLO complets sont dans [docs/sre/SLO.md](../sre/SLO.md).

## 1. Le concept en dix lignes

1. Un **SLO** est un objectif sur un SLI, sur une fenêtre : « 95 % des requêtes ont un TTFT <= 5 s, sur 30 jours glissants ».
2. Le **budget d'erreur** est ce que l'objectif tolère : 5 % de requêtes lentes. On le **dépense** (déploiements, pannes, surcharges) ; plus de budget = on gèle les changements risqués.
3. On ne pose pas un SLO au hasard : on part de ce que la configuration **sait faire** (la baseline mesurée) et de ce que l'utilisateur **supporte**. Trop strict, l'alerte
   sonne en permanence ; trop lâche, elle ne sonne jamais.
4. Un SLO se vérifie : on l'applique aux runs de classe (module 2) et on regarde si la part de requêtes bonnes dépasse l'objectif.

## 2. Les SLO proposés (config : `slo.classes`, `gitops/observability/config/values.yaml`)

| Classe | Disponibilité | TTFT | Durée de bout en bout | Justification (mesures du lab) |
|---|---|---|---|---|
| Interactive | **99 %** | **95 % <= 5 s** | 95 % <= 30 s | TTFT p95 mesuré : 0,20 s (1,5B, 2 req/s), 0,57 s (7B, 1 req/s) ; le 7B à 1 req/s sur un profil plus lourd avait un p95 de 1,65 à 2,86 s (3 répétitions) : 5 s laisse une marge de ~2x sur le pire cas observé |
| RAG | 99 % | **95 % <= 10 s** | 95 % <= 30 s | TTFT p50 3,1 s / p95 8,8 s sur le 1,5B à 0,5 req/s : le seuil de 10 s est volontairement proche de ce que le matériel sait faire |
| Multi-tour | 99 % | 95 % <= 5 s | 95 % <= 30 s | TTFT p95 0,81 s (1,5B, 0,5 req/s, cache de préfixes à 82 %) |
| Lot | 99 % | (aucun) | **95 % <= 300 s** | personne n'attend : on borne la durée pour détecter une file qui ne se vide plus ; le 1,5B saturé tient avec un p95 de 146 s |
| Embeddings | -- | -- | -- | **pas de SLO : classe non déployée** |

Ces valeurs sont des **propositions** fondées sur la baseline, à valider. Elles ne sont **pas** des engagements de service.
Contrainte technique : les seuils de latence doivent être des **seaux** des histogrammes LiteLLM (1, 2, 5, 10, 30, 60, 120, 300 s... : module 4).

## 3. Du pourcentage au budget (calcul)

Fenêtre de 30 jours = 720 h = 43 200 min.

| Objectif | Budget | Équivalent en indisponibilité totale (30 j) | Au débit de 2 req/s (5,18 M requêtes en 30 j) |
|---|---|---|---|
| 99 % | 1 % | **7,2 h** | 51 840 requêtes en échec tolérées |
| 95 % | 5 % | 36 h | 259 200 requêtes trop lentes tolérées |
| 99,9 % | 0,1 % | **43,2 min** | 5 184 requêtes |
| 99,99 % | 0,01 % | **4,3 min** | 518 requêtes |

## 4. Ce que ce budget autorise sur un seul GPU (observé + calcul)

Le lab n'a **qu'un réplica** sur **un nœud GPU** : toute panne est une indisponibilité totale. Durées mesurées sur ce cluster :

| Événement | Durée mesurée | Part du budget 99,9 % (43,2 min) | Part du budget 99 % (7,2 h) |
|---|---|---|---|
| Remplacement du modèle servi (changement de scénario, image déjà en cache) | **3 min 34 s** (11:09:51 -> 11:13:25) | 8,3 % | 0,8 % |
| Nœud GPU perdu et recréé : nœud créé -> vLLM Ready | **721 s (12 min 1 s)** | **27,8 %** | 2,8 % |
| Démarrage complet du cluster | 18 min 55 s | 43,8 % | 4,4 % |

Conclusion (calcul) : à 99,9 %, **quatre pertes de nœud par mois** (4 x 12 min) épuisent le budget ; à 99,99 % (4,3 min), **une seule** panne le dépasse. Sans réplica de secours, **99 % est le plus haut objectif
de disponibilité défendable** pour ce lab. C'est pourquoi la disponibilité est à 99 % et non à 99,9 %. Un deuxième réplica (autre GPU) ne supprimerait pas la panne mais la rendrait **partielle**.

## 5. Ce que les SLO ont dit sur la configuration (observé)

- Le **RAG sur le 1,5B** ne respecte pas son SLO à 0,5 req/s (91,3 % de requêtes bonnes pour 95 % demandés) ; voir les mesures du 7B dans [SLO.md](../sre/SLO.md).
- Le **lot** respecte son SLO tout en ayant une latence de 40 s au premier token : un SLO unique l'aurait fait passer pour en panne.
- Le **multi-tour** est limité par `max-model-len` (4 096 tokens) : le SLO de disponibilité ne compte pas les 400 de contexte dépassé (faute du client), mais l'application doit tronquer l'historique.

## 6. À retenir

1. Un objectif se pose à partir d'une **mesure** et d'un **besoin**, puis se **vérifie** sur la charge de chaque classe.
2. Convertissez toujours l'objectif en minutes et en requêtes : c'est ce qui révèle qu'un 99,9 % est inatteignable avec un GPU sans secours (un nœud perdu = 12 min).
3. Un SLO qui n'est jamais violé est trop lâche ; un SLO violé en permanence est trop strict. Les deux sont des échecs de conception.

## 7. Exercice (à faire vous-même)

Objectif : choisir l'objectif de disponibilité d'une **nouvelle** classe « support client » (chat interactif 24 h / 24) **avec 2 réplicas sur 2 GPU**.
1. Combien de minutes d'indisponibilité totale par mois votre objectif tolère-t-il ?
2. Une perte de nœud affecte la moitié de la capacité pendant ~12 min : à quel objectif cela mène-t-il, et que devient la latence des requêtes restantes ?
3. Quelle protection (file côté EPP, limites de concurrence, flow control) faut-il pour que la latence reste dans le SLO pendant la panne ?
Vérification : justifiez votre chiffre avec les durées du tableau du §4, pas avec une valeur « standard ».
