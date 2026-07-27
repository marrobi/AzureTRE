# Per-workspace airlock SAS signer (Entra app registration). Signing airlock user-delegation
# SAS as a per-workspace identity makes the shared global storage account's ABAC condition
# enforceable and prevents cross-workspace SAS replay. The core API federates as this signer
# via workload identity federation, falling back to the core API identity when
# register_aad_application is false. See docs/azure-tre-overview/airlock.md for the rationale.

locals {
  create_airlock_signer = var.register_aad_application
  aad_endpoint          = module.terraform_azurerm_environment_configuration.active_directory_endpoint
  aad_issuer            = "${local.aad_endpoint}/${data.azuread_client_config.current.tenant_id}/v2.0"
  # Token-exchange audience differs per sovereign cloud; must match api_app/core/credentials.py.
  token_exchange_audience = endswith(local.aad_endpoint, ".us") ? "api://AzureADTokenExchangeUSGov" : (
    endswith(local.aad_endpoint, ".cn") ? "api://AzureADTokenExchangeChina" : "api://AzureADTokenExchange"
  )
}

resource "azuread_application" "airlock_signer" {
  count        = local.create_airlock_signer ? 1 : 0
  display_name = "airlock-signer-${var.short_workspace_id}"
  owners       = [data.azuread_client_config.current.object_id]

  lifecycle { ignore_changes = [owners] }
}

resource "azuread_service_principal" "airlock_signer" {
  count     = local.create_airlock_signer ? 1 : 0
  client_id = azuread_application.airlock_signer[0].client_id
  owners    = [data.azuread_client_config.current.object_id]

  feature_tags {
    enterprise = true
  }

  lifecycle { ignore_changes = [owners] }
}

# Allow the core API managed identity to federate as this workspace's signer.
resource "azuread_application_federated_identity_credential" "api" {
  count          = local.create_airlock_signer ? 1 : 0
  application_id = azuread_application.airlock_signer[0].id
  display_name   = "api-mi"
  description    = "Allows the core API managed identity to mint airlock SAS as this workspace's signer"
  audiences      = [local.token_exchange_audience]
  issuer         = local.aad_issuer
  subject        = data.azurerm_user_assigned_identity.api_id.principal_id
}
