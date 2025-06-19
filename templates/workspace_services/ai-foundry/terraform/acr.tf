module "avm_res_containerregistry_registry" {
  source  = "Azure/avm-res-containerregistry-registry/azurerm"
  version = "~> 0.4"

  location            = data.azurerm_resource_group.ws.location
  name                = replace(module.naming.container_registry.name_unique, "-", "")
  resource_group_name = data.azurerm_resource_group.ws.name
  private_endpoints = {
    registry = {
      name                          = "${module.naming.private_endpoint.name_unique}-acr"
      subnet_resource_id            = data.azurerm_subnet.workspace_services.id
      private_dns_zone_resource_ids = [data.azurerm_private_dns_zone.azurecr.id]
      inherit_lock                  = false
    }
  }
  customer_managed_key = var.enable_cmk_encryption ? {
    key_vault_resource_id = data.azurerm_key_vault.ws.id
    key_name              = data.azurerm_key_vault_key.ws_encryption_key[0].name
    user_assigned_identity = {
      resource_id = data.azurerm_user_assigned_identity.ws_encryption_identity[0].id
    }
  } : null

  public_network_access_enabled = false
  tags                          = local.tre_workspace_service_tags
  zone_redundancy_enabled       = false
}
