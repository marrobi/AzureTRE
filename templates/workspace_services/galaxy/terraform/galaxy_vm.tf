resource "random_password" "galaxy_admin_passwd" {
  length      = 20
  min_upper   = 2
  min_lower   = 2
  min_numeric = 2
  min_special = 2
}

resource "azurerm_network_interface" "galaxy_vm" {
  name                = "nic-${local.vm_name}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  tags                = local.workspace_service_tags

  ip_configuration {
    name                          = "primary"
    subnet_id                     = data.azurerm_subnet.services.id
    private_ip_address_allocation = "Dynamic"
  }

  lifecycle { ignore_changes = [tags] }
}

data "cloudinit_config" "galaxy_config" {
  gzip          = true
  base64_encode = true

  part {
    content_type = "text/x-shellscript"
    content      = local.get_apt_keys_content
  }

  part {
    content_type = "text/cloud-config"
    content      = local.apt_sources_config_content
  }

  part {
    content_type = "text/x-shellscript"
    content      = local.galaxy_vm_config_content
  }
}

resource "azurerm_linux_virtual_machine" "galaxy_vm" {
  name                            = local.vm_name
  location                        = data.azurerm_resource_group.ws.location
  resource_group_name             = data.azurerm_resource_group.ws.name
  network_interface_ids           = [azurerm_network_interface.galaxy_vm.id]
  size                            = var.vm_size
  disable_password_authentication = false
  admin_username                  = "galaxyadmin"
  admin_password                  = random_password.galaxy_admin_passwd.result
  encryption_at_host_enabled      = true
  tags                            = local.workspace_service_tags

  custom_data = data.cloudinit_config.galaxy_config.rendered

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  os_disk {
    name                 = "osdisk-${local.vm_name}"
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb         = 128
  }

  identity {
    type = "SystemAssigned"
  }

  lifecycle { ignore_changes = [tags, custom_data] }
}

resource "azurerm_key_vault_secret" "galaxy_vm_password" {
  name         = "${local.vm_name}-admin-credentials"
  value        = "galaxyadmin\n${random_password.galaxy_admin_passwd.result}"
  key_vault_id = data.azurerm_key_vault.ws.id
  tags         = local.workspace_service_tags

  depends_on = [
    azurerm_role_assignment.keyvault_galaxy_ws_role
  ]

  lifecycle { ignore_changes = [tags] }
}
