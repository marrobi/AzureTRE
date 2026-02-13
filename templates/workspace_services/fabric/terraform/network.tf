# -------------------------------------------------------------------
# Workspace-level Private Link Service for Fabric
#
# This creates the hidden proxy resource that enables workspace-level
# private endpoints. There is no native azurerm resource for this;
# we use azapi_resource to deploy the ARM resource directly.
#
# Resource type: Microsoft.Fabric/privateLinkServicesForFabric
# This maps the Fabric workspace to a private link service that can
# be targeted by an Azure Private Endpoint.
# -------------------------------------------------------------------
resource "azapi_resource" "fabric_pls" {
  type      = "Microsoft.Fabric/privateLinkServicesForFabric@2024-06-01"
  name      = "fabric-pls-${local.service_resource_name_suffix}"
  location  = "global"
  parent_id = data.azurerm_resource_group.ws.id

  schema_validation_enabled = false

  body = {
    properties = {
      tenantId    = data.azurerm_client_config.current.tenant_id
      workspaceId = fabric_workspace.researchers.id
    }
  }

  tags = local.workspace_service_tags

  lifecycle {
    ignore_changes = [tags]
  }
}

# -------------------------------------------------------------------
# Private Endpoint for inbound access to the Fabric workspace
#
# Placed in ServicesSubnet so that VMs and other resources within the
# workspace VNet can access the Fabric workspace UI and APIs over
# the private network. Traffic resolves via privatelink.fabric.microsoft.com.
# -------------------------------------------------------------------
resource "azurerm_private_endpoint" "fabric_workspace" {
  name                = "pe-fabric-${local.service_resource_name_suffix}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  subnet_id           = data.azurerm_subnet.services.id

  private_service_connection {
    name                           = "psc-fabric-${local.service_resource_name_suffix}"
    private_connection_resource_id = azapi_resource.fabric_pls.id
    subresource_names              = ["workspace"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "fabric-dns-group"
    private_dns_zone_ids = [data.azurerm_private_dns_zone.fabric.id]
  }

  tags = local.workspace_service_tags

  lifecycle {
    ignore_changes = [tags]
  }
}

# -------------------------------------------------------------------
# Link the Fabric private DNS zone to the workspace VNet
#
# This ensures that DNS queries for *.fabric.microsoft.com from within
# the workspace VNet resolve to the private endpoint IP addresses.
# -------------------------------------------------------------------
resource "azurerm_private_dns_zone_virtual_network_link" "fabric" {
  provider              = azurerm.core
  name                  = "fabric-dns-link-ws-${local.short_workspace_id}-svc-${local.short_service_id}"
  resource_group_name   = local.core_resource_group_name
  private_dns_zone_name = data.azurerm_private_dns_zone.fabric.name
  virtual_network_id    = data.azurerm_virtual_network.ws.id

  lifecycle {
    ignore_changes = [tags]
  }
}
