# Three identities keep the portal, the Nextflow head and the pipeline task nodes separate.
# Pipeline code runs on the head and worker nodes, so none of them has ARM roles beyond its own scope.
resource "azurerm_user_assigned_identity" "portal" {
  name                = "id-nf-portal-${local.service_resource_name_suffix}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  tags                = local.workspace_service_tags

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_user_assigned_identity" "head" {
  name                = "id-nf-head-${local.service_resource_name_suffix}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  tags                = local.workspace_service_tags

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_user_assigned_identity" "worker" {
  name                = "id-nf-worker-${local.service_resource_name_suffix}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  tags                = local.workspace_service_tags

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_role_assignment" "acr_pull" {
  for_each = {
    portal = azurerm_user_assigned_identity.portal.principal_id
    head   = azurerm_user_assigned_identity.head.principal_id
    worker = azurerm_user_assigned_identity.worker.principal_id
  }
  scope                = data.azurerm_container_registry.mgmt_acr.id
  role_definition_name = "AcrPull"
  principal_id         = each.value
}

# The portal submits head tasks and the head submits pipeline tasks. Neither can create or change pools.
resource "azurerm_role_assignment" "batch_job_submitter" {
  for_each = {
    portal = azurerm_user_assigned_identity.portal.principal_id
    head   = azurerm_user_assigned_identity.head.principal_id
  }
  scope                = azurerm_batch_account.nf.id
  role_definition_name = "Azure Batch Job Submitter"
  principal_id         = each.value
}

# Also covers the user delegation keys Nextflow uses to issue container SAS tokens to tasks.
resource "azurerm_role_assignment" "blob_contributor" {
  for_each = {
    portal = azurerm_user_assigned_identity.portal.principal_id
    head   = azurerm_user_assigned_identity.head.principal_id
  }
  scope                = azurerm_storage_account.nf.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value
}

resource "random_password" "session_secret" {
  length  = 48
  special = false
}

resource "azurerm_key_vault_secret" "session_secret" {
  name         = "${local.webapp_name}-session-secret"
  value        = random_password.session_secret.result
  key_vault_id = data.azurerm_key_vault.ws.id
  tags         = local.workspace_service_tags

  lifecycle { ignore_changes = [tags] }
}

# The web app reads only the secrets of its Key Vault references.
resource "azurerm_role_assignment" "portal_secrets" {
  for_each = {
    client_secret  = "${data.azurerm_key_vault.ws.id}/secrets/workspace-client-secret"
    session_secret = azurerm_key_vault_secret.session_secret.resource_versionless_id
  }
  scope                = each.value
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.portal.principal_id
}
