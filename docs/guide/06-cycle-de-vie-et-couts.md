# 06 - Cycle de vie et coûts

Comment on **allume**, **met en pause** et **détruit** le lab, combien de temps ça prend, et ce que ça coûte. Règle d'or : un GPU alloué coûte pareil qu'il serve ou non, donc on le laisse allumé le moins possible.

<!-- mots: cold start, terraform, aks, pool de nœuds, pvc, vmss, gitops -->
> **Mots à connaître**
> - **Cold start** : Délai entre « on demande un GPU / un pod » et « il répond ». Ici : **721 s** pour un nœud GPU, **~3,5 min** pour changer de modèle (observé).
> - **Terraform** : Décrit l'infrastructure Azure (AKS, pools, secrets) dans des fichiers et la crée ou la détruit : `apply` / `destroy`.
> - **AKS** : Kubernetes managé par Azure : Azure gère le « cerveau », vous payez les machines.
> - **Nœud / pool de nœuds** : Une machine (VM) du cluster / un groupe de machines identiques. Le lab a un pool « système » et un pool « GPU ».
> - **PVC / disque persistant** : Demande de stockage qui survit au redémarrage d'un pod (disque managé Azure). Prometheus, Loki et PostgreSQL en ont un.
> - **VMSS** : Groupe de machines virtuelles identiques d'Azure qui se trouve derrière un pool de nœuds.
> - **GitOps** : L'état voulu du cluster est écrit dans Git ; Argo CD le fait appliquer. On ne modifie pas le cluster à la main.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## 1. Les commandes (`lab.sh`)

| Commande | Effet | Durée mesurée |
|---|---|---|
| `preflight` | outils, session `az`, quota T4, SKU, providers | ~3 min (appels `az` lents sous WSL) |
| `up` | `terraform apply` + attente Argo CD + attente des pods + `smoke` | **28 min 46 s** (16/11, modèle 7B) ; **≈ 19 min** (17/11, modèle 1,5B, après les deux améliorations du §2, reconstitué depuis les horodatages) |
| `smoke` | chaîne complète sans charge (chat T=0, T=0,7, streaming, Prometheus) | ~30 s |
| `bench <profil>` | job `inference-perf` sur le pool système, résultats dans `results/` | selon le profil |
| `scenario <nom>` | commit + push du scénario actif, Argo CD synchronise | **3 min 34 s** pour passer du 1,5B au 7B (observé le 17/11, image vLLM déjà en cache sur le nœud) |
| `gpu-scale 0/1/2` | `terraform apply` sur le nombre de nœuds GPU | ajout d'un nœud : 1 min 49 ; driver ~3 min |
| `stop` | `az aks stop` : les VM sont désallouées | 2 min 46 |
| `start` | `az aks start` puis attente réelle des pods | 5 min 13 pour AKS, ~12 min pour les pods |
| `down --yes` | `terraform destroy` (et suppression des groupes de ressources). **Sans `--yes`, la commande attend une confirmation interactive** | ~8 min (16/11, avec réessais, voir §4) ; **11 min 38 s** (17/11) |
| `idle [--stop-after M]` | durée d'inactivité du GPU ; arrêt optionnel (non testé sur cluster) | |
| `snapshot-metrics [h]` | exporte l'historique `lab:*` dans `results/` (non testé sur cluster) | |

## 2. Le démarrage à froid, décomposé (mesuré)

Installation depuis zéro, 1 nœud T4, modèle 7B AWQ (`tests/coldstart.py`, détail dans `BASELINE.md` §3) :

