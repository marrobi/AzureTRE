resource "azurerm_batch_account" "nf" {
  name                          = local.batch_account_name
  location                      = data.azurerm_resource_group.ws.location
  resource_group_name           = data.azurerm_resource_group.ws.name
  pool_allocation_mode          = "BatchService"
  public_network_access_enabled = false
  allowed_authentication_modes  = ["AAD"]
  tags                          = local.workspace_service_tags

  lifecycle { ignore_changes = [tags] }
}

# batchAccount serves the Batch API to the portal and head; nodeManagement lets nodes reach Batch privately.
resource "azurerm_private_endpoint" "batch" {
  for_each            = toset(["batchAccount", "nodeManagement"])
  name                = "pe-${lower(each.value)}-${local.batch_account_name}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  subnet_id           = data.azurerm_subnet.services.id
  tags                = local.workspace_service_tags

  private_service_connection {
    name                           = "psc-${lower(each.value)}-${local.batch_account_name}"
    private_connection_resource_id = azurerm_batch_account.nf.id
    subresource_names              = [each.value]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "private-dns-zone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.batch.id]
  }

  depends_on = [azurerm_private_dns_zone_virtual_network_link.batch]

  lifecycle { ignore_changes = [tags] }
}

locals {
  # Scale on pending and running tasks, then back to zero; nodes are only removed once their tasks finish.
  autoscale_formula = <<-EOT
    $samples = $PendingTasks.GetSamplePercent(TimeInterval_Minute * 5);
    $tasks = $samples < 70 ? max(0, $PendingTasks.GetSample(1)) : max($PendingTasks.GetSample(1), avg($PendingTasks.GetSample(TimeInterval_Minute * 5)));
    $target = min(%MAX%, $tasks);
    $%TARGET% = $target;
    $NodeDeallocationOption = taskcompletion;
  EOT
  pool_image = {
    publisher = "microsoft-dsvm"
    offer     = "ubuntu-hpc"
    sku       = "2404"
  }
}

resource "azurerm_batch_pool" "head" {
  name                           = local.head_pool_id
  display_name                   = "Nextflow head processes"
  resource_group_name            = data.azurerm_resource_group.ws.name
  account_name                   = azurerm_batch_account.nf.name
  vm_size                        = var.head_vm_size
  node_agent_sku_id              = "batch.node.ubuntu 24.04"
  max_tasks_per_node             = 2
  target_node_communication_mode = "Simplified"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.head.id]
  }

  storage_image_reference {
    publisher = local.pool_image.publisher
    offer     = local.pool_image.offer
    sku       = local.pool_image.sku
    version   = "latest"
  }

  container_configuration {
    type                  = "DockerCompatible"
    container_image_names = [local.runtime_image]
    container_registries = [{
      registry_server           = data.azurerm_container_registry.mgmt_acr.login_server
      user_assigned_identity_id = azurerm_user_assigned_identity.head.id
      user_name                 = null
      password                  = null
    }]
  }

  auto_scale {
    evaluation_interval = "PT5M"
    formula             = replace(replace(local.autoscale_formula, "%MAX%", var.head_max_nodes), "%TARGET%", "TargetDedicatedNodes")
  }

  network_configuration {
    subnet_id                        = azurerm_subnet.batch.id
    public_address_provisioning_type = "NoPublicIPAddresses"
  }

  task_scheduling_policy {
    node_fill_type = "Pack"
  }

  depends_on = [
    azurerm_role_assignment.acr_pull,
    azurerm_private_endpoint.batch,
    azurerm_subnet_network_security_group_association.batch,
    azurerm_subnet_route_table_association.batch,
  ]
}

resource "azurerm_batch_pool" "worker" {
  name                           = local.worker_pool_id
  display_name                   = "Nextflow pipeline tasks"
  resource_group_name            = data.azurerm_resource_group.ws.name
  account_name                   = azurerm_batch_account.nf.name
  vm_size                        = var.worker_vm_size
  node_agent_sku_id              = "batch.node.ubuntu 24.04"
  max_tasks_per_node             = local.worker_vcpus
  target_node_communication_mode = "Simplified"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.worker.id]
  }

  storage_image_reference {
    publisher = local.pool_image.publisher
    offer     = local.pool_image.offer
    sku       = local.pool_image.sku
    version   = "latest"
  }

  container_configuration {
    type                  = "DockerCompatible"
    container_image_names = [local.runtime_image]
    container_registries = [{
      registry_server           = data.azurerm_container_registry.mgmt_acr.login_server
      user_assigned_identity_id = azurerm_user_assigned_identity.worker.id
      user_name                 = null
      password                  = null
    }]
  }

  start_task {
    command_line       = "/bin/bash -c 'echo ${base64encode(file("${path.module}/worker_start_task.sh"))} | base64 -d > /tmp/nf-start-task.sh && bash /tmp/nf-start-task.sh'"
    wait_for_success   = true
    task_retry_maximum = 2
    common_environment_properties = {
      NF_RUNTIME_IMAGE = local.runtime_image
      NF_NEXUS_URL     = local.nexus_proxy_url
    }
    user_identity {
      auto_user {
        elevation_level = "Admin"
        scope           = "Pool"
      }
    }
  }

  auto_scale {
    evaluation_interval = "PT5M"
    formula = replace(replace(local.autoscale_formula, "%MAX%", var.worker_max_nodes), "%TARGET%",
    var.worker_use_spot ? "TargetLowPriorityNodes" : "TargetDedicatedNodes")
  }

  network_configuration {
    subnet_id                        = azurerm_subnet.batch.id
    public_address_provisioning_type = "NoPublicIPAddresses"
  }

  task_scheduling_policy {
    node_fill_type = "Pack"
  }

  depends_on = [
    azurerm_role_assignment.acr_pull,
    azurerm_private_endpoint.batch,
    azurerm_subnet_network_security_group_association.batch,
    azurerm_subnet_route_table_association.batch,
  ]
}
