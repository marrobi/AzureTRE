locals {
  myip = var.public_deployment_ip_address != "" ? var.public_deployment_ip_address : chomp(data.http.myip[0].response_body)
  tre_core_tags = {
    tre_id              = var.tre_id
    tre_core_service_id = var.tre_id
  }

  api_diagnostic_categories_enabled = [
    "AppServiceHTTPLogs", "AppServiceConsoleLogs", "AppServiceAppLogs",
    "AppServiceAuditLogs", "AppServiceIPSecAuditLogs", "AppServicePlatformLogs", "AppServiceAntivirusScanAuditLogs"
  ]
  servicebus_diagnostic_categories_enabled = ["OperationalLogs", "VNetAndIPFilteringLogs", "RuntimeAuditLogs", "ApplicationMetricsLogs"]

  docker_registry_server = data.azurerm_container_registry.mgmt_acr.login_server

  # https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-configure-firewall#allow-requests-from-the-azure-portal
  azure_portal_cosmos_ips = "104.42.195.92,40.76.54.131,52.176.6.30,52.169.50.45,52.187.184.26"

  # we define some zones in core despite not used by the core infra because
  # it's the easier way to make them available to other services in the system.
  private_dns_zone_names_non_core = toset([
    "privatelink.purview.azure.com",
    "privatelink.purviewstudio.azure.com",
    "privatelink.sql.azuresynapse.net",
    "privatelink.dev.azuresynapse.net",
    "privatelink.azuresynapse.net",
    "privatelink.dfs.core.windows.net",
    "privatelink.azurehealthcareapis.com",
    "privatelink.dicom.azurehealthcareapis.com",
    "privatelink.api.azureml.ms",
    "privatelink.cert.api.azureml.ms",
    "privatelink.notebooks.azure.net",
    "privatelink.postgres.database.azure.com",
    "privatelink.mysql.database.azure.com",
    "privatelink.database.windows.net",
    "privatelink.azuredatabricks.net",
    "privatelink.openai.azure.com",
    "privatelink.cognitiveservices.azure.com"
  ])

  service_bus_workspace_queue_name = "workspacequeue"
  service_bus_deployment_status_update_queue_name = "deploymentstatus"

  service_bus_airlock_step_result_queue_name    = "airlock-step-result"
  service_bus_airlock_status_changed_queue_name = "airlock-status-changed"
  service_bus_airlock_scan_result_queue_name    = "airlock-scan-result"
  service_bus_airlock_data_deletion_queue_name  = "airlock-data-deletion"
  service_bus_airlock_blob_created_topic_name   = "airlock-blob-created"

  service_bus_airlock_blob_created_al_processor_subscription_name = "airlock-blob-created-airlock-processor"

  # The followig regex extracts different parts of the service bus endpoint: scheme, fqdn, port, path, query and fragment. This allows us to extract the needed fqdn part.
  service_bus_namespace_fqdn = var.service_bus_emulator_enabled ? "http://localhost" : regex("(?:(?P<scheme>[^:/?#]+):)?(?://(?P<fqdn>[^/?#:]*))?(?::(?P<port>[0-9]+))?(?P<path>[^?#]*)(?:\\?(?P<query>[^#]*))?(?:#(?P<fragment>.*))?",  module.service_bus[0].endpoint).fqdn
  service_bus_namespace_id = var.service_bus_emulator_enabled ? "emulator" : module.service_bus[0].id
  service_bus_connection_string = var.service_bus_emulator_enabled ? "" : module.service_bus[0].primary_connection_string

  # The key store for encryption keys could either be external or created by terraform
  key_store_id = var.enable_cmk_encryption ? (var.external_key_store_id != null ? var.external_key_store_id : data.azurerm_key_vault.encryption_kv[0].id) : ""

  cmk_name                 = "tre-encryption-${var.tre_id}"
  encryption_identity_name = "id-encryption-${var.tre_id}"
}
