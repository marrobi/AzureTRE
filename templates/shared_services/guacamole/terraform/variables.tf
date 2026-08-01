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

variable "image_name" {
  type        = string
  description = "The Guacamole image name"
}

variable "image_tag" {
  type        = string
  description = "The Guacamole image tag"
}
