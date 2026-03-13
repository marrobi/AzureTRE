locals {
  short_service_id               = substr(var.id, -4, -1)
  short_workspace_id             = substr(var.workspace_id, -4, -1)
  workspace_resource_name_suffix = "${var.tre_id}-ws-${local.short_workspace_id}"
  service_resource_name_suffix   = "${var.tre_id}-ws-${local.short_workspace_id}-svc-${local.short_service_id}"
  core_resource_group_name       = "rg-${var.tre_id}"
  keyvault_name                  = lower("kv-${substr(local.workspace_resource_name_suffix, -20, -1)}")
  webapp_name                    = "galaxy-${local.service_resource_name_suffix}"
  vm_name                        = "galaxy-vm-${local.short_service_id}"
  image_tag_from_file            = replace(replace(replace(data.local_file.version.content, "__version__ = \"", ""), "\"", ""), "\n", "")
  image_tag                      = var.image_tag == "" ? local.image_tag_from_file : var.image_tag
  nexus_proxy_url                = "https://nexus-${data.azurerm_public_ip.app_gateway_ip.fqdn}"
  workspace_service_tags = {
    tre_id                   = var.tre_id
    tre_workspace_id         = var.workspace_id
    tre_workspace_service_id = var.id
  }
  web_app_diagnostic_categories_enabled = [
    "AppServiceHTTPLogs", "AppServiceConsoleLogs", "AppServiceAppLogs",
    "AppServiceAuditLogs", "AppServiceIPSecAuditLogs", "AppServicePlatformLogs", "AppServiceAntivirusScanAuditLogs"
  ]

  get_apt_keys_content = templatefile("${path.module}/get_apt_keys.sh", {
    NEXUS_PROXY_URL = local.nexus_proxy_url
  })

  apt_sources_config_content = templatefile("${path.module}/apt_sources_config.yml", {
    nexus_proxy_url = local.nexus_proxy_url
  })

  galaxy_vm_config_content = templatefile("${path.module}/galaxy_vm_config.sh", {
    NEXUS_PROXY_URL  = local.nexus_proxy_url
    GALAXY_IMAGE_TAG = var.galaxy_image_tag
  })
}
