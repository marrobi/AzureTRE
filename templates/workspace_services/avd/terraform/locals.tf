locals {
  short_service_id               = substr(var.tre_resource_id, -4, -1)
  short_workspace_id             = substr(var.workspace_id, -4, -1)
  workspace_resource_name_suffix = "${var.tre_id}-ws-${local.short_workspace_id}"
  service_resource_name_suffix   = "${var.tre_id}-ws-${local.short_workspace_id}-svc-${local.short_service_id}"
  core_resource_group_name       = "rg-${var.tre_id}"
  keyvault_name                  = lower("kv-${substr(local.workspace_resource_name_suffix, -20, -1)}")

  # AVD naming
  hostpool_name             = "hp-${local.service_resource_name_suffix}"
  avd_workspace_name        = "ws-${local.service_resource_name_suffix}"
  application_group_name    = "dag-${local.service_resource_name_suffix}"
  hostpool_friendly_name    = "Personal Desktop Host Pool"
  workspace_friendly_name   = "Azure Virtual Desktop"
  app_group_friendly_name   = "Desktop Application Group"

  workspace_service_tags = {
    tre_id                   = var.tre_id
    tre_workspace_id         = var.workspace_id
    tre_workspace_service_id = var.tre_resource_id
  }
}
