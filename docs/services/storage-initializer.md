# storage-initializer et Hugging Face

## Rôle
**Init container** ajouté par KServe à chaque pod vLLM : il **télécharge les poids du modèle** depuis l'URI déclarée (`hf://Qwen/...`) vers `/mnt/models` avant que vLLM ne démarre. Image `kserve/storage-initializer:v0.21.0`.

## Place dans l'architecture
Premier acteur du démarrage d'un pod vLLM. Il s'exécute **avant** le conteneur principal : le pull de l'image vLLM (9 Go) n'a lieu qu'après lui (d'où le pré-tirage proposé, voir [image-prepull](image-prepull.md)).

## Relations
Hugging Face Hub (HTTPS, sortie via le Load Balancer AKS) -> volume `emptyDir kserve-provision-location` -> monté dans le pod vLLM.

## Configuration retenue
- Ressources : requests 256 Mi / 100 m ; limites **6 Gio / 2 CPU** (`kserve.storage.resources`). À 1 Gio il était tué par OOM (code 137) sur le 7B.
- `HF_TOKEN` : le secret `hf-token` existe mais est **vide** : téléchargement anonyme. Les 4 modèles du lab sont publics. Un token est nécessaire pour des modèles à accès restreint (et relève les limites de débit).
- Le modèle est téléchargé **à chaque démarrage de pod** (pas de cache persistant) : disque temporaire du nœud.

## Authentification
Aucune (anonyme). Si un token est fourni, il est transmis à Hugging Face.

## Données traitées
Les **poids du modèle** : 7B AWQ ~5,5 Go, 1,5B FP16 ~3 Go. Aucun prompt.

## Contribution à l'inférence
Détermine le **temps de démarrage** : mesuré **41 s** pour le 7B AWQ depuis la région Azure `eastus` (observé, 41 à 59 s selon les essais). Une panne de Hugging Face empêche tout nouveau réplica de démarrer (scénario de game day prévu).

## Métriques
Pas de métrique propre ; durée visible dans les conditions du pod (`Initialized`), logs `storage.initializer` (`Model downloaded in N seconds`). Mesure automatisée : `tests/coldstart.py`.

## Pannes
`Init:CrashLoopBackOff` code 137 (OOM, corrigé) ; échecs réseau vers Hugging Face (non rencontrés).
