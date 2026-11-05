variable "workspace_id" {
  type = string
}
variable "tre_id" {
  type = string
}
variable "id" {
  type = string
}
variable "mgmt_resource_group_name" {
  type = string
}
variable "mgmt_acr_name" {
  type = string
}
variable "aad_authority_url" {
  type = string
}
variable "arm_environment" {
  type = string
}
variable "address_space" {
  type        = string
  description = "Address space for the Batch pool subnet, allocated by the TRE API"
}
variable "display_name" {
  type    = string
  default = "Nextflow"
}
variable "head_vm_size" {
  type    = string
  default = "Standard_D2s_v3"
}
variable "head_max_nodes" {
  type    = number
  default = 2
}
variable "worker_vm_size" {
  type    = string
  default = "Standard_D4s_v3"
}
variable "worker_max_nodes" {
  type    = number
  default = 4
}
variable "worker_use_spot" {
  type        = bool
  default     = false
  description = "Use Spot (low-priority) nodes for pipeline tasks"
}
variable "work_retention_days" {
  type        = number
  default     = 14
  description = "Days to keep Nextflow work directories before lifecycle management deletes them"
}
