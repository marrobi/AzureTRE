output "azureml_workspace_name" {
  value = azurerm_machine_learning_workspace.ml.name
}

output "azureml_acr_id" {
  value = azurerm_container_registry.acr.id
}

output "azureml_storage_account_id" {
  value = azurerm_storage_account.aml.id
}

output "connection_uri" {
  value = "https://ml.azure.com/?wsid=${azurerm_machine_learning_workspace.ml.id}&tid=${var.arm_tenant_id}"
}
