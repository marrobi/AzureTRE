# Microsoft Fabric Workspace Service

See: [https://learn.microsoft.com/en-us/fabric/](https://learn.microsoft.com/en-us/fabric/)

This workspace service provisions a dedicated Microsoft Fabric environment within a TRE workspace, including:

- **Fabric Capacity** — an Azure resource providing compute power (configurable SKU from F2 to F2048)
- **Fabric Workspace** — a collaborative analytics environment assigned to the capacity
- **Default Lakehouse** — a pre-provisioned Lakehouse with schema support enabled
- **Workspace-level Private Link** — inbound private endpoint so workspace VMs access Fabric over the private network
- **Managed Private Endpoints** — outbound private endpoints from Fabric to the workspace shared storage account (blob + DFS)

## Network Architecture

All traffic between the TRE workspace and Fabric stays on the private network:

- **Inbound (workspace → Fabric):** A workspace-level private endpoint is created in `ServicesSubnet` using `Microsoft.Fabric/privateLinkServicesForFabric`. DNS resolves via `privatelink.fabric.microsoft.com` zone linked to the workspace VNet.
- **Outbound (Fabric → storage):** Managed private endpoints connect the Fabric workspace to the workspace's shared ADLS Gen2 storage account for both blob and DFS access.
- **No firewall rules required** — all Fabric traffic is routed through private endpoints.

## Prerequisites

- [A base workspace bundle installed](../workspaces/base.md)
- **Fabric must be enabled at the tenant level** by a Fabric Administrator:
    1. Go to the [Fabric Admin Portal](https://app.fabric.microsoft.com/admin-portal)
    2. Navigate to **Tenant Settings** → **Users can create Fabric items**
    3. Enable this setting

    !!! warning
        This step **cannot be automated** via Terraform or APIs. It must be performed manually before deploying this workspace service.

- **Service principals must be allowed to use Fabric APIs** in the [Admin Portal](https://app.fabric.microsoft.com/admin-portal) under **Tenant Settings** → **Developer Settings**:

    | Setting | Required | Status needed |
    | ------- | -------- | ------------- |
    | **Service principals can call Fabric public APIs** | Yes | Enabled |
    | **Service principals can create workspaces, connections, and deployment pipelines** | Yes | Enabled |

    Either apply to the entire organization, or add a security group containing the resource processor VMSS managed identity.

    !!! warning
        Without these settings, managed identities and service principals cannot create Fabric workspaces or call the Fabric API, even if they have the Fabric Administrator Entra ID role.

- **The following Fabric tenant settings must be enabled** by a Fabric Administrator in the [Admin Portal](https://app.fabric.microsoft.com/admin-portal) under **Tenant Settings** → **Network Security**:

    | Setting | Required for | 
    | ------- | ------------ |
    | **Configure workspace-level inbound network rules** | Workspace-level private endpoint (inbound access from workspace VMs to Fabric) |
    | **Configure workspace-level outbound network rules** | Managed private endpoints (outbound access from Fabric to workspace storage) |

    !!! tip
        The **Configure workspace IP firewall rules** setting is optional for this service since access is controlled via private endpoints rather than IP rules.

- The `Microsoft.Fabric` resource provider must be registered on the Azure subscription:
    ```bash
    az provider register --namespace Microsoft.Fabric
    ```
- The **resource processor VMSS managed identity** must have the **Fabric Administrator** Entra ID role so it can call the Fabric API via MSI:
    ```bash
    PRINCIPAL_ID=$(az identity show --name id-vmss-<tre_id> --resource-group rg-<tre_id> --query principalId -o tsv)
    az rest --method POST \
      --url "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments" \
      --headers "Content-Type=application/json" \
      --body "{\"principalId\":\"${PRINCIPAL_ID}\",\"roleDefinitionId\":\"a9ea8996-122f-4c74-9520-8edcd192826c\",\"directoryScopeId\":\"/\"}"
    ```

## Configuration

### Required Properties

| Property | Options | Description |
| -------- | ------- | ----------- |
| `fabric_capacity_sku` | `F2`, `F4`, `F8`, `F16`, `F32`, `F64`, `F128`, `F256`, `F512`, `F1024`, `F2048` (Default: `F2`) | The SKU tier for the Fabric capacity. Larger SKUs provide more compute power but cost more. Can be changed after deployment to scale up or down. |

### Optional Properties

| Property | Options | Description |
| -------- | ------- | ----------- |
| `is_exposed_externally` | `true`/`false` (Default: `false`) | Whether the Fabric workspace is accessible from outside the workspace network |

## Managed Private Endpoint Approval

After deployment, the managed private endpoints (blob and DFS) targeting the workspace storage account will be in a **Pending** state. They must be approved before Fabric Spark workloads can access workspace storage:

1. Navigate to the workspace storage account in the Azure Portal
2. Go to **Networking** → **Private endpoint connections**
3. Find the pending connections from the Fabric workspace
4. Select and **Approve** them

If the deploying service principal has `Microsoft.Storage/storageAccounts/privateEndpointConnectionsApproval/action` permission on the storage account, approval may happen automatically.

## Restricting Public Access

The workspace-level private endpoint provides a private network path but does **not** automatically block public internet access to the Fabric workspace. Within the TRE, workspace VMs are restricted by the firewall and can only reach Fabric via the private endpoint. However, for defense-in-depth, you should also block public access on the Fabric side.

**Recommended:** After deployment, configure workspace IP firewall rules to block public access:

1. In the Fabric workspace settings, navigate to **Network Security**
2. Set the IP allowlist to empty (no allowed IPs)

This ensures the workspace is only accessible via the private endpoint. See [Fabric IP firewall rules](https://learn.microsoft.com/en-us/fabric/security/security-private-links-use) for details.

!!! note
    There is currently no Terraform resource to automate workspace IP firewall rules. This must be configured manually or via the [Fabric REST API](https://learn.microsoft.com/en-us/rest/api/fabric/core/workspaces).

## Accessing Workspace Storage from Fabric

The workspace's shared ADLS Gen2 storage account is accessible from Fabric via the managed private endpoints provisioned by this service. Researchers can read and write data using Spark notebooks with `abfss://` URIs — see [Access Azure Data Lake Storage Gen2 from Fabric](https://learn.microsoft.com/en-us/fabric/onelake/access-onelake-shortcuts#azure-data-lake-storage-gen2).

!!! note
    OneLake shortcuts to ADLS Gen2 are **not supported** through managed private endpoints ([details](https://learn.microsoft.com/en-us/fabric/security/security-managed-private-endpoints-overview)). Use Spark notebooks or Data Pipelines to load data from workspace storage into the Lakehouse instead.

## Known Limitations

- **OneLake shortcuts to ADLS Gen2 do not work through managed private endpoints.** This is a [documented Fabric limitation](https://learn.microsoft.com/en-us/fabric/security/security-managed-private-endpoints-overview). Spark notebooks and other compute workloads can access storage directly via the managed PEs.
- **Newly created capacity** may take up to 24 hours before the workspace private endpoint is fully functional.
- The `fabric_workspace_managed_private_endpoint` and `fabric_lakehouse` Terraform resources are in **preview** in the Microsoft Fabric Terraform provider.
- Fabric capacity is billed per hour. Consider scaling down to F2 when not in active use.

## References

- [Microsoft Fabric Terraform Provider](https://registry.terraform.io/providers/microsoft/fabric/latest/docs)
- [Fabric Terraform Quickstart](https://github.com/microsoft/fabric-terraform-quickstart)
- [Workspace-level Private Links](https://learn.microsoft.com/en-us/fabric/security/security-private-links-overview)
- [Managed Private Endpoints](https://learn.microsoft.com/en-us/fabric/security/security-managed-private-endpoints-overview)
- [Fabric Admin Portal Settings](https://learn.microsoft.com/en-us/fabric/admin/fabric-switch)
