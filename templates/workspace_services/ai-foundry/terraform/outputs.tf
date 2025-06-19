output "ai_foundry_hub_id" {
  value = module.aihub.resource_id
}

output "ai_foundry_project_id" {
  value = module.ai_foundry_project.resource_id
}

output "ai_foundry_fqdn" {
  value = "ai.azure.com"
}

output "connection_uri" {
  value = format("%s?wsid=%s&tid=%s", "https://ai.azure.com/build/overview", module.ai_foundry_project.resource_id, var.arm_tenant_id)
}

output "workspace_address_spaces" {
  value = data.azurerm_virtual_network.ws.address_space
}
