output "connection_uri" {
  value = "https://client.wvd.microsoft.com/arm/webclient/index.html"
}

output "hostpool_name" {
  value = azurerm_virtual_desktop_host_pool.avd.name
}

output "workspace_address_spaces" {
  value = jsonencode(data.azurerm_virtual_network.ws.address_space)
}
