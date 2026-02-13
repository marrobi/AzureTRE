# -------------------------------------------------------------------
# Fabric Capacity (Azure resource via azurerm provider)
# -------------------------------------------------------------------
resource "azurerm_fabric_capacity" "fabric" {
  name                = local.fabric_capacity_name
  resource_group_name = data.azurerm_resource_group.ws.name
  location            = data.azurerm_resource_group.ws.location

  administration_members = [data.azurerm_client_config.current.object_id]

  sku {
    name = var.fabric_capacity_sku
    tier = "Fabric"
  }

  tags = local.workspace_service_tags

  lifecycle {
    ignore_changes = [tags]
  }
}

# -------------------------------------------------------------------
# Wait for the Fabric API to register the newly created capacity.
# ARM creation completes before the Fabric control plane is ready.
# -------------------------------------------------------------------
resource "time_sleep" "wait_for_capacity" {
  depends_on      = [azurerm_fabric_capacity.fabric]
  create_duration = "60s"
}

# -------------------------------------------------------------------
# Fabric Capacity data source (reads the Fabric GUID from display name)
# -------------------------------------------------------------------
data "fabric_capacity" "this" {
  display_name = azurerm_fabric_capacity.fabric.name

  depends_on = [time_sleep.wait_for_capacity]

  lifecycle {
    postcondition {
      condition     = self.state == "Active"
      error_message = "Fabric Capacity '${azurerm_fabric_capacity.fabric.name}' is not in Active state (current: ${self.state})."
    }
  }
}

# -------------------------------------------------------------------
# Fabric Workspace
# -------------------------------------------------------------------
resource "fabric_workspace" "researchers" {
  display_name = local.fabric_workspace_name
  description  = "TRE Workspace ${var.workspace_id} - Fabric analytics environment"
  capacity_id  = data.fabric_capacity.this.id
}

# -------------------------------------------------------------------
# Default Lakehouse
# -------------------------------------------------------------------
resource "fabric_lakehouse" "default" {
  display_name = local.lakehouse_name
  description  = "Default Lakehouse for TRE workspace ${var.workspace_id}"
  workspace_id = fabric_workspace.researchers.id

  configuration = {
    enable_schemas = true
  }
}

# -------------------------------------------------------------------
# Managed Private Endpoints (outbound from Fabric to workspace storage)
# These allow Fabric Spark workloads to securely access the workspace
# storage account without traversing the public internet.
#
# NOTE: These PEs require approval on the target storage account.
# The deploying service principal must have sufficient permissions to
# auto-approve, or an admin must approve them manually.
# -------------------------------------------------------------------
resource "fabric_workspace_managed_private_endpoint" "blob" {
  workspace_id                    = fabric_workspace.researchers.id
  name                            = "pe-blob-${local.short_service_id}"
  target_private_link_resource_id = data.azurerm_storage_account.stg.id
  target_subresource_type         = "blob"
  request_message                 = "TRE Fabric workspace service - blob access for workspace ${var.workspace_id}"
}

resource "fabric_workspace_managed_private_endpoint" "dfs" {
  workspace_id                    = fabric_workspace.researchers.id
  name                            = "pe-dfs-${local.short_service_id}"
  target_private_link_resource_id = data.azurerm_storage_account.stg.id
  target_subresource_type         = "dfs"
  request_message                 = "TRE Fabric workspace service - dfs access for workspace ${var.workspace_id}"
}
