resource "azurerm_network_interface" "sessionhost" {
  name                = "nic-${local.service_resource_name_suffix}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  tags                = local.tre_user_resources_tags

  ip_configuration {
    name                          = "primary"
    subnet_id                     = data.azurerm_subnet.services.id
    private_ip_address_allocation = "Dynamic"
  }

  lifecycle { ignore_changes = [tags] }
}

resource "random_password" "password" {
  length           = 16
  lower            = true
  min_lower        = 1
  upper            = true
  min_upper        = 1
  numeric          = true
  min_numeric      = 1
  special          = true
  min_special      = 1
  override_special = "_%@"
}

resource "azurerm_windows_virtual_machine" "sessionhost" {
  name                       = local.vm_name
  location                   = data.azurerm_resource_group.ws.location
  resource_group_name        = data.azurerm_resource_group.ws.name
  network_interface_ids      = [azurerm_network_interface.sessionhost.id]
  size                       = local.vm_sizes[var.vm_size]
  allow_extension_operations = true
  admin_username             = local.admin_username
  admin_password             = random_password.password.result
  encryption_at_host_enabled = true
  secure_boot_enabled        = local.secure_boot_enabled
  vtpm_enabled               = local.vtpm_enabled
  license_type               = "Windows_Client"

  dynamic "source_image_reference" {
    for_each = local.selected_image_source_refs
    content {
      publisher = source_image_reference.value["publisher"]
      offer     = source_image_reference.value["offer"]
      sku       = source_image_reference.value["sku"]
      version   = source_image_reference.value["version"]
    }
  }

  os_disk {
    name                 = "osdisk-${local.vm_name}"
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
  }

  identity {
    type = "SystemAssigned"
  }

  tags = local.tre_user_resources_tags

  lifecycle { ignore_changes = [tags, secure_boot_enabled, vtpm_enabled, admin_username, os_disk[0].storage_account_type] }
}

# AVD Agent extension to join the session host to the host pool
resource "azurerm_virtual_machine_extension" "avd_dsc" {
  name                       = "Microsoft.PowerShell.DSC"
  virtual_machine_id         = azurerm_windows_virtual_machine.sessionhost.id
  publisher                  = "Microsoft.Powershell"
  type                       = "DSC"
  type_handler_version       = "2.73"
  auto_upgrade_minor_version = true
  tags                       = local.tre_user_resources_tags

  settings = <<SETTINGS
    {
      "modulesUrl": "https://wvdportalstorageblob.blob.core.windows.net/galleryartifacts/Configuration_1.0.02775.450.zip",
      "configurationFunction": "Configuration.ps1\\AddSessionHost",
      "properties": {
        "hostPoolName": "${data.azurerm_virtual_desktop_host_pool.avd.name}",
        "aadJoin": true
      }
    }
  SETTINGS

  protected_settings = <<PROTECTED_SETTINGS
    {
      "properties": {
        "registrationInfoToken": "${data.azurerm_key_vault_secret.avd_registration_token.value}"
      }
    }
  PROTECTED_SETTINGS

  lifecycle { ignore_changes = [tags, settings] }

  depends_on = [azurerm_windows_virtual_machine.sessionhost]
}

# AAD Join extension for Microsoft Entra ID authentication
resource "azurerm_virtual_machine_extension" "aad_join" {
  name                       = "AADLoginForWindows"
  virtual_machine_id         = azurerm_windows_virtual_machine.sessionhost.id
  publisher                  = "Microsoft.Azure.ActiveDirectory"
  type                       = "AADLoginForWindows"
  type_handler_version       = "2.2"
  auto_upgrade_minor_version = true
  tags                       = local.tre_user_resources_tags

  lifecycle { ignore_changes = [tags] }

  depends_on = [azurerm_virtual_machine_extension.avd_dsc]
}

resource "azurerm_key_vault_secret" "sessionhost_password" {
  name         = local.vm_password_secret_name
  value        = "${local.admin_username}\n${random_password.password.result}"
  key_vault_id = data.azurerm_key_vault.ws.id
  tags         = local.tre_user_resources_tags

  lifecycle { ignore_changes = [tags] }
}

resource "azurerm_dev_test_global_vm_shutdown_schedule" "shutdown_schedule" {
  count = var.enable_shutdown_schedule ? 1 : 0

  location              = data.azurerm_resource_group.ws.location
  virtual_machine_id    = azurerm_windows_virtual_machine.sessionhost.id
  daily_recurrence_time = var.shutdown_time
  timezone              = var.shutdown_timezone
  enabled               = var.enable_shutdown_schedule
  notification_settings {
    enabled = false
  }
}

# Mount shared storage if enabled
resource "azurerm_virtual_machine_extension" "mount_storage" {
  count                = var.shared_storage_access ? 1 : 0
  name                 = "mount-shared-storage"
  virtual_machine_id   = azurerm_windows_virtual_machine.sessionhost.id
  publisher            = "Microsoft.Compute"
  type                 = "CustomScriptExtension"
  type_handler_version = "1.10"
  tags                 = local.tre_user_resources_tags

  protected_settings = <<PROT
    {
      "commandToExecute": "powershell -ExecutionPolicy Unrestricted -Command \"$connectTestResult = Test-NetConnection -ComputerName '${data.azurerm_storage_account.stg.primary_file_host}' -Port 445; if ($connectTestResult.TcpTestSucceeded) { cmd.exe /C 'cmdkey /add:${data.azurerm_storage_account.stg.primary_file_host} /user:localhost\\${data.azurerm_storage_account.stg.name} /pass:${data.azurerm_storage_account.stg.primary_access_key}'; New-PSDrive -Name Z -PSProvider FileSystem -Root '\\\\${data.azurerm_storage_account.stg.primary_file_host}\\${var.shared_storage_name}' -Persist -Scope Global }\""
    }
  PROT

  lifecycle { ignore_changes = [tags] }

  depends_on = [azurerm_virtual_machine_extension.aad_join]
}
