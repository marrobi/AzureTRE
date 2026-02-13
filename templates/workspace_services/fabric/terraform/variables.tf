variable "tre_id" {
  type        = string
  description = "Unique TRE ID"
}

variable "tre_resource_id" {
  type        = string
  description = "Resource ID"
}

variable "workspace_id" {
  type        = string
  description = "Workspace ID"
}

variable "fabric_capacity_sku" {
  type        = string
  default     = "F2"
  description = "The SKU for the Fabric capacity (F2, F4, F8, etc.)"
  validation {
    condition     = contains(["F2", "F4", "F8", "F16", "F32", "F64", "F128", "F256", "F512", "F1024", "F2048"], var.fabric_capacity_sku)
    error_message = "fabric_capacity_sku must be one of: F2, F4, F8, F16, F32, F64, F128, F256, F512, F1024, F2048."
  }
}

variable "is_exposed_externally" {
  type        = bool
  default     = false
  description = "Whether the Fabric workspace is accessible from outside the workspace network"
}

variable "arm_tenant_id" {
  type        = string
  description = "Azure AD tenant ID for Fabric provider authentication"
}

variable "arm_subscription_id" {
  type        = string
  description = "Azure subscription ID"
}

variable "arm_client_id" {
  type        = string
  description = "Service principal client ID for Fabric provider authentication"
}

variable "arm_client_secret" {
  type        = string
  sensitive   = true
  default     = ""
  description = "Service principal client secret for Fabric provider authentication"
}

variable "arm_use_msi" {
  type        = bool
  default     = false
  description = "Whether to use Managed Service Identity for authentication"
}

variable "arm_environment" {
  type        = string
  default     = "public"
  description = "Azure cloud environment"
}
