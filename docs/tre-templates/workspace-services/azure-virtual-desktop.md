# Azure Virtual Desktop Service bundle

See: [https://azure.microsoft.com/services/virtual-desktop/](https://azure.microsoft.com/services/virtual-desktop/)

This service deploys Azure Virtual Desktop (AVD) infrastructure into a workspace, enabling secure remote desktop access via personal host pools.

## Features

- **Personal Host Pools**: One VM per user with automatic assignment
- **Private Endpoints**: All AVD traffic uses private endpoints to prevent data exfiltration
- **External Identity Support**: Works with external identities via Microsoft Entra ID
- **Start VM on Connect**: VMs automatically start when users connect to save costs
- **Diagnostics**: Full logging to Log Analytics workspace

## Architecture

The service deploys the following resources:

- **AVD Host Pool**: Personal type with persistent load balancing
- **AVD Workspace**: For organizing and publishing desktops
- **Desktop Application Group**: Provides access to the full desktop
- **Private Endpoints**: For host pool connections and workspace feed

## Firewall Rules

The following firewall rules are opened for the workspace when this service is deployed:

Service Tags:

- WindowsVirtualDesktop
- AzureActiveDirectory
- AzureMonitor

## Prerequisites

- [A base workspace bundle installed](../workspaces/base.md)

## User Resources

This workspace service includes the following user resources:

- **AVD Personal Session Host**: Windows VM that serves as a personal session host

## Connecting to Azure Virtual Desktop

Users can connect to their virtual desktops using:

1. **Web Client**: [https://client.wvd.microsoft.com](https://client.wvd.microsoft.com)
2. **Windows Desktop Client**: Download from [Microsoft Store](https://aka.ms/wvd/clients/windows)
3. **macOS Client**: Download from [Mac App Store](https://aka.ms/wvd/clients/mac)

For more information, see the [Azure Virtual Desktop documentation](https://learn.microsoft.com/en-us/azure/virtual-desktop/).
