output "resource_group" {
  value = azurerm_resource_group.this.name
}
output "cluster_name" {
  value = azurerm_kubernetes_cluster.this.name
}
output "get_credentials" {
  value = "az aks get-credentials -g ${azurerm_resource_group.this.name} -n ${azurerm_kubernetes_cluster.this.name} --overwrite-existing"
}
output "grafana_admin_password" {
  value     = random_password.grafana.result
  sensitive = true
}
output "litellm_master_key" {
  value     = "sk-${random_password.litellm_master.result}"
  sensitive = true
}
