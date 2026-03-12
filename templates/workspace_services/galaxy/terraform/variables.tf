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
variable "vm_size" {
  type    = string
  default = "Standard_D4s_v5"
}
variable "galaxy_image_tag" {
  type    = string
  default = "24.2"
}
