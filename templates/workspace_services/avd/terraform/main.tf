# Azure Virtual Desktop Host Pool - Personal type (one VM per user)
resource "azurerm_virtual_desktop_host_pool" "avd" {
  name                             = local.hostpool_name
  location                         = data.azurerm_resource_group.ws.location
  resource_group_name              = data.azurerm_resource_group.ws.name
  friendly_name                    = local.hostpool_friendly_name
  description                      = "Personal host pool for secure virtual desktop access"
  type                             = "Personal"
  load_balancer_type               = "Persistent"
  personal_desktop_assignment_type = "Automatic"
  start_vm_on_connect              = true
  tags                             = local.workspace_service_tags

  lifecycle { ignore_changes = [tags] }
}

# Generate registration token for session host registration
resource "azurerm_virtual_desktop_host_pool_registration_info" "avd" {
  hostpool_id     = azurerm_virtual_desktop_host_pool.avd.id
  expiration_date = timeadd(timestamp(), "24h")

  lifecycle {
    ignore_changes = [expiration_date]
  }
}

# Store registration token in Key Vault for session host deployment
resource "azurerm_key_vault_secret" "avd_registration_token" {
  name         = "avd-registration-token-${local.short_service_id}"
  value        = azurerm_virtual_desktop_host_pool_registration_info.avd.token
  key_vault_id = data.azurerm_key_vault.ws.id
  tags         = local.workspace_service_tags

  lifecycle { ignore_changes = [tags, value] }
}

# Azure Virtual Desktop Workspace
resource "azurerm_virtual_desktop_workspace" "avd" {
  name                = local.avd_workspace_name
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  friendly_name       = local.workspace_friendly_name
  description         = "Secure virtual desktop workspace for TRE"
  tags                = local.workspace_service_tags

  lifecycle { ignore_changes = [tags] }
}

# Desktop Application Group (required for personal desktop access)
resource "azurerm_virtual_desktop_application_group" "avd" {
  name                = local.application_group_name
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  host_pool_id        = azurerm_virtual_desktop_host_pool.avd.id
  type                = "Desktop"
  friendly_name       = local.app_group_friendly_name
  description         = "Desktop application group for personal desktops"
  tags                = local.workspace_service_tags

  lifecycle { ignore_changes = [tags] }
}

# Associate application group with workspace
resource "azurerm_virtual_desktop_workspace_application_group_association" "avd" {
  workspace_id         = azurerm_virtual_desktop_workspace.avd.id
  application_group_id = azurerm_virtual_desktop_application_group.avd.id
}

# Diagnostic settings for host pool
resource "azurerm_monitor_diagnostic_setting" "hostpool" {
  name                       = "diag-${local.hostpool_name}"
  target_resource_id         = azurerm_virtual_desktop_host_pool.avd.id
  log_analytics_workspace_id = data.azurerm_log_analytics_workspace.tre.id

  enabled_log {
    category = "Checkpoint"
  }

  enabled_log {
    category = "Error"
  }

  enabled_log {
    category = "Management"
  }

  enabled_log {
    category = "Connection"
  }

  enabled_log {
    category = "HostRegistration"
  }

  enabled_log {
    category = "AgentHealthStatus"
  }

  enabled_log {
    category = "NetworkData"
  }

  enabled_log {
    category = "SessionHostManagement"
  }
}

# Diagnostic settings for workspace
resource "azurerm_monitor_diagnostic_setting" "workspace" {
  name                       = "diag-${local.avd_workspace_name}"
  target_resource_id         = azurerm_virtual_desktop_workspace.avd.id
  log_analytics_workspace_id = data.azurerm_log_analytics_workspace.tre.id

  enabled_log {
    category = "Checkpoint"
  }

  enabled_log {
    category = "Error"
  }

  enabled_log {
    category = "Management"
  }

  enabled_log {
    category = "Feed"
  }
}

# Diagnostic settings for application group
resource "azurerm_monitor_diagnostic_setting" "application_group" {
  name                       = "diag-${local.application_group_name}"
  target_resource_id         = azurerm_virtual_desktop_application_group.avd.id
  log_analytics_workspace_id = data.azurerm_log_analytics_workspace.tre.id

  enabled_log {
    category = "Checkpoint"
  }

  enabled_log {
    category = "Error"
  }

  enabled_log {
    category = "Management"
  }
}
