module "ai_foundry_storage" {
  source  = "Azure/avm-res-storage-storageaccount/azurerm"
  version = "~> 0.4"

  location            = data.azurerm_resource_group.ws.location
  name                = replace(module.naming.storage_account.name_unique, "-", "")
  resource_group_name = data.azurerm_resource_group.ws.name
  # for idempotency
  blob_properties = {
    cors_rule = [{
      allowed_headers = ["*", ]
      allowed_methods = [
        "GET",
        "HEAD",
        "PUT",
        "DELETE",
        "OPTIONS",
        "POST",
        "PATCH",
      ]
      allowed_origins = [
        "https://mlworkspace.azure.ai",
        "https://ml.azure.com",
        "https://*.ml.azure.com",
        "https://ai.azure.com",
        "https://*.ai.azure.com",
      ]
      exposed_headers = [
        "*",
      ]
      max_age_in_seconds = 1800
    }]
  }
  enable_telemetry = false
  managed_identities = {
    system_assigned = true
  }
  network_rules = {
    bypass         = ["Logging", "Metrics", "AzureServices"]
    default_action = "Deny"
  }
  private_endpoints = {
    blob = {
      name                          = "${module.naming.private_endpoint.name_unique}-blob"
      subnet_resource_id            = data.azurerm_subnet.workspace_services.id
      subresource_name              = "blob"
      private_dns_zone_resource_ids = [data.azurerm_private_dns_zone.blobcore.id]
      inherit_lock                  = false
    }
    file = {
      name                          = "${module.naming.private_endpoint.name_unique}-file"
      subnet_resource_id            = data.azurerm_subnet.workspace_services.id
      subresource_name              = "file"
      private_dns_zone_resource_ids = [data.azurerm_private_dns_zone.filecore.id]
      inherit_lock                  = false
    }
  }
  public_network_access_enabled = false
  shared_access_key_enabled     = false
  customer_managed_key = var.enable_cmk_encryption ? {
    key_vault_resource_id = data.azurerm_key_vault.ws.id
    key_name              = data.azurerm_key_vault_key.ws_encryption_key[0].name
    user_assigned_identity = {
      resource_id = data.azurerm_user_assigned_identity.ws_encryption_identity[0].id
    }
  } : null
  infrastructure_encryption_enabled = true
  queue_encryption_key_type         = var.enable_cmk_encryption ? "Account" : "Service"
  table_encryption_key_type         = var.enable_cmk_encryption ? "Account" : "Service"
  tags                              = local.tre_workspace_service_tags
}
