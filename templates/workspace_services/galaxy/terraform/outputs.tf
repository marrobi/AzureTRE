output "connection_uri" {
  value = "https://${azurerm_linux_web_app.galaxy_proxy.default_hostname}/"
}

output "workspace_address_space" {
  value = jsonencode(data.azurerm_virtual_network.ws.address_space)
}

output "is_exposed_externally" {
  value = false
}
