# Batch pools join this subnet. Nodes have no public IPs, reach Batch and storage through private
# endpoints, and send any other egress through the TRE firewall via the core route table.
resource "azurerm_subnet" "batch" {
  name                            = "NextflowSubnet${local.short_service_id}"
  virtual_network_name            = data.azurerm_virtual_network.ws.name
  resource_group_name             = data.azurerm_resource_group.ws.name
  address_prefixes                = [var.address_space]
  default_outbound_access_enabled = false
}

resource "azurerm_network_security_group" "batch" {
  name                = "nsg-nf-${local.service_resource_name_suffix}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  tags                = local.workspace_service_tags

  # Simplified node communication needs no inbound access to the nodes.
  security_rule {
    name                       = "deny-inbound-override"
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

resource "azurerm_subnet_network_security_group_association" "batch" {
  subnet_id                 = azurerm_subnet.batch.id
  network_security_group_id = azurerm_network_security_group.batch.id
}

resource "azurerm_subnet_route_table_association" "batch" {
  subnet_id      = azurerm_subnet.batch.id
  route_table_id = data.azurerm_route_table.core.id
}

# The core TRE has no Batch private DNS zone, so the service links one to the workspace VNet.
resource "azurerm_private_dns_zone" "batch" {
  name                = module.terraform_azurerm_environment_configuration.private_links["privatelink.batch.azure.com"]
  resource_group_name = data.azurerm_resource_group.ws.name
  tags                = local.workspace_service_tags

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_private_dns_zone_virtual_network_link" "batch" {
  name                  = "batch-${local.service_resource_name_suffix}"
  resource_group_name   = data.azurerm_resource_group.ws.name
  private_dns_zone_name = azurerm_private_dns_zone.batch.name
  virtual_network_id    = data.azurerm_virtual_network.ws.id
  registration_enabled  = false
  tags                  = local.workspace_service_tags

  lifecycle { ignore_changes = [tags] }
}
