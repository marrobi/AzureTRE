variable "workspace_id" {
  type = string
}

variable "tre_id" {
  type = string
}

variable "parent_service_id" {
  type = string
}

variable "tre_resource_id" {
  type = string
}

variable "image" {
  type = string
}

variable "vm_size" {
  type = string
}

variable "shared_storage_access" {
  type = bool
}

variable "shared_storage_name" {
  type = string
}

variable "enable_shutdown_schedule" {
  type    = bool
  default = false
}

variable "shutdown_time" {
  type = string
}

variable "shutdown_timezone" {
  type    = string
  default = "UTC"
}

variable "owner_id" {
  type = string
}

variable "admin_username" {
  type = string
}

variable "arm_environment" {
  type = string
}

variable "workspace_subscription_id" {
  type        = string
  description = "The id of the Azure subscription the workspace is deployed to"
  default     = ""
}
