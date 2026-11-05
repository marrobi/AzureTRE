resource "azurerm_storage_account" "nf" {
  name                             = local.storage_name
  location                         = data.azurerm_resource_group.ws.location
  resource_group_name              = data.azurerm_resource_group.ws.name
  account_tier                     = "Standard"
  account_replication_type         = "LRS"
  min_tls_version                  = "TLS1_2"
  https_traffic_only_enabled       = true
  allow_nested_items_to_be_public  = false
  cross_tenant_replication_enabled = false
  shared_access_key_enabled        = false
  default_to_oauth_authentication  = true
  tags                             = local.workspace_service_tags

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }

  # changing this value is destructive, hence attribute is in lifecycle.ignore_changes block below
  infrastructure_encryption_enabled = true

  lifecycle { ignore_changes = [infrastructure_encryption_enabled, tags] }
}

resource "azurerm_storage_container" "nf" {
  for_each              = toset(local.storage_containers)
  name                  = each.value
  storage_account_id    = azurerm_storage_account.nf.id
  container_access_type = "private"
}

resource "azurerm_storage_management_policy" "nf" {
  storage_account_id = azurerm_storage_account.nf.id

  rule {
    name    = "expire-nextflow-work"
    enabled = true
    filters {
      prefix_match = ["work/"]
      blob_types   = ["blockBlob"]
    }
    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = var.work_retention_days
      }
    }
  }
}

resource "azurerm_private_endpoint" "blob" {
  name                = "pe-blob-${local.storage_name}"
  location            = data.azurerm_resource_group.ws.location
  resource_group_name = data.azurerm_resource_group.ws.name
  subnet_id           = data.azurerm_subnet.services.id
  tags                = local.workspace_service_tags

  private_service_connection {
    name                           = "psc-blob-${local.storage_name}"
    private_connection_resource_id = azurerm_storage_account.nf.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "private-dns-zone-group"
    private_dns_zone_ids = [data.azurerm_private_dns_zone.blobcore.id]
  }

  lifecycle { ignore_changes = [tags] }
}
