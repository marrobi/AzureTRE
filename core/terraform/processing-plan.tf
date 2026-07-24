# Shared App Service Plan for the TRE core "processing" Function apps (Airlock and Cost Processor).
# The Azure resource name is intentionally kept as "plan-airlock-<tre_id>" (its original name) even
# though the Terraform resource is now "processing": an App Service Plan name is immutable, so
# renaming it would force a destroy/recreate and take the Airlock Processor offline on upgrade.
# The state address change (it previously lived inside the airlock module) is handled by the moved
# block below, so existing deployments migrate in place with no downtime.
resource "azurerm_service_plan" "processing" {
  name                = "plan-airlock-${var.tre_id}"
  resource_group_name = azurerm_resource_group.core.name
  location            = azurerm_resource_group.core.location
  os_type             = "Linux"
  sku_name            = var.core_app_service_plan_sku
  tags                = local.tre_core_tags
  worker_count        = 1

  lifecycle { ignore_changes = [tags] }
}

moved {
  from = module.airlock_resources.azurerm_service_plan.airlock_plan
  to   = azurerm_service_plan.processing
}
