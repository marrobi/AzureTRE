data "azurerm_client_config" "current" {
  provider = azurerm.core
}

data "azurerm_resource_group" "ws" {
  name = "rg-${var.tre_id}-ws-${local.short_workspace_id}"
}

data "azurerm_virtual_network" "ws" {
  name                = "vnet-${var.tre_id}-ws-${local.short_workspace_id}"
  resource_group_name = data.azurerm_resource_group.ws.name
}

data "azurerm_subnet" "services" {
  name                 = "ServicesSubnet"
  virtual_network_name = data.azurerm_virtual_network.ws.name
  resource_group_name  = data.azurerm_resource_group.ws.name
}

data "azurerm_key_vault" "ws" {
  name                = local.keyvault_name
  resource_group_name = data.azurerm_resource_group.ws.name
}

data "azurerm_log_analytics_workspace" "tre" {
  provider            = azurerm.core
  name                = "log-${var.tre_id}"
  resource_group_name = local.core_resource_group_name
}

data "azurerm_private_dns_zone" "wvd" {
  provider            = azurerm.core
  name                = module.terraform_azurerm_environment_configuration.private_links["privatelink.wvd.microsoft.com"]
  resource_group_name = local.core_resource_group_name
}
