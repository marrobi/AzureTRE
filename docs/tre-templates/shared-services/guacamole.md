# Guacamole Shared Service

Apache Guacamole is a clientless remote desktop gateway that provides browser-based access to virtual machines. It is available both as a per-workspace [workspace service](../workspace-services/guacamole.md) and as a **shared service** that runs a single Guacamole instance able to serve virtual machines across multiple workspaces.

The shared service is useful when you want to run one Guacamole deployment for the whole TRE instead of one per workspace, reducing the number of App Service instances that need to be operated.

## How it differs from the workspace service

The per-workspace Guacamole service authenticates every user against a single workspace's Microsoft Entra application registration using OAuth2 Proxy. A shared instance has to authenticate users against *any* workspace, so it uses a **dynamic, dual user token** authentication flow implemented in the bundled Guacamole authentication extension:

1. **Workspace selection** – the target workspace is identified from the request, either via the `X-Workspace-Id` header or by extracting the workspace ID from the request URI (for example `/guacamole/{workspace_id}/`).
1. **Core API token** – the user's TRE Core API token (passed in the `X-Core-Api-Token` header) is used to call `GET /api/workspaces/{workspace_id}` and retrieve that workspace's authentication configuration (client ID, issuer and JWKS endpoint).
1. **Workspace token** – the user's workspace-scoped token (passed in the `X-Forwarded-Access-Token` header) is then validated against the workspace-specific OAuth2 configuration fetched in the previous step.

Because both tokens are the user's own tokens, the shared service does **not** require any managed identity permissions on the Core API.

Once authenticated, the extension queries the Core API for the Guacamole workspace services in the resolved workspace and aggregates their user-resource virtual machines to build the list of available connections. The per-workspace Guacamole [workspace service](../workspace-services/guacamole.md) is still used to create those user-resource VMs.

## Deploy

To deploy this shared service you should use the UI (or the API) to issue a request. If you don't see the option available for this specific template make sure it has been built, published and registered by the TRE Admin.

## Configuration

The following properties can be set when deploying the shared service (see `template_schema.json` for the full list):

| Property | Description | Default |
| --- | --- | --- |
| `guac_disable_copy` | Disable copying from the remote clipboard. | `true` |
| `guac_disable_paste` | Disable pasting to the remote clipboard. | `false` |
| `guac_enable_drive` | Enable the virtual transfer drive. | `false` |
| `guac_disable_download` | Disable file download from the remote VM. | `true` |
| `guac_disable_upload` | Disable file upload to the remote VM. | `true` |
| `guac_server_layout` | Keyboard layout for the Guacamole server. | `en-us-qwerty` |

## Network exposure

!!! warning
    The shared Guacamole web app is deployed with a private endpoint and is not exposed externally by the bundle itself. Routing external traffic (for example a path-based Application Gateway rule for `/guacamole/{workspace_id}/` that supplies the required `X-Core-Api-Token` and `X-Forwarded-Access-Token` headers) must be configured for your environment before end users can reach the service.
