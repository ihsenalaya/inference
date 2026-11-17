# NVIDIA GPU Operator (driver, toolkit, device plugin, DCGM, NFD)

**En une phrase.** Le GPU Operator installe tout ce qu'il faut pour que Kubernetes voie et utilise le GPU : le pilote (driver), les outils pour les conteneurs, l'annonce « ce nœud a 1 GPU » et les mesures du GPU.

<!-- mots: driver, dcgm, gpu_util, nvidia t4, taint, cold start -->
> **Mots à connaître**
> - **Driver / device plugin** : Pilote du GPU installé sur le nœud / composant qui déclare `nvidia.com/gpu` à Kubernetes.
> - **DCGM** : Outil NVIDIA qui mesure le GPU ; `dcgm-exporter` publie ces mesures pour Prometheus.
> - **GPU_UTIL** : Part du temps où *au moins un* calcul tournait. **100 % ne veut pas dire saturé** (observé : le même GPU passe de 284 à 933 tokens/s à `GPU_UTIL` constant ou plus bas).
> - **NVIDIA T4** : Le GPU du lab : architecture Turing, 16 Go, 70 W maximum, pas de bf16 ni FP8. Peu cher, peu puissant.
> - **Taint / toleration** : « Chasse-pods » posé sur le nœud GPU (`sku=gpu`) / autorisation pour les pods qui doivent y aller.
> - **Cold start** : Délai entre « on demande un GPU / un pod » et « il répond ». Ici : **721 s** pour un nœud GPU, **~3,5 min** pour changer de modèle (observé).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Rend le GPU **utilisable par Kubernetes** : installe le driver NVIDIA sur le nœud, configure le runtime de conteneurs, annonce la ressource `nvidia.com/gpu` au scheduler, expose les métriques GPU et valide l'ensemble.
Version **v26.7.2**, namespace `gpu-operator`. Il est piloté par un objet unique, la **`ClusterPolicy`** `cluster-policy`.

## Pourquoi l'opérateur plutôt que le GPU managé d'AKS
AKS propose deux modes **exclusifs** : (a) driver et device plugin gérés par AKS, (b) pool créé avec `gpu_driver = "None"` et tout géré par le GPU Operator. Le lab utilise **(b)** ; mélanger les deux produit `FailedCreatePodSandBox: no runtime for "nvidia"` et zéro GPU annoncé (doc Microsoft). Le réglage ne s'applique qu'à la **création** du pool.

## Place dans l'architecture
Entre le matériel et vLLM. Un pod ne reçoit un GPU que si le device plugin l'a annoncé ; sans driver, aucun pod vLLM ne démarre (`Pending`).

## Les composants (inventaire réel, `docs/reference/workloads.txt`)

| Composant | Version | Où | Rôle |
|---|---|---|---|
| `gpu-operator` (contrôleur) | v26.7.2 | système | réconcilie la `ClusterPolicy`, déploie les DaemonSets sur les nœuds GPU |
| Node Feature Discovery (master, gc, worker) | v0.19.0 | système + chaque nœud | détecte le matériel (PCI NVIDIA) et pose des labels sur les nœuds |
| `nvidia-driver-daemonset` | **580.95.05** (image `nvcr.io/nvidia/driver:580.95.05-ubuntu22.04`) | nœud GPU | **compile et charge les modules noyau** NVIDIA ; installe le driver |
| `nvidia-container-toolkit-daemonset` | v1.20.1 | nœud GPU | configure containerd pour injecter le GPU dans les conteneurs |
| `nvidia-device-plugin-daemonset` | v0.20.1 | nœud GPU | annonce `nvidia.com/gpu` à kubelet |
| `gpu-feature-discovery` | v0.20.1 | nœud GPU | labels détaillés du GPU (produit, mémoire...) |
| `nvidia-dcgm-exporter` | 4.6.1-4.8.4 (distroless) | nœud GPU | exporte les métriques GPU (port 9400) |
| `nvidia-operator-validator` + `nvidia-cuda-validator` | v26.7.2 | nœud GPU | vérifie driver, toolkit, plugin, puis lance un calcul CUDA de test |
| `nvidia-mig-manager`, `nvidia-device-plugin-mps-control-daemon` | | **0 pod** sur ce nœud | DaemonSets existants mais sans cible : MIG n'existe pas sur T4, MPS non activé |

## Relations
- NFD -> labels -> l'opérateur -> DaemonSets. L'ordre sur un nœud neuf : driver -> toolkit -> device plugin / GFD / DCGM -> validateur.
- Le device plugin parle à **kubelet** (gRPC local) ; kubelet annonce `nvidia.com/gpu: 1` dans `allocatable` (observé via `kubectl get nodes`).
- Le DCGM exporter est scrapé par Prometheus ; avec `enablePodLabels: true` et `honorLabels: true`, les métriques portent les labels du **pod qui utilise le GPU** (observé : `pod`, `namespace`, `container`).

