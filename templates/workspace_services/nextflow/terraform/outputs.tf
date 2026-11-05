output "connection_uri" {
  value = "https://${azurerm_linux_web_app.portal.default_hostname}/"
}

output "authentication_callback_uri" {
  value = "https://${azurerm_linux_web_app.portal.default_hostname}/auth/callback"
}

output "workspace_address_spaces" {
  value = data.azurerm_virtual_network.ws.address_space
}

output "is_exposed_externally" {
  value = false
}

# Sign-in needs Microsoft Entra ID from the portal (token exchange) and from workspace VMs (the user's browser).
# The Batch subnet is deliberately excluded: pipeline code never needs to sign in.
output "auth_source_addresses" {
  value = concat(data.azurerm_subnet.web_apps.address_prefixes, data.azurerm_subnet.services.address_prefixes)
}
