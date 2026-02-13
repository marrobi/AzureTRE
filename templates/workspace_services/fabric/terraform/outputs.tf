output "fabric_workspace_name" {
  value = fabric_workspace.researchers.display_name
}

output "fabric_capacity_name" {
  value = azurerm_fabric_capacity.fabric.name
}

output "connection_uri" {
  value = "https://app.fabric.microsoft.com/groups/${fabric_workspace.researchers.id}"
}

output "lakehouse_name" {
  value = fabric_lakehouse.default.display_name
}

output "fabric_workspace_id" {
  value = fabric_workspace.researchers.id
}