## Configuration retenue (config : `gitops/platform/gpu-operator/values.yaml`)
- `driver.enabled: true`, **`driver.version: "580.95.05"`** : branche de production 580 ; supporte le T4 (Turing) et **CUDA 13.0**, requis par l'image vLLM (driver >= 580).
- **`driver.kernelModuleType: proprietary`** : les modules **ouverts** (`kernel-open`) ne compilent pas sur le noyau d'AKS Ubuntu 22.04 (`5.15.0-1126-azure`) : `error: too few arguments to function 'pci_resize_resource'` (observé). Les modules propriétaires, supportés sur T4, fonctionnent.
- `toolkit.enabled: true`, `operator.defaultRuntime: containerd`, tolérations du taint `sku=gpu:NoSchedule` sur tous les DaemonSets et le worker NFD.
- DCGM : `serviceMonitor` à 15 s avec **`honorLabels: true`** ; liste de métriques personnalisée dans une ConfigMap `dcgm-metrics` (champs d'utilisation, mémoire, puissance, énergie, température, XID, throttling, ECC, PCIe, profilage `GR_ENGINE_ACTIVE`, `SM_ACTIVE`, `SM_OCCUPANCY`, `PIPE_TENSOR_ACTIVE`, `PIPE_FP16_ACTIVE`, `DRAM_ACTIVE`).
- Wave Argo CD **1** pour que le driver compile pendant l'installation du reste. **Prouvé le 17/11** (installation de zéro) : le driver démarre **317 s** après la création du nœud au lieu de 590 s ([module 6](../formation/06-demarrage-a-froid.md)).

## Authentification et privilèges
ServiceAccounts par composant. Le conteneur du driver et le toolkit ont un accès **privilégié à l'hôte** (compilation et chargement de modules noyau, modification de la configuration de containerd) : composants de confiance maximale (doc).
Les images viennent de `nvcr.io` en pull anonyme.

## Données traitées
Aucune donnée d'inférence. Il manipule du matériel et expose des **métriques de télémétrie GPU**.

## Contribution à l'inférence
Sans lui, pas de GPU. Mesuré : sur un nœud neuf, **installation du driver 3 min 11 à 3 min 41** (191 s le 16/11, 221 s le 17/11 : compilation des modules noyau), puis GPU annoncé. Attente avant le démarrage du driver : 590 s le 16/11 (derrière d'autres composants Argo CD), **317 s** le 17/11 (après passage en vague 1). Nœud GPU créé -> GPU annoncé : 804 s puis 564 s.

## Métriques à suivre
`DCGM_FI_DEV_GPU_UTIL`, `_FB_USED`, `_FB_FREE`, `_POWER_USAGE`, `_GPU_TEMP`, `_TOTAL_ENERGY_CONSUMPTION`, `_CLOCK_THROTTLE_REASONS`, `_XID_ERRORS`, `DCGM_FI_PROF_GR_ENGINE_ACTIVE`, `_DRAM_ACTIVE`, `_PCIE_*`. Détails : [guide GPU](../guide/05-gpu-t4.md).
**Mise à jour (17/11)** : les compteurs `DCGM_FI_PROF_SM_ACTIVE`, `SM_OCCUPANCY`, `PIPE_TENSOR_ACTIVE` et `PIPE_FP16_ACTIVE` **sont exportés** sur le T4 quand l'exporteur démarre avec la liste actuelle du ConfigMap `dcgm-metrics` (observé en charge : `SM_ACTIVE` 0,91, `PIPE_TENSOR_ACTIVE` 0,11 sur le 1,5B ; 0,28 à 0,32 sur le 7B AWQ).
Une première observation avait conclu qu'ils n'étaient pas exposés : cause probable (non vérifiable, ce cluster est détruit) = exporteur resté sur l'ancienne liste ; la documentation du GPU Operator précise que l'opérateur ne surveille pas ce ConfigMap, un changement exige de **redémarrer le DaemonSet de l'exporteur**. Lecture des valeurs : [module 5](../formation/05-lire-un-gpu.md).

## Pannes et diagnostic
| Symptôme | Cause / réponse |
|---|---|
| `nvidia.com/gpu` absent des `allocatable` | driver en cours de compilation ; `kubectl -n gpu-operator logs <nvidia-driver-daemonset>` |
| Driver en `Error` : `make: *** modules` | modules ouverts sur un noyau incompatible : `kernelModuleType: proprietary` |
| `FailedCreatePodSandBox: no runtime for "nvidia"` | mélange des modes GPU AKS / opérateur |
| Nœud cordonné quelques minutes pendant l'installation | comportement du gestionnaire de driver (observé) |
| Nouveau noyau après mise à jour de l'image de nœud | le driver doit être recompilé (~3 min) |
