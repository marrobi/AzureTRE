# AI Foundry (Azure Machine Learning Services) Workspace variables
variable "workspace_id" { type = string }
variable "tre_id" { type = string }
variable "tre_resource_id" { type = string }
variable "display_name" { type = string }
variable "description" { type = string }
variable "is_exposed_externally" { type = bool }
variable "arm_tenant_id" { type = string }
variable "auth_tenant_id" { type = string }
variable "auth_client_id" { type = string }
variable "auth_client_secret" {
  type      = string
  sensitive = true
}
variable "arm_environment" { type = string }
variable "azure_environment" { type = string }
variable "enable_cmk_encryption" {
  type    = bool
  default = false
}
variable "key_store_id" { type = string }
variable "log_analytics_workspace_name" {
  type = string
}

variable "workspace_owners_group_id" {
  type        = string
  description = "The Microsoft Entra ID group ID of workspace owners who will be granted Contributor roles"
}

variable "workspace_researchers_group_id" {
  type        = string
  description = "The Microsoft Entra ID group ID of workspace researchers who will be granted User type roles"
}
