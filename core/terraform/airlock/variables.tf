variable "tre_id" {
  type = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "airlock_storage_subnet_id" {
  type = string
}
variable "airlock_events_subnet_id" {
  type = string
}
variable "enable_local_debugging" {
  type = bool
}
variable "myip" {
  type = string
}
variable "api_principal_id" {
  type = string
}

variable "docker_registry_server" {
  type        = string
  description = "Docker registry server"
}

variable "airlock_processor_image_repository" {
  type        = string
  description = "Repository for Airlock processor image"
  default     = "microsoft/azuretre/airlock-processor"
}

variable "mgmt_resource_group_name" {
  type        = string
  description = "Shared management resource group"
}

variable "mgmt_acr_name" {
  type        = string
  description = "Management ACR name"
}

variable "airlock_app_service_plan_sku" {
  type    = string
  default = "P1v3"
}

variable "airlock_processor_subnet_id" {
  type = string
}

variable "applicationinsights_connection_string" {
  type = string
}

variable "servicebus_namespace_id"{
  type = string
}

variable "servicebus_connection_string" {
  type = string
}

variable "blob_created_topic_name" {
  type = string
}

variable "status_changed_queue_name" {
  type = string
}

variable "scan_result_queue_name" {
  type = string
}

variable "data_deletion_queue_name" {
  type = string
}

variable "tre_core_tags" {
  type = map(string)
}

variable "enable_malware_scanning" {
  type        = bool
  description = "If False, Airlock requests will skip the malware scanning stage"
}

variable "arm_environment" {
  type = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "blob_core_dns_zone_id" {
  type = string
}
variable "file_core_dns_zone_id" {
  type = string
}
variable "queue_core_dns_zone_id" {
  type = string
}
variable "table_core_dns_zone_id" {
  type = string
}

variable "encryption_identity_id" {
  type        = string
  description = "User Managed Identity with permissions to get encryption keys from key vault"
}

variable "enable_cmk_encryption" {
  type        = bool
  description = "A boolean indicating if customer managed keys will be used for encryption of supporting resources"
}

variable "encryption_key_versionless_id" {
  type        = string
  description = "Versionless ID of the encryption key in the key vault"
}
