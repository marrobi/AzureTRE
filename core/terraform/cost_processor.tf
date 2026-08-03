data "local_file" "cost_processor_version" {
  filename = "${path.root}/../../cost_processor/_version.py"
}

locals {
  cost_processor_version           = replace(replace(replace(data.local_file.cost_processor_version.content, "__version__ = \"", ""), "\"", ""), "\n", "")
  cost_processor_function_app_name = "func-cost-processor-${var.tre_id}"
  cost_processor_function_sa_name  = lower(replace("stcostp${var.tre_id}", "-", ""))
  cost_exports_container_name      = "cost-exports"
}

# Managed identity the Cost Processor uses to call the TRE API; the internal refresh endpoint
# authorises it by matching this identity's client id (no Graph app role assignment required).
resource "azurerm_user_assigned_identity" "cost_processor_id" {
  resource_group_name = azurerm_resource_group.core.name
  location            = azurerm_resource_group.core.location
  name                = "id-cost-processor-${var.tre_id}"
  tags                = local.tre_core_tags

  lifecycle { ignore_changes = [tags] }
}

# Allow the identity to pull the Cost Processor container image.
resource "azurerm_role_assignment" "cost_processor_acrpull" {
  scope                = data.azurerm_container_registry.mgmt_acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.cost_processor_id.principal_id
}

resource "azurerm_storage_account" "sa_cost_processor_func_app" {
  name                             = local.cost_processor_function_sa_name
  resource_group_name              = azurerm_resource_group.core.name
  location                         = azurerm_resource_group.core.location
  account_tier                     = "Standard"
  account_replication_type         = "LRS"
  table_encryption_key_type        = var.enable_cmk_encryption ? "Account" : "Service"
  queue_encryption_key_type        = var.enable_cmk_encryption ? "Account" : "Service"
  allow_nested_items_to_be_public  = false
  cross_tenant_replication_enabled = false
  local_user_enabled               = false
  shared_access_key_enabled        = false
  public_network_access_enabled    = true
  tags                             = local.tre_core_tags

  network_rules {
    default_action = var.enable_local_debugging ? "Allow" : "Deny"
    bypass         = ["AzureServices"]
  }

  dynamic "identity" {
    for_each = var.enable_cmk_encryption ? [1] : []
    content {
      type         = "UserAssigned"
      identity_ids = [azurerm_user_assigned_identity.encryption[0].id]
    }
  }

  # changing this value is destructive, hence attribute is in lifecycle.ignore_changes block below
  infrastructure_encryption_enabled = true

  dynamic "customer_managed_key" {
    for_each = var.enable_cmk_encryption ? [1] : []
    content {
      key_vault_key_id          = azurerm_key_vault_key.tre_encryption[0].versionless_id
      user_assigned_identity_id = azurerm_user_assigned_identity.encryption[0].id
    }
  }

  lifecycle { ignore_changes = [infrastructure_encryption_enabled, tags] }
}

# Allow the function host to use its storage account via managed identity.
resource "azurerm_role_assignment" "cost_processor_function_host_storage" {
  for_each             = toset(["Storage Account Contributor", "Storage Blob Data Owner", "Storage Queue Data Contributor"])
  scope                = azurerm_storage_account.sa_cost_processor_func_app.id
  role_definition_name = each.value
  principal_id         = azurerm_user_assigned_identity.cost_processor_id.principal_id
}

# Container the Cost Management exports deliver their monthly CSVs to. Closed months are seeded
# and finalised from exports (see the "Seed a historical cost dataset with the Exports API"
# tutorial) rather than repeated Query API calls.
resource "azurerm_storage_container" "cost_exports" {
  name                  = local.cost_exports_container_name
  storage_account_id    = azurerm_storage_account.sa_cost_processor_func_app.id
  container_access_type = "private"
}

# Create/run Cost Management exports and read the cost data they are built from.
resource "azurerm_role_assignment" "cost_processor_cost_management" {
  scope                = data.azurerm_subscription.current.id
  role_definition_name = "Cost Management Contributor"
  principal_id         = azurerm_user_assigned_identity.cost_processor_id.principal_id
}

# Read the CSVs the export writes.
resource "azurerm_role_assignment" "cost_processor_exports_blob_reader" {
  scope                = azurerm_storage_container.cost_exports.resource_manager_id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_user_assigned_identity.cost_processor_id.principal_id
}

# Creating or updating an export makes Cost Management assign Storage Blob Data Contributor to
# the export's own system-assigned identity on the destination container, using the caller's
# privilege - so the caller needs to be able to write role assignments at that scope.
resource "azurerm_role_assignment" "cost_processor_exports_rbac_admin" {
  scope                            = azurerm_storage_container.cost_exports.resource_manager_id
  role_definition_name             = "Role Based Access Control Administrator"
  principal_id                     = azurerm_user_assigned_identity.cost_processor_id.principal_id
  skip_service_principal_aad_check = true
}

