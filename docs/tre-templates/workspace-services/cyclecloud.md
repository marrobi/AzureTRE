# CycleCloud Shared Service

Azure CycleCloud is an enterprise-friendly tool for orchestrating and managing High Performance Computing (HPC) environments on Azure. With CycleCloud, users can provision infrastructure for HPC systems, deploy familiar HPC schedulers, and automatically scale the infrastructure to run jobs efficiently at any scale. Through CycleCloud, users can create different types of file systems and mount them to the compute cluster nodes to support HPC workloads.

Documentation on CycleCloud can be found here: [https://docs.microsoft.com/en-us/azure/cyclecloud/](https://docs.microsoft.com/en-us/azure/cyclecloud/).

This CycleCloud workspace service provide a very basic deployment of CycleCloud into a workspace For any advanced scenarios these templates will need extending.

## Getting Started

1. Deploy the CycleCloud workspace service.
2. Connect to the CycleCloud admin console using the `connection_uri` property, or clickign connect in the TRE UI.
3. Log into the admin console using instructions here [https://docs.microsoft.com/en-us/azure/cyclecloud/qs-install-marketplace?view=cyclecloud-8#log-into-the-cyclecloud-application-server](https://docs.microsoft.com/en-us/azure/cyclecloud/qs-install-marketplace?view=cyclecloud-8#log-into-the-cyclecloud-application-server).
4. 

## Network requirements

Gitea needs to be able to access the following resource outside the Azure TRE VNET via explicitly allowed [Service Tags](https://docs.microsoft.com/en-us/azure/virtual-network/service-tags-overview) or URLs.

| Service Tag / Destination | Justification |
| --- | --- |
| AzureActiveDirectory | Authorize the signed in user against Azure Active Directory. |
| AzureContainerRegistry | Pull the Gitea container image, as it is located in Azure Container Registry.  |
| (www.)github.com | Allows Gitea to mirror any repo on GitHub |
