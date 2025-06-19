module "ai_services" {
  source  = "Azure/avm-res-cognitiveservices-account/azurerm"
  version = "0.6.0"

  kind                               = "AIServices"
  location                           = data.azurerm_resource_group.ws.location
  name                               = module.naming.cognitive_account.name_unique
  resource_group_name                = data.azurerm_resource_group.ws.name
  sku_name                           = "S0"
  enable_telemetry                   = false
  local_auth_enabled                 = true
  outbound_network_access_restricted = false
  public_network_access_enabled      = true # required for AI Foundry
  tags                               = local.tre_workspace_service_tags
}

module "aihub" {
  source  = "Azure/avm-res-machinelearningservices-workspace/azurerm"
  version = "0.7.0"

  location            = data.azurerm_resource_group.ws.location
  name                = local.hub_name
  resource_group_name = data.azurerm_resource_group.ws.name
  aiservices = {
    resource_group_id         = data.azurerm_resource_group.ws.id
    name                      = module.ai_services.name
    create_service_connection = true
  }
  container_registry = {
    resource_id = module.avm_res_containerregistry_registry.resource_id
  }
  enable_telemetry = false
  is_private       = var.is_exposed_externally ? false : true
  key_vault = {
    resource_id = data.azurerm_key_vault.ws.id
  }
  kind = "Hub"
  private_endpoints = {
    hub = {
      name                          = "${module.naming.private_endpoint.name_unique}-aihub"
      subnet_resource_id            = data.azurerm_subnet.workspace_services.id
      private_dns_zone_resource_ids = [data.azurerm_private_dns_zone.azureml.id, data.azurerm_private_dns_zone.notebooks.id]
      inherit_lock                  = false
    }
  }
  storage_account = {
    resource_id = module.ai_foundry_storage.resource_id
  }
  workspace_friendly_name = "Private AI Studio Hub"
  workspace_managed_network = {
    isolation_mode = "AllowOnlyApprovedOutbound"
  }
}

module "ai_foundry_project" {
  source  = "Azure/avm-res-machinelearningservices-workspace/azurerm"
  version = "0.7.0"

  location                = data.azurerm_resource_group.ws.location
  name                    = local.project_name
  resource_group_name     = data.azurerm_resource_group.ws.name
  workspace_friendly_name = var.display_name
  workspace_description   = var.description
  tags                    = local.tre_workspace_service_tags
  kind                    = "Project"
  ai_studio_hub_id        = module.aihub.resource_id
}
