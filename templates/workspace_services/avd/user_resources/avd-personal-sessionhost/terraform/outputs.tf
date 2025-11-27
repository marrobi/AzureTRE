output "ip" {
  value = azurerm_network_interface.sessionhost.private_ip_address
}

output "hostname" {
  value = azurerm_windows_virtual_machine.sessionhost.name
}

output "azure_resource_id" {
  value = azurerm_windows_virtual_machine.sessionhost.id
}

output "connection_uri" {
  value = "https://client.wvd.microsoft.com/arm/webclient/index.html"
}

output "vm_username" {
  value = local.admin_username
}

output "vm_password_secret_name" {
  value = local.vm_password_secret_name
}

output "keyvault_name" {
  value = local.keyvault_name
}
