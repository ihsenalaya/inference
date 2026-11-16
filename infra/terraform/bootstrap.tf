# Amorçage GitOps : Argo CD, secrets, application racine. Tout le reste vit dans Git.

provider "kubernetes" {
  host                   = azurerm_kubernetes_cluster.this.kube_config[0].host
  client_certificate     = base64decode(azurerm_kubernetes_cluster.this.kube_config[0].client_certificate)
  client_key             = base64decode(azurerm_kubernetes_cluster.this.kube_config[0].client_key)
  cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.this.kube_config[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes = {
    host                   = azurerm_kubernetes_cluster.this.kube_config[0].host
    client_certificate     = base64decode(azurerm_kubernetes_cluster.this.kube_config[0].client_certificate)
    client_key             = base64decode(azurerm_kubernetes_cluster.this.kube_config[0].client_key)
    cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.this.kube_config[0].cluster_ca_certificate)
  }
}

# --- Secrets générés (jamais dans Git ; l'état Terraform est local et ignoré) ---
resource "random_password" "litellm_master" {
  length  = 32
  special = false
}
resource "random_password" "litellm_salt" {
  length  = 32
  special = false
}
resource "random_password" "postgres" {
  length  = 24
  special = false
}
resource "random_password" "grafana" {
  length  = 20
  special = false
}

resource "kubernetes_namespace_v1" "ns" {
  for_each = toset(["gateway", "monitoring", "inference"])
  metadata {
    name = each.key
  }
  depends_on = [azurerm_kubernetes_cluster_node_pool.gpu]
}

resource "kubernetes_secret_v1" "litellm" {
  metadata {
    name      = "litellm-secrets"
    namespace = kubernetes_namespace_v1.ns["gateway"].metadata[0].name
  }
  data = {
    LITELLM_MASTER_KEY = "sk-${random_password.litellm_master.result}"
    LITELLM_SALT_KEY   = "sk-${random_password.litellm_salt.result}"
    POSTGRES_PASSWORD  = random_password.postgres.result
    DATABASE_URL       = "postgresql://litellm:${random_password.postgres.result}@postgres.gateway.svc:5432/litellm"
  }
}

resource "kubernetes_secret_v1" "grafana" {
  metadata {
    name      = "grafana-admin"
    namespace = kubernetes_namespace_v1.ns["monitoring"].metadata[0].name
  }
  data = {
    admin-user     = "admin"
    admin-password = random_password.grafana.result
  }
}

resource "kubernetes_secret_v1" "hf" {
  metadata {
    name      = "hf-token"
    namespace = kubernetes_namespace_v1.ns["inference"].metadata[0].name
  }
  data = {
    HF_TOKEN = var.hf_token
  }
}

resource "kubernetes_secret_v1" "alert_webhook" {
  metadata {
    name      = "alert-webhook"
    namespace = kubernetes_namespace_v1.ns["monitoring"].metadata[0].name
  }
  data = {
    url = var.alert_webhook_url != "" ? var.alert_webhook_url : "http://alert-sink.monitoring.svc:8080/"
  }
}

# --- Argo CD ---
resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_chart_version
  namespace        = "argocd"
  create_namespace = true
  wait             = true
  timeout          = 900
  values           = [file("${path.module}/../../gitops/bootstrap/argocd-values.yaml")]
  depends_on       = [kubernetes_secret_v1.litellm]
}

# --- Application racine (app-of-apps) ---
resource "helm_release" "root" {
  name       = "root"
  chart      = "${path.module}/../../gitops/bootstrap/root-app"
  namespace  = "argocd"
  wait       = true
  depends_on = [helm_release.argocd]

  set = [
    { name = "repoURL", value = var.git_repo_url },
    { name = "revision", value = var.git_revision },
    { name = "env", value = "azure" },
    { name = "gpuHourlyPrice", value = tostring(var.gpu_hourly_price) },
    { name = "gpuNodes", value = tostring(var.gpu_node_count) },
  ]
}