resource "azurerm_linux_function_app" "cost_processor_function_app" {
  name                                           = local.cost_processor_function_app_name
  resource_group_name                            = azurerm_resource_group.core.name
  location                                       = azurerm_resource_group.core.location
  https_only                                     = true
  virtual_network_subnet_id                      = module.network.processor_subnet_id
  service_plan_id                                = azurerm_service_plan.processing.id
  ftp_publish_basic_authentication_enabled       = false
  webdeploy_publish_basic_authentication_enabled = false
  storage_account_name                           = azurerm_storage_account.sa_cost_processor_func_app.name
  storage_uses_managed_identity                  = true
  vnet_image_pull_enabled                        = true

  tags = local.tre_core_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.cost_processor_id.id]
  }

  app_settings = {
    "TRE_API_URL"                                     = "https://${azurerm_linux_web_app.api.default_hostname}"
    "API_CLIENT_ID"                                   = var.api_client_id
    "MANAGED_IDENTITY_CLIENT_ID"                      = azurerm_user_assigned_identity.cost_processor_id.client_id
    "TRE_ID"                                          = var.tre_id
    "AZURE_SUBSCRIPTION_ID"                           = data.azurerm_subscription.current.subscription_id
    "COST_EXPORT_STORAGE_ACCOUNT"                     = azurerm_storage_account.sa_cost_processor_func_app.name
    "COST_EXPORT_STORAGE_ACCOUNT_ID"                  = azurerm_storage_account.sa_cost_processor_func_app.id
    "COST_EXPORT_CONTAINER"                           = azurerm_storage_container.cost_exports.name
    "ARM_ENVIRONMENT"                                 = var.arm_environment
    "COST_PROCESSOR_CURRENT_MONTH_SCHEDULE"           = var.cost_processor_current_month_schedule
    "COST_PROCESSOR_PREVIOUS_MONTH_SCHEDULE"          = var.cost_processor_previous_month_schedule
    "COST_PROCESSOR_PREVIOUS_MONTHS_LOOK_BACK"        = var.cost_processor_previous_months_look_back
    "COST_PROCESSOR_BACKFILL_SCHEDULE"                = var.cost_processor_backfill_schedule
    "COST_PROCESSOR_BACKFILL_MAX_MONTHS"              = var.cost_processor_backfill_max_months
    "COST_PROCESSOR_BACKFILL_STOP_AFTER_EMPTY_MONTHS" = var.cost_processor_backfill_stop_after_empty_months
    "COST_PROCESSOR_BACKFILL_MAX_RUNTIME_SECONDS"     = var.cost_processor_backfill_max_runtime_seconds
    "WEBSITES_ENABLE_APP_SERVICE_STORAGE"             = false
    "WEBSITE_CONTENTOVERVNET"                         = 1
    "STORAGE_ENDPOINT_SUFFIX"                         = module.terraform_azurerm_environment_configuration.storage_suffix

    "AzureWebJobsStorage__clientId"   = azurerm_user_assigned_identity.cost_processor_id.client_id
    "AzureWebJobsStorage__credential" = "managedidentity"
  }

  site_config {
    http2_enabled                                 = true
    always_on                                     = true
    container_registry_managed_identity_client_id = azurerm_user_assigned_identity.cost_processor_id.client_id
    container_registry_use_managed_identity       = true
    vnet_route_all_enabled                        = true
    ftps_state                                    = "Disabled"
    minimum_tls_version                           = "1.3"

    application_stack {
      docker {
        registry_url = "https://${local.docker_registry_server}"
        image_name   = var.cost_processor_image_repository
        image_tag    = local.cost_processor_version
      }
    }

    # This is added automatically (by Azure?) when the equivalent is set in app_settings.
    # Setting it here to save TF from updating on every apply.
    application_insights_connection_string = module.azure_monitor.app_insights_connection_string
  }

  lifecycle { ignore_changes = [tags] }
  # Ensure the private endpoint is created on the storage account to try to avoid a race condition.
  depends_on = [azurerm_private_endpoint.cost_processor_function_storage]
}

resource "azurerm_monitor_diagnostic_setting" "cost_processor_function_app" {
  name                       = "diagnostics-cost-processor-function-${var.tre_id}"
  target_resource_id         = azurerm_linux_function_app.cost_processor_function_app.id
  log_analytics_workspace_id = module.azure_monitor.log_analytics_workspace_id

  enabled_log {
    category = "FunctionAppLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }

  lifecycle { ignore_changes = [log_analytics_destination_type] }
}

resource "azurerm_private_endpoint" "cost_processor_function_storage" {
  for_each = {
    Blob  = module.network.blob_core_dns_zone_id
    File  = module.network.file_core_dns_zone_id
    Queue = module.network.queue_core_dns_zone_id
    Table = module.network.table_core_dns_zone_id
  }
  name                = "pe-${local.cost_processor_function_sa_name}-${lower(each.key)}"
  location            = azurerm_resource_group.core.location
  resource_group_name = azurerm_resource_group.core.name
  subnet_id           = module.network.shared_subnet_id
  tags                = local.tre_core_tags

  lifecycle { ignore_changes = [tags] }

  private_dns_zone_group {
    name                 = "private-dns-zone-group-${local.cost_processor_function_sa_name}"
    private_dns_zone_ids = [each.value]
  }

  private_service_connection {
    name                           = "psc-${local.cost_processor_function_sa_name}"
    private_connection_resource_id = azurerm_storage_account.sa_cost_processor_func_app.id
    is_manual_connection           = false
    subresource_names              = [each.key]
  }
}
