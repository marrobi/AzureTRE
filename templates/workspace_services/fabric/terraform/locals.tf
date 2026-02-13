locals {
  short_service_id               = substr(var.tre_resource_id, -4, -1)
  short_workspace_id             = substr(var.workspace_id, -4, -1)
  workspace_resource_name_suffix = "${var.tre_id}-ws-${local.short_workspace_id}"
  service_resource_name_suffix   = "${var.tre_id}-ws-${local.short_workspace_id}-svc-${local.short_service_id}"
  core_resource_group_name       = "rg-${var.tre_id}"

  # Fabric capacity name must be alphanumeric, 3-63 chars, start with a letter
  fabric_capacity_name = lower(replace("fc${local.service_resource_name_suffix}", "-", ""))

  fabric_workspace_name = "ws-${local.service_resource_name_suffix}"
  lakehouse_name        = "lh${local.short_service_id}"

  # Workspace shared storage account - same naming convention as base workspace
  storage_name = lower(replace("stg${substr(local.workspace_resource_name_suffix, -8, -1)}", "-", ""))

  workspace_service_tags = {
    tre_id                   = var.tre_id
    tre_workspace_id         = var.workspace_id
    tre_workspace_service_id = var.tre_resource_id
  }
}
