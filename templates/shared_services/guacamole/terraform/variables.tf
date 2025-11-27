variable "tre_id" {
  type        = string
  description = "Unique TRE ID"
}

variable "tre_resource_id" {
  type        = string
  description = "Resource ID"
}

variable "mgmt_resource_group_name" {
  type        = string
  description = "Resource group name for TRE management"
}

variable "mgmt_acr_name" {
  type        = string
  description = "Name of Azure Container Registry"
}

variable "arm_environment" {
  type = string
}

variable "aad_authority_url" {
  type        = string
  description = "The Azure AD authority URL"
  default     = "https://login.microsoftonline.com"
}

variable "api_scope" {
  type        = string
  description = "The scope for the Core API, used by managed identity to get workspace details"
}

variable "image_name" {
  type        = string
  description = "The Guacamole image name"
}

variable "image_tag" {
  type        = string
  description = "The Guacamole image tag"
}

variable "guac_disable_copy" {
  type        = bool
  description = "Disable copy from the Guacamole session"
}

variable "guac_disable_paste" {
  type        = bool
  description = "Disable paste to the Guacamole session"
}

variable "guac_enable_drive" {
  type        = bool
  description = "Enable drive redirection"
}

variable "guac_drive_name" {
  type        = string
  description = "The drive name"
}

variable "guac_drive_path" {
  type        = string
  description = "The drive path"
}

variable "guac_disable_download" {
  type        = bool
  description = "Disable download from the Guacamole session"
}

variable "guac_disable_upload" {
  type        = bool
  description = "Disable upload to the Guacamole session"
}

variable "guac_server_layout" {
  type        = string
  description = "Server keyboard layout"
}
