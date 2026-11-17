# Terraform

**En une phrase.** Terraform est la « recette » écrite des ressources Azure : `apply` crée tout, `destroy` supprime tout. Après lui, plus aucune action manuelle n'est nécessaire.

<!-- mots: terraform, aks, helm, secret, gitops -->
> **Mots à connaître**
> - **Terraform** : Décrit l'infrastructure Azure (AKS, pools, secrets) dans des fichiers et la crée ou la détruit : `apply` / `destroy`.
> - **AKS** : Kubernetes managé par Azure : Azure gère le « cerveau », vous payez les machines.
> - **Helm / chart** : Gabarit de manifestes Kubernetes avec des valeurs ; un *chart* = un paquet.
> - **ConfigMap / Secret** : Configuration / données sensibles (mots de passe, clés) injectées dans les pods.
> - **GitOps** : L'état voulu du cluster est écrit dans Git ; Argo CD le fait appliquer. On ne modifie pas le cluster à la main.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Crée l'**infrastructure Azure** et **amorce** le GitOps : après `terraform apply`, plus rien n'est fait à la main (`infra/terraform/`).

## Ce qu'il crée (dans cet ordre)
1. Groupe de ressources `inflab-rg` (+ budget de coût).
2. Cluster AKS `inflab-aks` (pool `system`) puis pool `gpu`.
3. Dans le cluster (providers `kubernetes` et `helm`, authentifiés par le certificat admin du cluster) : namespaces `gateway`, `monitoring`, `inference` ; **secrets** (LiteLLM, Grafana, webhook d'alerte, `hf-token`) ; **Argo CD** (chart `argo-cd` 10.18.0) ; **application racine** (chart local `gitops/bootstrap/root-app`).

## Configuration retenue
- Providers : `azurerm` 5.14, `helm` 3.3, `kubernetes` 3.5, `random` 3.9 (`versions.tf`).
- Variables clés (`variables.tf`) : `location=eastus`, `gpu_node_count` (0 à 2, défaut 1), `system_vm_size=Standard_D4as_v7`, `kubernetes_version=1.34`, `budget_amount=40`.
- `gpu_node_count` est aussi transmis à Argo CD (`gpuNodes`) : le chart de serving limite les réplicas au nombre de nœuds GPU.
- Durées observées le 17/11 : `apply` complet 530 s (cluster AKS 4 min 8, budget Azure 7 s), relance sans changement 51 s, `destroy` 11 min 38 s.
- Les secrets sont générés par `random_password` ; **l'état est local** (`terraform.tfstate`, ignoré par Git) et contient ces secrets en clair.

## Authentification
Votre session `az login`. Le provider ne contient aucun secret.

## Contribution à l'inférence
Indirecte mais décisive : la taille du pool GPU, le taint, les labels et le disque éphémère de 128 Gio conditionnent où vLLM peut tourner et la vitesse de pull des images de 9 Go.

## Points d'attention (observés)
- `lab.sh down` demande une confirmation interactive sauf avec `--yes`.
- `lab.sh up` appelle Terraform ; `lab.sh down` retire d'abord les objets Helm/Kubernetes de l'état (finalisateurs Argo CD) puis détruit l'infrastructure, avec réessais.
- `az` sous WSL est la version Windows : `az aks get-credentials --file` ne peut pas écrire dans `/tmp` ; le script récupère le kubeconfig sur stdout.
- Pas de backend distant : si le fichier d'état est perdu alors que le cluster existe, il faut `terraform import` ou détruire à la main.
