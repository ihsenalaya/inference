variable "subscription_id" {
  type        = string
  description = "Abonnement Azure cible."
}

variable "location" {
  type        = string
  default     = "eastus"
  description = "Région. Seule eastus a du quota T4 sur l'abonnement (8 vCPU)."
}

variable "prefix" {
  type    = string
  default = "inflab"
}

variable "kubernetes_version" {
  type        = string
  default     = "1.34"
  description = "Version mineure d'AKS (voir docs/DECISIONS.md)."
}

variable "system_vm_size" {
  type        = string
  default     = "Standard_D4as_v7"
  description = "Pool système : 4 vCPU / 16 Gio AMD, le moins cher (0,182 $/h) qui héberge la plateforme."
}

variable "system_node_count" {
  type    = number
  default = 1
}

variable "gpu_vm_size" {
  type    = string
  default = "Standard_NC4as_T4_v3"
}

variable "gpu_node_count" {
  type        = number
  default     = 1
  description = "Nombre de nœuds T4 (0 à 2). Commencer à 1."
  validation {
    condition     = var.gpu_node_count >= 0 && var.gpu_node_count <= 2
    error_message = "Le quota T4 permet 2 nœuds au maximum."
  }
}

variable "gpu_os_disk_type" {
  type        = string
  default     = "Ephemeral"
  description = "Ephemeral (disque temporaire 180 Gio, gratuit, rapide) ou Managed."
}

variable "gpu_os_disk_size_gb" {
  type    = number
  default = 128
}

variable "api_server_authorized_cidrs" {
  type        = list(string)
  default     = []
  description = "Restreint l'API server (MY_IP_CIDR). Vide = ouvert."
}

# ---- GitOps -----------------------------------------------------------------
variable "git_repo_url" {
  type    = string
  default = "https://github.com/ihsenalaya/inference.git"
}

variable "git_revision" {
  type    = string
  default = "main"
}

variable "argocd_chart_version" {
  type    = string
  default = "10.18.0"
}

variable "hf_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "alert_webhook_url" {
  type      = string
  default   = ""
  sensitive = true
}

variable "gpu_hourly_price" {
  type        = number
  default     = 0.526
  description = "Prix horaire d'un nœud GPU (Azure Retail Prices, eastus, Linux), exposé en métrique."
}

# ---- Garde-fou de coût ------------------------------------------------------
variable "budget_amount" {
  type        = number
  default     = 40
  description = "Budget mensuel du groupe de ressources du lab (devise de l'abonnement). 0 = pas de budget. Alertes à 50 %, 80 %, 100 % (réel) et 100 % (prévision)."
}
