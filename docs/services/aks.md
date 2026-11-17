# AKS et ressources Azure

## Rôle
Azure Kubernetes Service fournit le **plan de contrôle Kubernetes managé** (API server, etcd, scheduler, controller-manager) et les nœuds (VM Azure en VMSS).
Le lab utilise le tier **Free** : pas de SLA sur le plan de contrôle, ce qui suffit pour un lab (config `sku_tier = "Free"`).

## Place dans l'architecture
Socle de tout le reste. Tout ce qui est décrit dans les autres fiches tourne sur deux **pools de nœuds** (`infra/terraform/main.tf`) :

| Pool | VM | Nombre | Rôle | Label / taint |
|---|---|---|---|---|
| `system` | `Standard_D4as_v7` (4 vCPU, 16 Gio, AMD) | 1 | plateforme, observabilité, passerelles, bancs de charge | `workload=platform` |
| `gpu` | `Standard_NC4as_T4_v3` (4 vCPU, 28 Gio, 1 T4) | 0 à 2 (défaut 1) | uniquement vLLM + DaemonSets GPU | `workload=inference`, taint `sku=gpu:NoSchedule` |

Mesures : nœud système, 3 860 m CPU et ~12 Gio allouables ; à l'état stable, 75 % des requests CPU et 51 % des requests mémoire utilisés (limites mémoire en sur-allocation).

## Configuration retenue (config)
- Version Kubernetes **1.34**, Ubuntu 22.04 (noyau 5.15.0-1126-azure observé). Pas de mise à jour automatique du cluster ni de l'OS des nœuds : une nouvelle image de nœud change le noyau et relance la compilation du driver GPU.
- Réseau : **Azure CNI Overlay** (pods en `10.244.x.x`, nœuds en `10.224.x.x`, observé), Standard Load Balancer pour la sortie des nœuds. Aucun Service exposé.
- Identité : **identité managée système** ; OIDC issuer et workload identity activés mais **non utilisés** par les services du lab.
- Pool GPU : `gpu_driver = "None"` (le driver est installé par le GPU Operator, pas par AKS), disque OS **éphémère** de 128 Gio sur le disque temporaire (gratuit), `max_unavailable = 1` (pas de surge possible : le quota de 8 vCPU T4 = 2 nœuds).
- Aucun add-on Azure Monitor, Defender, Policy, KAITO, Istio managé.
- `node_provisioning_profile` en mode `Manual` (obligatoire avec le provider `azurerm` 5) : pas de Node Auto Provisioning.

## Composants AKS visibles dans `kube-system` (observé)
`azure-cns` (réseau des pods), `azure-ip-masq-agent`, `cloud-node-manager`, `csi-azuredisk-node` et `csi-azurefile-node` (volumes), `kube-proxy`, `metrics-server` (permet `kubectl top`).
Classes de stockage : `managed-csi` (disques Azure, utilisée par Prometheus et Loki), `default`, `azurefile*`.

## Authentification
- Vous -> API : `az aks get-credentials` (certificat client admin, comptes locaux activés). `MY_IP_CIDR` restreint l'API server par IP (non activé par défaut).
- Cluster -> Azure : identité managée système.

## Données traitées
Aucune donnée d'application : AKS ne voit que des objets Kubernetes. Les volumes persistants (PVC) sont des disques managés dans le groupe de ressources `inflab-aks-nodes`.

## Contribution à l'inférence
Fournit le calcul : le **T4** (via la VM `NC4as_T4_v3`) et le CPU. Contraintes qu'il impose :
- quota de **8 vCPU** de famille NCASv3_T4 en `eastus` seulement (2 nœuds T4 maximum) ; quota Spot de 3 vCPU : pas de T4 Spot ;
- risque d'`AllocationFailed` au démarrage malgré le quota (signalé par la communauté en 2026 ; non rencontré ici).

## Métriques à suivre
`kube_node_status_allocatable`, `kube_node_status_capacity{resource="nvidia_com_gpu"}`, `node_*` (node-exporter), `container_*` (cAdvisor), `kube_pod_status_phase`. Alerte coût : `LabGPUIdleCost`.

## Pannes et diagnostic
| Symptôme | Cause connue |
|---|---|
| `terraform apply` : `maxSurge and maxUnavailable cannot both be 0` | paramètre `upgrade_settings` du pool GPU (corrigé : `max_unavailable = "1"`) |
| `down` : `ResourceGroupDeletionBlocked` | mise à jour de plateforme du VMSS en cours ; réessayer |
| nœuds recréés après `stop`/`start` | comportement observé : nouveaux noms `vmss00000N`, donc driver et image à refaire |
