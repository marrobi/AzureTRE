# Azure TRE base workspace

The base workspace template is the foundation that all other workspaces and workspace services are built upon. Alternative workspace architectures could be used. However, the templates provided in this repository rely on the specific architecture of this base workspace.

The base workspace template contains the following resources:

- Virtual Network
- Storage Account
- Key Vault
- VNet Peer to Core VNet
- Network Security Group
- App Service Plan

## Workspace Configuration

When deploying a workspace the following properties need to be configured.

### Required Properties

| Property | Options | Description |
| -------- | ------- | ----------- |
| `client_id` | Valid client ID of the Workspace App Registration. | The OpenID client ID which should be submitted to the OpenID service when necessary. This value is typically provided to you by the OpenID service when OpenID credentials are generated for your application. |
| `client_secret` | Valid client secret. | |

### Optional Properties

| Property | Options | Description |
| -------- | ------- | ----------- |
| `allowed_workspace_service_templates` | Array of workspace service template names (e.g. `tre-service-guacamole`). | Restricts which workspace service templates can be deployed into the workspace. When omitted or empty, all workspace service templates are allowed. A TRE Admin can set this property when creating the workspace, or update it later, to control which services a Workspace Owner is permitted to deploy. |

## Azure Trusted Services
*Azure Trusted Services* are allowed to connect to both the key vault and storage account provsioned within the workspace. If this is undesirable additonal resources without this setting configured can be deployed.

Further details around which Azure services are allowed to connect can be found below:

- Key Vault: <https://docs.microsoft.com/en-us/azure/key-vault/general/overview-vnet-service-endpoints#trusted-services>
- Azure Storage: <https://docs.microsoft.com/en-us/azure/storage/common/storage-network-security?msclkid=ee4e79e4b97911eca46dae54da464d11&tabs=azure-portal#trusted-access-for-resources-registered-in-your-subscription>
