locals {
  core_vnet                = "vnet-${var.tre_id}"
  core_resource_group_name = "rg-${var.tre_id}"
  webapp_name              = "guacamole-${var.tre_id}"
  identity_name            = "id-guacamole-${var.tre_id}"
  keyvault_name            = "kv-${var.tre_id}"
  image_tag_from_file      = replace(replace(replace(data.local_file.version.content, "__version__ = \"", ""), "\"", ""), "\n", "")
  image_tag                = var.image_tag == "" ? local.image_tag_from_file : var.image_tag
  webapp_suffix            = module.terraform_azurerm_environment_configuration.web_app_suffix
  api_url                  = "https://api-${var.tre_id}.${local.webapp_suffix}"

  tre_shared_service_tags = {
    tre_id                = var.tre_id
    tre_shared_service_id = var.tre_resource_id
  }

  guacamole_diagnostic_categories_enabled = [
    "AppServiceHTTPLogs", "AppServiceConsoleLogs", "AppServiceAppLogs",
    "AppServiceAuditLogs", "AppServiceIPSecAuditLogs", "AppServicePlatformLogs", "AppServiceAntivirusScanAuditLogs"
  ]
}
