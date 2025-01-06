terraform {
  # In modules we should only specify the min version
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.117"
    }
  }
}

module "terraform_azurerm_environment_configuration" {
  source          = "git::https://github.com/microsoft/terraform-azurerm-environment-configuration.git?ref=0.6.0"
  arm_environment = var.arm_environment
}

data "azurerm_monitor_diagnostic_categories" "sb" {
  resource_id =  azurerm_servicebus_namespace.sb.id
}
