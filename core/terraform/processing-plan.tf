# Shared App Service Plan for the TRE core "processing" Function apps.
#
# This plan hosts more than one appropriately-named Function app (for example the
# Airlock Processor and the Cost Processor), so it is intentionally named after its
# role ("processing") rather than after any single app that runs on it.
resource "azurerm_service_plan" "processing" {
  name                = "plan-processing-${var.tre_id}"
  resource_group_name = azurerm_resource_group.core.name
  location            = azurerm_resource_group.core.location
  os_type             = "Linux"
  sku_name            = var.core_app_service_plan_sku
  tags                = local.tre_core_tags
  worker_count        = 1

  lifecycle { ignore_changes = [tags] }
}
