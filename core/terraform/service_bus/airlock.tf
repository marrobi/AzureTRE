# Utilize the existing service bus - add new queue
resource "azurerm_servicebus_queue" "step_result" {
  name         = var.airlock_step_result_queue_name
  namespace_id = azurerm_servicebus_namespace.sb.id

  partitioning_enabled = false
}

resource "azurerm_servicebus_queue" "status_changed" {
  name         = var.airlock_status_changed_queue_name
  namespace_id = azurerm_servicebus_namespace.sb.id

  partitioning_enabled = false
}

resource "azurerm_servicebus_queue" "scan_result" {
  name         = var.airlock_scan_result_queue_name
  namespace_id = azurerm_servicebus_namespace.sb.id

  partitioning_enabled = false
}

resource "azurerm_servicebus_queue" "data_deletion" {
  name         = var.airlock_data_deletion_queue_name
  namespace_id = azurerm_servicebus_namespace.sb.id

  partitioning_enabled = false
}

resource "azurerm_servicebus_topic" "blob_created" {
  name         = var.airlock_blob_created_topic_name
  namespace_id = azurerm_servicebus_namespace.sb.id

  partitioning_enabled = false
}

resource "azurerm_servicebus_subscription" "airlock_processor" {
  name               = var.airlock_blob_created_al_processor_subscription_name
  topic_id           = azurerm_servicebus_topic.blob_created.id
  max_delivery_count = 1
}




