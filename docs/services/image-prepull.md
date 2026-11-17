# Pré-tirage de l'image vLLM (`image-prepull`)

> **Statut : codé, non retesté depuis zéro.** Ajouté après la dernière installation complète ; il n'a jamais tourné sur Azure.

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
Réduit le temps de **cold start** (estimation : jusqu'à ~3 min 35 sur un nœud neuf, à confirmer par une mesure) et le coût associé d'un nœud GPU facturé mais inutile pendant ce temps.

## Limites connues
- Un changement d'image dans le scénario exige de **mettre à jour aussi** `prepull.yaml` (sinon le pré-tirage tire l'ancienne image : le test statique le signale).
- Docker Hub peut limiter les pulls anonymes ; non rencontré.
