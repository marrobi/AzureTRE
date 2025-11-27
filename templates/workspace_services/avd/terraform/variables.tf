variable "workspace_id" {
  type        = string
  description = "The workspace ID"
}

variable "tre_id" {
  type        = string
  description = "The TRE ID"
}

variable "tre_resource_id" {
  type        = string
  description = "The workspace service ID"
}

variable "arm_environment" {
  type        = string
  description = "The ARM cloud environment"
}

variable "workspace_subscription_id" {
  type        = string
  description = "The id of the Azure subscription the workspace is deployed to"
  default     = ""
}

variable "enable_clipboard" {
  type        = bool
  description = "Enable clipboard redirection between session and client"
  default     = false
}

variable "clipboard_transfer_direction" {
  type        = string
  description = "Direction of allowed clipboard transfers (disabled, client_to_session, session_to_client, both)"
  default     = "disabled"
}