| Étape | Durée |
|---|---|
| `terraform apply` (RG, AKS 5 min, pool GPU 1 min 54, Argo CD) | 575 s |
| Argo CD installe tout (jusqu'à tout Synced) | ~10 min 30 |
| Nœud GPU créé -> installation du driver **démarrée** | 590 s (attente derrière d'autres composants) |
| Installation du driver (compilation des modules noyau) | 191 s |
| Modèle téléchargé par `storage-initializer` | 41 s |
| Image vLLM (~9 Go) tirée | 215 s (après le téléchargement du modèle) |
| vLLM : chargement des poids 21,7 s ; `torch.compile` 19,8 s ; graphes CUDA ~28 s ; initialisation du moteur 72,8 s | 154 s |
| **Nœud GPU créé -> vLLM prêt** | **1 228 s (20,5 min)** |

**Mise à jour (17/11, installation de zéro, 1,5B)** : deux améliorations sont maintenant **prouvées** : le GPU Operator en vague 1 (le driver compile en parallèle de cert-manager et Prometheus : démarrage du driver à 317 s au lieu de 590 s) et un DaemonSet qui pré-tire l'image vLLM dès que le nœud existe (pull de 1 s au lieu de 215 s).
Nœud GPU créé -> vLLM prêt : **721 s au lieu de 1 228 s**. Le modèle n'étant pas le même (1,5B contre 7B), seuls -273 s et -214 s sont attribuables aux changements. Décomposition complète et réserves : [module 6 de la formation](../formation/06-demarrage-a-froid.md).

## 3. Ce qui arrive aux données selon l'action

| Action | Disques (Prometheus, Loki, PostgreSQL) | Nœuds | Facturation |
|---|---|---|---|
| `stop` | conservés | **recréés au `start`** (observé : nouveaux noms de VMSS) donc nouveau driver, nouvelle image | calcul à 0 ; disques et IP restent (quelques centimes) |
| `gpu-scale 0` | conservés | pool GPU vide | T4 à 0 |
| `down` | **supprimés** | supprimés | tout à 0 |

## 4. Particularités de la destruction

- Les objets Helm/Kubernetes sont retirés de l'état Terraform avant le `destroy` : leur désinstallation (finalisateurs Argo CD) dépassait 5 minutes.
- Azure refuse parfois de supprimer le groupe de nœuds pendant une **mise à jour de plateforme** du VMSS (`ResourceGroupDeletionBlocked`, observé) : réessayer suffit ; `lab.sh down` réessaie jusqu'à 4 fois.
- Vérification de fin : `az group exists -n inflab-rg` et `-n inflab-aks-nodes` doivent répondre `false`.

## 5. Les coûts (eastus, Linux, pay-as-you-go, Azure Retail Prices du 16/11/2026)

| Poste | Prix |
|---|---|
| `Standard_NC4as_T4_v3` | 0,526 $/h |
| `Standard_D4as_v7` | 0,182 $/h |
| AKS tier Free, disque OS T4 éphémère | ~0 |
| 1 T4 + système | **0,708 $/h (≈ 17 $/jour)** |
| 2 T4 + système | 1,234 $/h (≈ 29,6 $/jour) |
| Disques managés (3 PVC), IP publique, trafic | quelques centimes par jour |

Coût réel de la séance du 17/11 (cluster actif de 08:38 à 12:36, **calcul** : 4 h x 0,708 $/h) : **≈ 2,8 $**.

Coût d'usage mesuré : à 1 req/s sur le 7B AWQ, ≈ 1,0 $ par million de tokens de sortie ; à 3 req/s sur le 1,5B, ≈ 0,34 $ (GPU seul, `BASELINE.md` §5). Le prix par token dépend **surtout de l'utilisation** : un GPU à 20 % coûte 5 fois plus cher par token.

### Garde-fous
- Budget Azure du groupe de ressources (`azurerm_consumption_budget_resource_group`, 40 $/mois par défaut, alertes 50/80/100 % et prévision à 100 % envoyées aux propriétaires) : **prévient, n'arrête rien**. **Création testée le 17/11** (7 s, aucun refus de l'abonnement) ; l'envoi des e-mails n'a pas été observé.
- `lab.sh idle --stop-after N` : arrête le cluster si le GPU est inactif depuis N minutes ; à lancer à la main ou par cron (aucun arrêt automatique caché). **Non testé sur cluster.**
- Alerte `LabGPUIdleCost` : inactif depuis 30 minutes.
