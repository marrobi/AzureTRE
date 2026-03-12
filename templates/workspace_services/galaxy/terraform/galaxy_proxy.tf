resource "azurerm_user_assigned_identity" "galaxy_id" {
  resource_group_name = data.azurerm_resource_group.ws.name
  location            = data.azurerm_resource_group.ws.location
  tags                = local.workspace_service_tags

  name = "id-galaxy-${local.service_resource_name_suffix}"

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_linux_web_app" "galaxy_proxy" {
  name                                           = local.webapp_name
  location                                       = data.azurerm_resource_group.ws.location
  resource_group_name                            = data.azurerm_resource_group.ws.name
  service_plan_id                                = data.azurerm_service_plan.workspace.id
  https_only                                     = true
  key_vault_reference_identity_id                = azurerm_user_assigned_identity.galaxy_id.id
  virtual_network_subnet_id                      = data.azurerm_subnet.web_apps.id
  ftp_publish_basic_authentication_enabled       = false
  webdeploy_publish_basic_authentication_enabled = false
  tags                                           = local.workspace_service_tags
  public_network_access_enabled                  = false

  app_settings = {
    WEBSITES_PORT  = "80"
    GALAXY_VM_HOST = azurerm_network_interface.galaxy_vm.private_ip_address
  }

  site_config {
    container_registry_use_managed_identity       = true
    container_registry_managed_identity_client_id = azurerm_user_assigned_identity.galaxy_id.client_id
    ftps_state                                    = "Disabled"
    always_on                                     = true
    minimum_tls_version                           = "1.3"
    vnet_route_all_enabled                        = true

    application_stack {
      docker_registry_url = "https://${data.azurerm_container_registry.mgmt_acr.login_server}"
      docker_image_name   = "/microsoft/azuretre/galaxy-workspace-service-proxy:${local.version}"
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

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.galaxy_id.id]
  }

  lifecycle { ignore_changes = [tags] }

  depends_on = [
    azurerm_role_assignment.keyvault_galaxy_ws_role,
    azurerm_linux_virtual_machine.galaxy_vm
  ]
}

resource "azapi_update_resource" "galaxy_vnet_container_pull_routing" {
  resource_id = azurerm_linux_web_app.galaxy_proxy.id
  type        = "Microsoft.Web/sites@2022-09-01"

  body = jsonencode({
    properties = {
      vnetImagePullEnabled : true
    }
  })

  depends_on = [
    azurerm_linux_web_app.galaxy_proxy
  ]
}

resource "azapi_resource_action" "restart_galaxy_webapp" {
  type        = "Microsoft.Web/sites@2022-09-01"
  resource_id = azurerm_linux_web_app.galaxy_proxy.id
  method      = "POST"
  action      = "restart"

  depends_on = [
    azapi_update_resource.galaxy_vnet_container_pull_routing
  ]
}

resource "azurerm_private_endpoint" "galaxy_private_endpoint" {
  name                = "pe-${local.webapp_name}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  subnet_id           = data.azurerm_subnet.services.id
  tags                = local.workspace_service_tags

  private_service_connection {
    private_connection_resource_id = azurerm_linux_web_app.galaxy_proxy.id
    name                           = "psc-${local.webapp_name}"
    subresource_names              = ["sites"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = module.terraform_azurerm_environment_configuration.private_links["privatelink.azurewebsites.net"]
    private_dns_zone_ids = [data.azurerm_private_dns_zone.azurewebsites.id]
  }

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_monitor_diagnostic_setting" "galaxy" {
  name                       = "diag-${local.service_resource_name_suffix}"
  target_resource_id         = azurerm_linux_web_app.galaxy_proxy.id
  log_analytics_workspace_id = data.azurerm_log_analytics_workspace.tre.id

  dynamic "enabled_log" {
    for_each = [
      for category in data.azurerm_monitor_diagnostic_categories.galaxy.log_category_types :
      category if contains(local.web_app_diagnostic_categories_enabled, category)
    ]
    content {
      category = enabled_log.value
    }
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

resource "azurerm_role_assignment" "keyvault_galaxy_ws_role" {
  scope                = data.azurerm_key_vault.ws.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.galaxy_id.principal_id
}

resource "azurerm_role_assignment" "galaxy_acrpull_role" {
  scope                = data.azurerm_container_registry.mgmt_acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.galaxy_id.principal_id
}
