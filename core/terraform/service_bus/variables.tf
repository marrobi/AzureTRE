variable "location" {
  description = "The Azure region where the resources will be created."
  type        = string
}

variable "resource_group_name" {
  description = "The name of the resource group where the resources will be created."
  type        = string
}

variable "tre_id" {
  description = "The TRE ID used for naming resources."
  type        = string
}

variable "core_vnet_id" {
  description = "The ID of the core virtual network."
  type        = string

}

variable "api_user_assigned_identity_id" {
  description = "The ID of the API user assigned identity."
  type        = string

}

variable "log_analytics_workspace_id" {
  description = "The ID of the log analytics workspace."
  type        = string
}
variable "tre_core_tags" {
  description = "Tags to be applied to all resources."
  type        = map(string)
}

variable "enable_local_debugging" {
  description = "Flag to enable local debugging."
  type        = bool
  default     = false
}

variable "enable_cmk_encryption" {
  description = "Flag to enable customer-managed key encryption."
  type        = bool
  default     = false
}

variable "servicebus_diagnostic_categories_enabled" {
  description = "List of enabled diagnostic categories for Service Bus."
  type        = list(string)
  default     = []
}

variable "myip" {
  description = "The IP address for local debugging."
  type        = string
}

variable "encryption_identity_id" {
  description = "identity to use for encryption"
  type        = string
}

variable "encryption_key_versionless_id" {
  description = "key to use for encryption"
  type        = string
}

variable "airlock_notification_subnet_id" {
  description = "The subnet ID for airlock notification."
  type        = string
}

variable "airlock_events_subnet_id" {
  description = "The subnet ID for airlock events."
  type        = string

}

variable "resource_processor_subnet_id" {
  description = "The subnet ID for resource processor."
  type        = string
}

variable "workspace_queue_name" {
  description = "The name of the workspace queue."
  type        = string

}

variable "deployment_status_update_queue_name" {
  description = "The name of the deployment status update queue."
  type  = string
}
variable "airlock_step_result_queue_name" {
  description = "The name of the step result queue."
  type        = string

}

variable "airlock_status_changed_queue_name" {
  description = "The name of the status changed queue."
  type        = string
}

variable "airlock_scan_result_queue_name" {
  description = "The name of the scan result queue."
  type        = string
}

variable "airlock_data_deletion_queue_name" {
  description = "The name of the data deletion queue."
  type        = string
}

variable "airlock_blob_created_topic_name" {
  description = "The name of the blob created topic."
  type        = string
}

variable "airlock_blob_created_al_processor_subscription_name" {
  description = "The name of the blob created AL processor subscription."
  type        = string
}

variable "arm_environment" {
  description = "The ARM environment to use."
  type        = string
}
