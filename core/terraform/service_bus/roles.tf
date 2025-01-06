resource "azurerm_role_assignment" "servicebus_sender" {
  scope                =  azurerm_servicebus_namespace.sb.id
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = var.api_user_assigned_identity_id
}

resource "azurerm_role_assignment" "servicebus_receiver" {
  scope                = azurerm_servicebus_namespace.sb.id
  role_definition_name = "Azure Service Bus Data Receiver"
  principal_id         = var.api_user_assigned_identity_id
}
