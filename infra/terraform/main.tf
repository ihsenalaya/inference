provider "azurerm" {
  subscription_id                 = var.subscription_id
  resource_provider_registrations = "none"
  features {
    resource_group {
      # Le groupe de ressources du lab ne doit jamais contenir autre chose que le lab.
      prevent_deletion_if_contains_resources = false
    }
  }
}

locals {
  tags = {
    project = "inference-lab"
    prefix  = var.prefix
    managed = "terraform"
  }
}

resource "azurerm_resource_group" "this" {
  name     = "${var.prefix}-rg"
  location = var.location
  tags     = local.tags
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = "${var.prefix}-aks"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  dns_prefix          = "${var.prefix}-aks"
  node_resource_group = "${var.prefix}-aks-nodes"
  kubernetes_version  = var.kubernetes_version
  sku_tier            = "Free"
  tags                = local.tags

  # Pas de mise à jour automatique : une nouvelle image de nœud change le noyau
  # et relance l'installation du driver GPU (reproductibilité).
  node_os_upgrade_channel = "None"

  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  dynamic "api_server_access_profile" {
    for_each = length(var.api_server_authorized_cidrs) > 0 ? [1] : []
    content {
      authorized_ip_ranges = var.api_server_authorized_cidrs
    }
  }

  identity {
    type = "SystemAssigned"
  }

  # Mode Manual : nous gérons nos pools (pas de Node Auto Provisioning / Karpenter).
  node_provisioning_profile {
    mode               = "Manual"
    default_node_pools = "None"
  }

  default_node_pool {
    name                        = "system"
    vm_size                     = var.system_vm_size
    node_count                  = var.system_node_count
    os_sku                      = "Ubuntu"
    os_disk_type                = "Managed"
    os_disk_size_gb             = 64
    temporary_name_for_rotation = "systmp"
    auto_scaling_enabled        = false
    node_labels                 = { workload = "platform" }
    upgrade_settings {
      max_surge = "10%"
    }
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    load_balancer_sku   = "standard"
    outbound_type       = "loadBalancer"
  }

  # Aucun add-on Azure Monitor / Defender / Policy : tout est open source dans le cluster.
  lifecycle {
    ignore_changes = [default_node_pool[0].node_count]
  }
}

# Pool GPU : le GPU Operator installe le driver (gpu_driver = None) et AKS ne
# gère pas le GPU (pas de device plugin managé) : les deux modes sont exclusifs.
resource "azurerm_kubernetes_cluster_node_pool" "gpu" {
  name                  = "gpu"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = var.gpu_vm_size
  node_count            = var.gpu_node_count
  os_sku                = "Ubuntu"
  os_disk_type          = var.gpu_os_disk_type
  os_disk_size_gb       = var.gpu_os_disk_size_gb
  gpu_driver            = "None"
  auto_scaling_enabled  = false
  node_taints           = ["sku=gpu:NoSchedule"]
  node_labels           = { workload = "inference" }
  tags                  = local.tags

  # Pas de surge possible (quota T4 de 2 nœuds) : on remplace un nœud à la fois.
  upgrade_settings {
    max_unavailable = "1"
  }
}
