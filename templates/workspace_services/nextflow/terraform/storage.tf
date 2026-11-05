# The service keeps its files in a container in the workspace storage account rather than its own
# account, because storage accounts are limited per subscription and region. The workspace account
# already has a blob private endpoint in the workspace network.
data "azurerm_storage_account" "ws" {
  name                = local.workspace_storage_name
  resource_group_name = data.azurerm_resource_group.ws.name
}

resource "azurerm_storage_container" "nf" {
  name                  = local.storage_container_name
  storage_account_id    = data.azurerm_storage_account.ws.id
  container_access_type = "private"
  metadata = {
    tre_workspace_service_id = replace(var.id, "-", "_")
  }
}
