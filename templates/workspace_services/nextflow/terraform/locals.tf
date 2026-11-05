locals {
  short_service_id               = substr(var.id, -4, -1)
  short_workspace_id             = substr(var.workspace_id, -4, -1)
  workspace_resource_name_suffix = "${var.tre_id}-ws-${local.short_workspace_id}"
  service_resource_name_suffix   = "${var.tre_id}-ws-${local.short_workspace_id}-svc-${local.short_service_id}"
  core_resource_group_name       = "rg-${var.tre_id}"
  keyvault_name                  = lower("kv-${substr(local.workspace_resource_name_suffix, -20, -1)}")
  compact_suffix                 = lower(replace("${var.tre_id}${local.short_workspace_id}${local.short_service_id}", "-", ""))
  storage_name                   = substr("stnf${local.compact_suffix}", 0, 24)
  batch_account_name             = substr("banf${local.compact_suffix}", 0, 24)
  webapp_name                    = "nextflow-${local.service_resource_name_suffix}"
  version                        = replace(replace(replace(data.local_file.version.content, "__version__ = \"", ""), "\"", ""), "\n", "")
  runtime_image                  = "${data.azurerm_container_registry.mgmt_acr.login_server}/microsoft/azuretre/nextflow-workspace-service:${local.version}"
  nexus_proxy_url                = "https://nexus-${data.azurerm_public_ip.app_gateway_ip.fqdn}"
  head_pool_id                   = "nf-head"
  worker_pool_id                 = "nf-worker"
  storage_containers             = ["pipelines", "inputs", "work", "results", "runs"]
  # Nextflow requires one task slot per vCPU on existing pools. Keep in sync with template_schema.json.
  vm_vcpus = {
    Standard_D2s_v3  = 2
    Standard_D4s_v3  = 4
    Standard_D8s_v3  = 8
    Standard_D16s_v3 = 16
    Standard_E4s_v3  = 4
    Standard_E8s_v3  = 8
    Standard_E16s_v3 = 16
  }
  worker_vcpus = local.vm_vcpus[var.worker_vm_size]
  web_app_diagnostic_categories_enabled = [
    "AppServiceHTTPLogs", "AppServiceConsoleLogs", "AppServiceAppLogs",
    "AppServiceAuditLogs", "AppServiceIPSecAuditLogs", "AppServicePlatformLogs"
  ]
  workspace_service_tags = {
    tre_id                   = var.tre_id
    tre_workspace_id         = var.workspace_id
    tre_workspace_service_id = var.id
  }
}
