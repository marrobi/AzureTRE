data "azurerm_key_vault_secret" "workspace_client_id" {
  name         = "workspace-client-id"
  key_vault_id = data.azurerm_key_vault.ws.id
}

resource "azurerm_role_assignment" "researchers_storage_blob_data_contributor" {
  scope              = module.ai_foundry_storage.resource_id
  role_definition_id = data.azurerm_role_definition.storage_blob_data_contributor.id
  principal_id       = var.workspace_researchers_group_id
}

resource "azurerm_role_assignment" "researchers_storage_file_data_contributor" {
  scope              = module.ai_foundry_storage.resource_id
  role_definition_id = data.azurerm_role_definition.storage_file_data_contributor.id
  principal_id       = var.workspace_researchers_group_id
}

resource "azurerm_role_assignment" "researchers_openai_user" {
  scope              = module.ai_services.resource_id
  role_definition_id = data.azurerm_role_definition.cognitive_services_openai_user.id
  principal_id       = var.workspace_researchers_group_id
}

resource "azurerm_role_assignment" "researchers_azure_ai_developer" {
  scope              = module.aihub.resource_id
  role_definition_id = data.azurerm_role_definition.azure_ai_developer.id
  principal_id       = var.workspace_researchers_group_id
}
