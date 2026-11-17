# 03 - Identités et sécurité

Ce lab est un **lab d'apprentissage**, pas une production : plusieurs choix ci-dessous sont volontairement simples (HTTP en clair dans le cluster, accès anonyme à Hugging Face).
Cette page dit **qui s'authentifie auprès de qui**, ce qui protège quoi, et ce qui ne protège **pas**.

## 1. Matrice « qui parle à qui, avec quelle identité »

| De | Vers | Mécanisme | Secret / identité | Preuve |
|---|---|---|---|---|
| Vous (poste) | Azure (Terraform, `az`) | session `az login` (Entra ID) | votre compte | (config) provider `azurerm`, `subscription_id` |
| Terraform | API Kubernetes d'AKS | **certificat client** de l'admin du cluster (`kube_config`) | issu de la ressource AKS, jamais écrit dans Git | (config) `infra/terraform/bootstrap.tf` |
| AKS (plan de contrôle) | Azure (disques, LB, VMSS) | **identité managée système** | gérée par Azure | (config) `identity { type = "SystemAssigned" }` |
| Argo CD | GitHub | HTTPS **anonyme** (dépôt public) | aucune | (observé) aucun secret `argocd.argoproj.io/secret-type=repository` |
| Argo CD | API Kubernetes | ServiceAccount `argocd-application-controller` | jeton projeté | (observé) |
| Vous | Argo CD (UI) | `admin` + mot de passe initial | secret `argocd-initial-admin-secret` | (observé, `lab.sh ui`) |
| Vous | Grafana | `admin` + mot de passe généré | secret `grafana-admin` (créé par Terraform) | (config) |
| Client | LiteLLM | **clé virtuelle** `Authorization: Bearer sk-...` | `lab-bench` ou `lab-user` (secret `litellm-keys`) | (observé) |
| Admin LiteLLM | LiteLLM (API d'administration) | **master key** | `LITELLM_MASTER_KEY` (secret `litellm-secrets`) | (observé : noms des clés du secret) |
| LiteLLM | PostgreSQL | utilisateur `litellm` + mot de passe | `DATABASE_URL`, `POSTGRES_PASSWORD` | (observé) |
| LiteLLM | Gateway Istio | **aucune** (`api_key: none`) | - | (config) `configmap.yaml` |
| Gateway Istio (Envoy) | EPP | TLS auto-signé, certificat **non vérifié** | - | (config) `DestinationRule ... insecureSkipVerify: true` |
| Gateway Istio | pod vLLM | **aucune**, HTTP | - | (observé) |
| Prometheus | cibles de scrape | HTTP anonyme, sauf EPP et KServe : **jeton de ServiceAccount** | ClusterRole `kps-prometheus` (`/metrics` en `get`) | (observé) 401 sans jeton sur l'EPP |
| Prometheus | API Kubernetes (découverte) | ServiceAccount `kps-prometheus` | ClusterRole : nodes, services, endpoints, pods, endpointslices, ingresses (lecture) | (observé) |
| KEDA | Prometheus | **aucune** (URL interne `http://kps-prometheus.monitoring.svc:9090`) | - | (config) trigger du `ScaledObject` |
| KServe (`llmisvc-controller-manager`) | API Kubernetes | ServiceAccount + ClusterRole `kserve-llmisvc-manager-role` | - | (observé) |
| EPP | API Kubernetes | ServiceAccount `<nom>-epp-sa` | Role : lecture des pods, InferencePool, EndpointSlices ; écriture des leases et des événements | (observé) |
| Alloy | API Kubernetes | ServiceAccount `alloy` + ClusterRole `alloy` | lecture des pods, de leurs logs, des événements, **des secrets et configmaps** | (observé) |
| `storage-initializer` | Hugging Face | HTTPS **anonyme** | secret `hf-token` **vide** | (observé) |
| Alertmanager | récepteur d'alertes | URL dans un secret monté (`url_file`) | secret `alert-webhook` | (config) |
| Nœuds AKS | registres d'images (MCR, Docker Hub, ghcr.io, nvcr.io, quay.io) | HTTPS anonyme | - | (observé) images tirées sans secret |

## 2. Les secrets : qui les crée, où ils vivent

| Secret | Créé par | Namespace | Contenu |
|---|---|---|---|
| `litellm-secrets` | Terraform (`random_password`) | `gateway` | `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URL` |
| `litellm-keys` | hook Argo CD PostSync (job `litellm-bootstrap-keys`) | `gateway` | clés virtuelles `lab-bench`, `lab-user` |
| `grafana-admin` | Terraform | `monitoring` | `admin-user`, `admin-password` |
| `alert-webhook` | Terraform | `monitoring` | `url` du récepteur (défaut : `alert-sink` interne) |
| `hf-token` | Terraform | `inference` | `HF_TOKEN` (**vide** par défaut) |
| `argocd-initial-admin-secret` | chart Argo CD | `argocd` | mot de passe initial de `admin` |
| certificats KServe | cert-manager (`selfsigned-issuer`, `Certificate llmisvc-serving-cert`) | `kserve` | certificat TLS du webhook du contrôleur |

Le mot de passe maître et la `LITELLM_SALT_KEY` : la doc de LiteLLM précise que la salt key chiffre les secrets stockés en base et **ne doit plus changer** une fois posée (doc).

**Où sont les secrets en clair ?** Dans l'**état Terraform local** (`infra/terraform/terraform.tfstate`, ignoré par Git) : c'est pourquoi gitleaks le signale quand on scanne le disque.
Terraform n'a pas de backend distant dans ce lab. Dans le cluster, ce sont des `Secret` Kubernetes classiques (base64 ; chiffrement au repos de l'etcd par la plateforme AKS, doc).

