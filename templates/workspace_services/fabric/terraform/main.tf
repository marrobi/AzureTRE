# -------------------------------------------------------------------
# Fabric Capacity (Azure resource via azurerm provider)
# -------------------------------------------------------------------
resource "azurerm_fabric_capacity" "fabric" {
  name                = local.fabric_capacity_name
  resource_group_name = data.azurerm_resource_group.ws.name
  location            = data.azurerm_resource_group.ws.location

  administration_members = local.capacity_admin_ids

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
  create_duration = "120s"
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

  timeouts = {
    create = "30m"
    update = "30m"
    delete = "30m"
  }
}

# -------------------------------------------------------------------
# Assign TRE workspace AAD groups to the Fabric workspace.
# Workspace Owners group → Admin role
# Workspace Researchers group → Contributor role
# -------------------------------------------------------------------
resource "fabric_workspace_role_assignment" "owners" {
  workspace_id = fabric_workspace.researchers.id

  principal = {
    id   = var.workspace_owners_group_id
    type = "Group"
  }

  role = "Admin"
}

resource "fabric_workspace_role_assignment" "researchers" {
  workspace_id = fabric_workspace.researchers.id

  principal = {
    id   = var.workspace_researchers_group_id
    type = "Group"
  }

  role = "Contributor"
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

  timeouts = {
    create = "10m"
    update = "10m"
    delete = "10m"
  }
}

# -------------------------------------------------------------------
# Wait for the Fabric managed VNet to be ready before creating PEs.
# The workspace must be fully initialised or PE creation may fail
# with transient "UnknownError" responses from the Fabric API.
# -------------------------------------------------------------------
resource "time_sleep" "wait_for_managed_vnet" {
  depends_on      = [fabric_workspace.researchers]
  create_duration = "30s"
}

# -------------------------------------------------------------------
# Managed Private Endpoints (outbound from Fabric to workspace storage)
# These allow Fabric Spark workloads to securely access the workspace
# storage account without traversing the public internet.
#
# The endpoints are serialised (dfs depends_on blob) to avoid
# concurrent-write errors against the Fabric control-plane.
# -------------------------------------------------------------------
resource "fabric_workspace_managed_private_endpoint" "blob" {
  workspace_id                    = fabric_workspace.researchers.id
  name                            = "pe-blob-${local.short_service_id}"
  target_private_link_resource_id = data.azurerm_storage_account.stg.id
  target_subresource_type         = "blob"
  request_message                 = "TRE Fabric workspace service - blob access for workspace ${var.workspace_id}"

  depends_on = [time_sleep.wait_for_managed_vnet]

  timeouts = {
    create = "10m"
    delete = "10m"
  }
}

resource "fabric_workspace_managed_private_endpoint" "dfs" {
  workspace_id                    = fabric_workspace.researchers.id
  name                            = "pe-dfs-${local.short_service_id}"
  target_private_link_resource_id = data.azurerm_storage_account.stg.id
  target_subresource_type         = "dfs"
  request_message                 = "TRE Fabric workspace service - dfs access for workspace ${var.workspace_id}"

  depends_on = [fabric_workspace_managed_private_endpoint.blob]

  timeouts = {
    create = "10m"
    delete = "10m"
  }
}

# -------------------------------------------------------------------
# Auto-approve managed PE connections on the workspace storage account.
#
# Fabric creates managed PEs from its managed VNet, but these appear
# as "Pending" on the target storage account and require explicit
# approval. This resource obtains an ARM token and approves any
# pending connections that match our managed PE request messages.
# -------------------------------------------------------------------
resource "terraform_data" "approve_managed_pe_connections" {
  depends_on = [fabric_workspace_managed_private_endpoint.dfs]

  # Re-run if managed PEs are recreated
  input = {
    blob_id = fabric_workspace_managed_private_endpoint.blob.id
    dfs_id  = fabric_workspace_managed_private_endpoint.dfs.id
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-e", "-c"]
    command     = <<-EOT
      # Obtain an ARM access token using the service principal credentials
      if [ "$${ARM_USE_MSI}" = "true" ]; then
        TOKEN=$(curl -s 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/' \
          -H 'Metadata: true' | jq -r '.access_token')
      else
        TOKEN=$(curl -s -X POST \
          "https://login.microsoftonline.com/$${ARM_TENANT_ID}/oauth2/v2.0/token" \
          -d "client_id=$${ARM_CLIENT_ID}&client_secret=$${ARM_CLIENT_SECRET}&scope=https://management.azure.com/.default&grant_type=client_credentials" \
          | jq -r '.access_token')
      fi

      STORAGE_ID="${data.azurerm_storage_account.stg.id}"
      API_URL="https://management.azure.com$${STORAGE_ID}/privateEndpointConnections?api-version=2023-05-01"

      # List PE connections and find pending ones matching our workspace
      CONNECTIONS=$(curl -s -H "Authorization: Bearer $${TOKEN}" "$${API_URL}")

      echo "$${CONNECTIONS}" | jq -r '.value[] | select(.properties.privateLinkServiceConnectionState.status == "Pending") | .id' | while read -r CONN_ID; do
        echo "Approving PE connection: $${CONN_ID}"
        curl -s -X PUT \
          -H "Authorization: Bearer $${TOKEN}" \
          -H "Content-Type: application/json" \
          "https://management.azure.com$${CONN_ID}?api-version=2023-05-01" \
          -d '{"properties":{"privateLinkServiceConnectionState":{"status":"Approved","description":"Auto-approved by TRE Fabric workspace service"}}}' \
          | jq -r '.properties.privateLinkServiceConnectionState.status'
      done

      echo "Managed PE approval complete."
    EOT
  }
}

# -------------------------------------------------------------------
# Custom Spark Pool
#
# Starter Pools do NOT support Managed Private Endpoints or Private
# Links.  A Custom Pool is required so that Spark sessions route
# traffic through the workspace managed VNet and its approved PEs.
#
# Node sizing is kept minimal (Small / single-node) to work within
# F2 capacity (4 Spark VCores).  Larger SKUs can increase max nodes.
# -------------------------------------------------------------------
resource "fabric_spark_custom_pool" "default" {
  workspace_id = fabric_workspace.researchers.id
  name         = "tre-pool-${local.short_service_id}"
  node_family  = "MemoryOptimized"
  node_size    = "Small"
  type         = "Workspace"

  auto_scale = {
    enabled        = true
    min_node_count = 1
    max_node_count = 1
  }

  dynamic_executor_allocation = {
    enabled       = true
    min_executors = 1
    max_executors = 1
  }

  depends_on = [terraform_data.approve_managed_pe_connections]

  timeouts = {
    create = "10m"
    update = "10m"
    delete = "10m"
  }
}

# -------------------------------------------------------------------
# Spark Workspace Settings
#
# Point the workspace at the custom pool so all notebook / Spark-job
# sessions use the managed VNet and can reach workspace storage via
# the approved managed private endpoints.
# -------------------------------------------------------------------
resource "fabric_spark_workspace_settings" "default" {
  workspace_id = fabric_workspace.researchers.id

  pool = {
    default_pool = {
      name = fabric_spark_custom_pool.default.name
      type = "Workspace"
    }
    starter_pool = {
      max_executors  = 1
      max_node_count = 1
    }
    customize_compute_enabled = true
  }

  automatic_log = {
    enabled = true
  }

  environment = {
    runtime_version = "1.3"
  }

  depends_on = [fabric_spark_custom_pool.default]
}
