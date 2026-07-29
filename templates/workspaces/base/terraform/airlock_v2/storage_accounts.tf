# Global Workspace Storage with workspace_id ABAC
# This file replaces storage_accounts.tf to use the global workspace storage account
# created in core infrastructure instead of creating a per-workspace account

# Data source to reference the global workspace storage account
data "azurerm_storage_account" "sa_airlock_workspace_global" {
  provider            = azurerm.core
  name                = local.airlock_workspace_global_storage_name
  resource_group_name = local.core_resource_group_name
}

# Private Endpoint for this workspace to access the global storage account
# Each workspace needs its own PE for network isolation
# ABAC will restrict this PE to only access containers with matching workspace_id
resource "azurerm_private_endpoint" "airlock_workspace_pe" {
  name                = "pe-sa-airlock-ws-global-${var.short_workspace_id}"
  location            = var.location
  resource_group_name = var.ws_resource_group_name
  subnet_id           = var.services_subnet_id
  tags                = var.tre_workspace_tags

  lifecycle { ignore_changes = [tags] }

  # NOTE: intentionally NO private_dns_zone_group here. The shared global account is reached by one PE
  # per workspace; a per-workspace DNS zone (below) avoids the shared-zone A-record collision.
  # See docs/azure-tre-overview/airlock.md (DNS).

  private_service_connection {
    name                           = "psc-sa-airlock-ws-global-${var.short_workspace_id}"
    private_connection_resource_id = data.azurerm_storage_account.sa_airlock_workspace_global.id
    is_manual_connection           = false
    subresource_names              = ["Blob"]
  }
}

# Per-workspace private DNS zone (full account FQDN) so the shared global account resolves to THIS
# workspace's PE by longest-suffix match, keeping the per-workspace ABAC condition enforceable.
# See docs/azure-tre-overview/airlock.md (DNS).
resource "azurerm_private_dns_zone" "airlock_ws_global" {
  name                = "${local.airlock_workspace_global_storage_name}.${data.azurerm_private_dns_zone.blobcore.name}"
  resource_group_name = var.ws_resource_group_name
  tags                = var.tre_workspace_tags

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_private_dns_zone_virtual_network_link" "airlock_ws_global" {
  name                  = "airlock-ws-global-${var.short_workspace_id}"
  resource_group_name   = var.ws_resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.airlock_ws_global.name
  virtual_network_id    = var.workspace_vnet_id
  registration_enabled  = false
  tags                  = var.tre_workspace_tags

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_private_dns_a_record" "airlock_ws_global" {
  name                = "@"
  zone_name           = azurerm_private_dns_zone.airlock_ws_global.name
  resource_group_name = var.ws_resource_group_name
  ttl                 = 10
  records             = [azurerm_private_endpoint.airlock_workspace_pe.private_service_connection[0].private_ip_address]
  tags                = var.tre_workspace_tags

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_role_assignment" "api_workspace_global_blob_data_contributor" {
  provider = azurerm.core

  # Deterministic per-workspace name: distinct signer principals give distinct (principal, role, scope)
  # tuples, so multiple workspaces hold conditioned assignments on the shared account without collision.
  name                 = uuidv5("url", "${data.azurerm_storage_account.sa_airlock_workspace_global.id}-${var.workspace_id}-blob-data-contributor")
  scope                = data.azurerm_storage_account.sa_airlock_workspace_global.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.register_aad_application ? azuread_service_principal.airlock_signer[0].object_id : data.azurerm_user_assigned_identity.api_id.principal_id
  principal_type       = "ServicePrincipal"

  condition_version = "2.0"
  condition         = <<-EOT
    (
      (
        !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read'})
        AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write'})
        AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/add/action'})
        AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/delete'})
        AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/move/action'})
        AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/read'})
        AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/write'})
        AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/delete'})
      )
      OR
      (
        @Environment[Microsoft.Network/privateEndpoints] StringEqualsIgnoreCase
          '${azurerm_private_endpoint.airlock_workspace_pe.id}'
        AND
        @Resource[Microsoft.Storage/storageAccounts/blobServices/containers/metadata:workspace_id]
          StringEquals '${var.workspace_id}'
        AND
        (
          @Resource[Microsoft.Storage/storageAccounts/blobServices/containers/metadata:stage]
            StringEquals 'import-approved'
          OR
          @Resource[Microsoft.Storage/storageAccounts/blobServices/containers/metadata:stage]
            StringEquals 'export-internal'
          OR
          @Resource[Microsoft.Storage/storageAccounts/blobServices/containers/metadata:stage]
            StringEquals 'export-in-progress'
        )
      )
    )
  EOT
}