## 3. Ce qui protège ... et ce qui ne protège pas

| Protection | État |
|---|---|
| Aucun Service exposé à Internet (tout en `ClusterIP`) | **oui** (observé) |
| Accès à l'API Kubernetes restreint par IP | **optionnel** : `MY_IP_CIDR` -> `api_server_access_profile` (config) ; **non activé** par défaut |
| Authentification des clients de l'inférence | **oui, au niveau de LiteLLM** (clés virtuelles, budgets, quotas rpm/tpm) |
| Authentification entre LiteLLM -> Gateway -> vLLM | **non** : n'importe quel pod du cluster qui connaît l'URL de la Gateway peut appeler les modèles sans clé |
| Chiffrement du trafic interne (mTLS) | **non** : pas de `PeerAuthentication` ni de `AuthorizationPolicy` (observé), pas de sidecar Istio. Seul le lien Envoy -> EPP est en TLS, sans vérification |
| NetworkPolicies | **uniquement celles d'Argo CD** (livrées par sa chart) : aucune sur `inference`, `gateway`, `monitoring` (observé) |
| Alloy peut lire **tous les secrets du cluster** | c'est le `ClusterRole` livré par la chart (observé : `configmaps`, `secrets` en `get/list/watch`). À restreindre en production |
| Hugging Face anonyme | limites de débit, pas de modèles privés ; `hf-token` est prévu mais vide |
| Secrets dans Git | **aucun** dans l'arbre ; **2 clés virtuelles LiteLLM d'anciens clusters détruits** restent dans l'historique (invalides) - voir `BASELINE.md` critère 12 |
| Supply chain : images épinglées | LiteLLM et vLLM **par digest** ; les autres par tag. Raison pour LiteLLM : les versions PyPI 1.82.7 et 1.82.8 ont été compromises le 24/03/2026 (doc LiteLLM / `versions.yaml`) |

## 4. Ce qui est privilégié (à connaître)

- **GPU Operator** : ses DaemonSets (driver, toolkit, device plugin) accèdent à l'hôte et au GPU ; le conteneur du driver compile et charge des **modules noyau** sur le nœud (observé : « Compiling NVIDIA driver kernel modules ») - c'est un composant de confiance maximale (doc).
- **Argo CD** applique des objets dans tout le cluster : son compte a des droits très étendus (ClusterRole de la chart ; non audité ligne à ligne ici). Qui peut pousser sur la branche `main` du dépôt peut donc **tout** déployer. Protégez la branche.
- **Terraform** a les droits de l'abonnement sur le groupe de ressources du lab et l'admin du cluster.

## 5. Bonnes pratiques à appliquer pour passer en production (non faites ici)

1. Backend Terraform distant et chiffré ; secrets dans Key Vault avec External Secrets (exclus du lab par choix de coût).
2. `PeerAuthentication` STRICT + sidecars ou ambient, `AuthorizationPolicy` ; NetworkPolicies par namespace ; vérification du certificat de l'EPP.
3. Clés LiteLLM avec rotation, `hf-token` renseigné, restriction de l'API server à vos IP.
4. `ClusterRole` d'Alloy limité aux logs/événements.
5. Protection de branche et revue obligatoire sur le dépôt GitOps.
