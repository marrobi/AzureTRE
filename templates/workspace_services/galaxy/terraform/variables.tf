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
variable "arm_environment" {
  type = string
}
variable "image_name" {
  type        = string
  description = "The Galaxy proxy image name"
}
variable "image_tag" {
  type        = string
  default     = ""
  description = "The Galaxy proxy image tag"
}
variable "vm_size" {
  type    = string
  default = "Standard_D4s_v6"
}
variable "galaxy_image_tag" {
  type    = string
  default = "24.2"
}
variable "aad_authority_url" {
  type    = string
  default = "https://login.microsoftonline.com"
}
variable "galaxy_admin_users" {
  type    = string
  default = ""
}
