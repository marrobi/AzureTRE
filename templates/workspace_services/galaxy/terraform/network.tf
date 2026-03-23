resource "azurerm_network_security_group" "galaxy_vm" {
  name                = "nsg-${local.vm_name}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  tags                = local.workspace_service_tags

  security_rule {
    name                       = "AllowHTTPFromWebAppsSubnet"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefixes    = data.azurerm_subnet.web_apps.address_prefixes
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "DenyAllInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_network_interface_security_group_association" "galaxy_vm" {
  network_interface_id      = azurerm_network_interface.galaxy_vm.id
  network_security_group_id = azurerm_network_security_group.galaxy_vm.id
}
