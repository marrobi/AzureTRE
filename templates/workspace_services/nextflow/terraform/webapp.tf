resource "azurerm_linux_web_app" "portal" {
  name                                           = local.webapp_name
  location                                       = data.azurerm_resource_group.ws.location
  resource_group_name                            = data.azurerm_resource_group.ws.name
  service_plan_id                                = data.azurerm_service_plan.workspace.id
  https_only                                     = true
  public_network_access_enabled                  = false
  virtual_network_subnet_id                      = data.azurerm_subnet.web_apps.id
  key_vault_reference_identity_id                = azurerm_user_assigned_identity.portal.id
  ftp_publish_basic_authentication_enabled       = false
  webdeploy_publish_basic_authentication_enabled = false
  tags                                           = local.workspace_service_tags

  app_settings = {
    WEBSITES_PORT                       = "8000"
    WEBSITES_ENABLE_APP_SERVICE_STORAGE = "false"
    AZURE_CLIENT_ID                     = azurerm_user_assigned_identity.portal.client_id
    NF_SERVICE_NAME                     = var.display_name
    NF_PUBLIC_URL                       = "https://${local.webapp_name}.azurewebsites.net"
    NF_STORAGE_ACCOUNT                  = azurerm_storage_account.nf.name
    NF_BATCH_ENDPOINT                   = "https://${azurerm_batch_account.nf.account_endpoint}"
    NF_HEAD_POOL_ID                     = local.head_pool_id
    NF_WORKER_POOL_ID                   = local.worker_pool_id
    NF_RUNTIME_IMAGE                    = local.runtime_image
    NF_HEAD_IDENTITY_CLIENT_ID          = azurerm_user_assigned_identity.head.client_id
    NF_AUTH_CLIENT_ID                   = data.azurerm_key_vault_secret.client_id.value
    NF_AUTH_AUTHORITY                   = "${var.aad_authority_url}/${data.azurerm_key_vault_secret.aad_tenant_id.value}"
    NF_AUTH_CLIENT_SECRET               = "@Microsoft.KeyVault(SecretUri=${data.azurerm_key_vault.ws.vault_uri}secrets/workspace-client-secret)"
    NF_SESSION_SECRET                   = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault_secret.session_secret.versionless_id})"
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.portal.id]
  }

  site_config {
    always_on                                     = true
    ftps_state                                    = "Disabled"
    minimum_tls_version                           = "1.2"
    vnet_route_all_enabled                        = true
    health_check_path                             = "/healthz"
    health_check_eviction_time_in_min             = 5
    container_registry_use_managed_identity       = true
    container_registry_managed_identity_client_id = azurerm_user_assigned_identity.portal.client_id

    application_stack {
      docker_registry_url = "https://${data.azurerm_container_registry.mgmt_acr.login_server}"
      docker_image_name   = "microsoft/azuretre/nextflow-workspace-service:${local.version}"
    }
  }

  logs {
    application_logs {
      file_system_level = "Information"
    }
    http_logs {
      file_system {
        retention_in_days = 7
        retention_in_mb   = 100
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.acr_pull,
    azurerm_role_assignment.portal_secrets,
  ]

  lifecycle { ignore_changes = [tags] }
}

resource "azapi_update_resource" "portal_vnet_container_pull_routing" {
  resource_id = azurerm_linux_web_app.portal.id
  type        = "Microsoft.Web/sites@2022-09-01"

  body = jsonencode({
    properties = {
      vnetImagePullEnabled = true
    }
  })
}

resource "azapi_resource_action" "restart_portal" {
  type        = "Microsoft.Web/sites@2022-09-01"
  resource_id = azurerm_linux_web_app.portal.id
  method      = "POST"
  action      = "restart"

  depends_on = [azapi_update_resource.portal_vnet_container_pull_routing]
}

resource "azurerm_private_endpoint" "portal" {
  name                = "pe-${local.webapp_name}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  subnet_id           = data.azurerm_subnet.services.id
  tags                = local.workspace_service_tags

  private_service_connection {
    name                           = "psc-${local.webapp_name}"
    private_connection_resource_id = azurerm_linux_web_app.portal.id
    subresource_names              = ["sites"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = module.terraform_azurerm_environment_configuration.private_links["privatelink.azurewebsites.net"]
    private_dns_zone_ids = [data.azurerm_private_dns_zone.azurewebsites.id]
  }

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_monitor_diagnostic_setting" "portal" {
  name                       = "diag-${local.service_resource_name_suffix}"
  target_resource_id         = azurerm_linux_web_app.portal.id
  log_analytics_workspace_id = data.azurerm_log_analytics_workspace.tre.id

  dynamic "enabled_log" {
    for_each = [
      for category in data.azurerm_monitor_diagnostic_categories.portal.log_category_types :
      category if contains(local.web_app_diagnostic_categories_enabled, category)
    ]
    content {
      category = enabled_log.value
    }
  }

  metric {
    category = "AllMetrics"
  }
}
