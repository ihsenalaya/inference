# Pré-tirage de l'image vLLM (`image-prepull`)

**En une phrase.** Ce petit programme télécharge à l'avance l'image de vLLM (~9 Go) sur le nœud GPU, pour que le modèle démarre sans attendre ce téléchargement.

<!-- mots: cold start, pod, taint, daemonset, digest d'image -->
> **Mots à connaître**
> - **Cold start** : Délai entre « on demande un GPU / un pod » et « il répond ». Ici : **721 s** pour un nœud GPU, **~3,5 min** pour changer de modèle (observé).
> - **Pod** : La plus petite unité qui tourne : un ou plusieurs conteneurs. Un pod vLLM = un modèle sur un GPU.
> - **Taint / toleration** : « Chasse-pods » posé sur le nœud GPU (`sku=gpu`) / autorisation pour les pods qui doivent y aller.
> - **Deployment / DaemonSet / Job** : Programme à N copies / une copie par nœud / tâche qui se termine (un bench).
> - **Digest d'image** : Empreinte exacte d'une image de conteneur : on « épingle » la version au lieu d'un tag qui peut changer.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

> **Statut : prouvé le 17/11** sur une installation de zéro : le pull de l'image vLLM a pris **1 s** au démarrage du pod (215 s sans pré-tirage, mesure du 16/11). Détail et réserves : [module 6](../formation/06-demarrage-a-froid.md).

## Rôle
Tirer l'image vLLM (~9 Go) sur le nœud GPU **dès qu'il existe**, en parallèle de l'installation du driver NVIDIA, pour ne plus attendre ce pull au premier démarrage du modèle.

## Pourquoi
Mesuré à froid : image vLLM tirée **après** le téléchargement du modèle (le conteneur principal ne démarre qu'après l'init container) : 215 s (3 min 35). Le driver, lui, met ~3 min à compiler : les deux peuvent se chevaucher.

## Place dans l'architecture
DaemonSet `image-prepull` (`gitops/platform/image-prepull/prepull.yaml`, application Argo CD en vague 1, `azure` seulement), namespace `inference`, `nodeSelector workload=inference` et toleration du taint GPU.
Un **init container** utilise l'image vLLM (commande `exit 0`) : kubelet la tire, puis le conteneur principal est un `pause` de quelques Ko qui occupe le pod.

## Configuration
Image identique à `vllm.image` de `gitops/serving/chart/values.yaml` (même digest) : `tests/static.sh` vérifie l'égalité des deux références. Ressources : 1 m CPU, 4 Mi.

## Authentification / données
Pull anonyme depuis Docker Hub. Aucune donnée.

## Contribution à l'inférence
Réduit le temps de **cold start** : **-214 s mesurés** (215 s -> 1 s) sur un nœud neuf, et le coût associé d'un nœud GPU facturé mais inutile pendant ce temps (~0,03 $ par démarrage, calcul).

## Limites connues
- Un changement d'image dans le scénario exige de **mettre à jour aussi** `prepull.yaml` (sinon le pré-tirage tire l'ancienne image : le test statique le signale).
- Docker Hub peut limiter les pulls anonymes ; non rencontré.
