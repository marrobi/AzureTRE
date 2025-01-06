output "id" {
  value = azurerm_servicebus_namespace.sb.id
}

output "connection_string" {
  value = azurerm_servicebus_namespace.sb.default_primary_connection_string

}

output "endpoint" {
  value = azurerm_servicebus_namespace.sb.endpoint
}
