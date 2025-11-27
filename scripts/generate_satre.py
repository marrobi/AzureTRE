import pathlib

from typing import Dict, List

TEMPLATE_PATH = pathlib.Path("/workspaces/marrobi-azuretre/docs/azure-tre-overview/satre-template.md")
OUTPUT_PATH = pathlib.Path("/workspaces/marrobi-azuretre/docs/azure-tre-overview/satre.md")


def sanitize(item: str) -> str:
    return item.strip().rstrip('.')


def join_bullets(values: List[str]) -> str:
    return "<br>".join(values)


def main() -> None:
    overrides: Dict[str, Dict[str, List[str] | str]] = {
        "1.5.1": {
            "score": "Partially supported",
            "response": [
                "- All TRE entry points rely on Microsoft Entra ID, so you can enforce MFA/Conditional Access before issuing credentials (https://learn.microsoft.com/entra/identity/authentication/concept-mfa-howitworks).",
                "- Not part of accelerator; however, Entra ID Identity Governance access packages let sponsors validate identity evidence before users are assigned to TRE Enterprise Apps (https://learn.microsoft.com/entra/id-governance/entitlement-management-overview).",
            ],
            "improvements": [
                "- Store the offline ID-proofing artefacts with each Entra access package request to evidence accreditation decisions.",
            ],
        },
        "1.5.2": {
            "score": "Partially supported",
            "response": [
                "- `make auth` provisions dedicated Entra Enterprise Applications and app roles per TRE role, giving you a structured onboarding path (https://microsoft.github.io/AzureTRE/latest/tre-admins/auth/).",
                "- Not part of accelerator; however, Microsoft Entra ID access packages can bundle prerequisite training approvals before a user receives a TRE role assignment (https://learn.microsoft.com/entra/id-governance/entitlement-management-access-package-overview).",
            ],
            "improvements": [
                "- Capture evidence of training completion or terms-of-use acceptance inside each onboarding workflow.",
            ],
        },
        "1.5.3": {
            "score": "Partially supported",
            "response": [
                "- Identity enforcement uses Microsoft Entra ID app registrations per workspace/service via `make auth`, delivering RBAC separation (https://microsoft.github.io/AzureTRE/latest/tre-admins/auth/).",
                "- Azure TRE user roles map to TRE Admin, Workspace Owner, Researcher, etc., so the API enforces least-privilege scopes (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/user-roles/).",
                "- Architecture isolates services per workspace VNet/resource group, so identities can only reach resources they own (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/architecture/).",
            ],
            "improvements": [
                "- Integrate Entra role assignments with organizational joiner/mover/leaver reviews and document Data Controller approvals per project.",
            ],
        },
        "1.5.4": {
            "score": "Partially supported",
            "response": [
                "- Airlock import/export approvals are limited to workspace owners and Airlock Managers, so Data Controllers can delegate dataset access deliberately (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
                "- The Airlock workflow records every decision for audit, giving Data Controllers assurance that approvals followed policy (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
            ],
            "improvements": [
                "- Maintain documented Data Controller delegations and tie them to the corresponding Airlock role assignments.",
            ],
        },
        "1.5.5": {
            "score": "Partially supported",
            "response": [
                "- Auth automation provisions confidential clients and relies on Entra-issued tokens so tenant-wide MFA/conditional access applies to all TRE entry points (https://microsoft.github.io/AzureTRE/latest/tre-admins/auth/).",
                "- Access to UI/API/Guacamole is only over HTTPS behind Azure AD, eliminating local/shared passwords for TRE components.",
            ],
            "improvements": [
                "- Enforce phishing-resistant MFA and conditional access policies plus periodic access reviews in the customer tenant.",
            ],
        },
        "1.5.6": {
            "score": "Supported",
            "response": [
                "- Each user signs in with their own Entra ID identity and is assigned app roles via Enterprise Applications; no shared logons are created (https://microsoft.github.io/AzureTRE/latest/tre-admins/auth/).",
                "- Role memberships and approvals remain auditable because everything maps to a unique user object ID (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/user-roles/).",
            ],
            "improvements": [
                "- Connect TRE role assignments to HR feeds to auto-disable access when researchers leave a study.",
            ],
        },
        "2.1.1": {
            "score": "Supported",
            "response": [
                "- Guacamole workspace service exposes `guac_disable_copy`, `guac_disable_download`, etc., defaulting to blocking outbound clipboard/file transfer (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspace-services/guacamole/).",
                "- Deployment guidance shows how admins enforce those parameters when publishing workspace services (https://github.com/microsoft/AzureTRE/blob/main/docs/tre-admins/setup-instructions/installing-workspace-service-and-user-resource.md).",
            ],
            "improvements": [
                "- Validate any custom workspace services follow the same clipboard/file-transfer restrictions before onboarding.",
            ],
        },
        "2.1.2": {
            "score": "Supported",
            "response": [
                "- Template catalog ships Windows/Linux desktops plus Azure ML, Databricks, OHDSI, OpenAI, etc., matching familiar research stacks (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspace-services/).",
                "- Guacamole VMs expose full desktop environments reachable via a browser (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspace-services/guacamole/).",
            ],
            "improvements": [
                "- Add additional templates for domain-specific workloads (e.g., CAD, genomics) as demand grows.",
            ],
        },
        "2.1.4": {
            "score": "Supported",
            "response": [
                "- Researchers reach the TRE portal and remote desktops via standard HTTPS browsers; no bespoke client install is needed (https://microsoft.github.io/AzureTRE/latest/using-tre/tre-for-research/using-vms/).",
                "- Automation integrates through documented REST APIs and Swagger UI (https://microsoft.github.io/AzureTRE/latest/tre-developers/api/).",
            ],
            "improvements": [
                "- Perform accessibility/usability testing for the organization’s supported browsers.",
            ],
        },
        "2.1.5": {
            "score": "Supported",
            "response": [
                "- Researcher guides explain how to create VMs, manage services, and operate inside the TRE (https://microsoft.github.io/AzureTRE/latest/using-tre/tre-for-research/using-vms/).",
                "- Airlock docs walk Airlock Managers through ingress/egress reviews and manual validation (https://microsoft.github.io/AzureTRE/latest/using-tre/tre-for-research/review-airlock-request/).",
            ],
            "improvements": [
                "- Layer organization-specific SOPs, videos, or onboarding sessions onto the published guidance.",
            ],
        },
        "2.1.6": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Update Manager can orchestrate recurring OS and application security patches for the Azure VMs hosting workspaces (https://learn.microsoft.com/azure/update-manager/overview).",
                "- Not part of accelerator; however, Azure Automanage for Virtual Machines enforces baseline update configurations for Windows and Linux desktops deployed via TRE templates (https://learn.microsoft.com/azure/automanage/automanage-virtual-machines-overview).",
            ],
            "improvements": [
                "- Define maintenance windows and validation steps before enabling automatic patch deployment per workspace.",
            ],
        },
        "2.1.7": {
            "score": "Supported",
            "response": [
                "- Shared services like Nexus (package proxy) and Gitea (git mirror) are deployed centrally but scoped to TRE projects (https://microsoft.github.io/AzureTRE/latest/tre-templates/shared-services/nexus/).",
                "- Workspace services/user resources live inside workspace resource groups, so only members of that workspace can consume them (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspaces/base/).",
            ],
            "improvements": [
                "- Document an approval path for enabling new shared services per project/data type.",
            ],
        },
        "2.1.8": {
            "score": "Supported",
            "response": [
                "- Hub-spoke networking plus `nsg-ws` rules block traffic between workspace VNets, preventing cross-project sharing (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
                "- Each workspace has its own Entra application/API, so tokens issued for one project cannot call another’s endpoints (https://microsoft.github.io/AzureTRE/latest/tre-admins/auth/).",
            ],
            "improvements": [
                "- Automate periodic NSG/UDR compliance checks within the customer subscription.",
            ],
        },
        "2.1.9": {
            "score": "Partially supported",
            "response": [
                "- Outbound internet access is denied by Azure Firewall unless administrators explicitly allow software license endpoints, limiting telemetry exposure (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
                "- Not part of accelerator; however, Azure Network Watcher traffic analytics can log any approved outbound FQDNs, providing evidence of what telemetry leaves the TRE (https://learn.microsoft.com/azure/network-watcher/traffic-analytics).",
            ],
            "improvements": [
                "- Require vendors to document telemetry payloads and review firewall logs before permitting new endpoints.",
            ],
        },
        "2.1.10": {
            "score": "Supported",
            "response": [
                "- Catalog includes Azure ML, Databricks, Azure SQL, OpenAI, Guacamole VMs, OHDSI, etc., covering common data tooling (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspace-services/).",
                "- Admins can extend templates with bespoke stacks using the documented Porter authoring model (https://microsoft.github.io/AzureTRE/latest/tre-workspace-authors/authoring-workspace-templates/).",
            ],
            "improvements": [
                "- Maintain a living map of datasets to recommended workspace services/software.",
            ],
        },
        "2.1.11": {
            "score": "Supported",
            "response": [
                "- Gitea shared service offers an internal git forge for version-controlled code and notebooks (https://microsoft.github.io/AzureTRE/latest/tre-templates/shared-services/gitea/).",
                "- Templates and deployment automation are stored in Git/Porter bundles, enabling reproducible environment rebuilds (https://github.com/microsoft/AzureTRE/tree/main/templates).",
            ],
            "improvements": [
                "- Encourage projects to adopt tagging/branching conventions or CI pipelines for reproducibility.",
            ],
        },
        "2.1.12": {
            "score": "Supported",
            "response": [
                "- Nexus proxy exposes curated PyPI, Conda, Docker, CRAN, VS Code, etc., letting users install approved public packages without direct internet (https://microsoft.github.io/AzureTRE/latest/tre-templates/shared-services/nexus/).",
                "- Built-in Linux and Windows Guacamole VMs are preconfigured to use the Nexus endpoints, keeping installs within the TRE boundary (same reference).",
            ],
            "improvements": [
                "- Define governance for onboarding new upstream feeds and monitoring mirror health.",
            ],
        },
        "2.1.13": {
            "score": "Supported",
            "response": [
                "- Nexus content selectors/allow-lists let admins restrict which packages and versions appear inside the TRE (https://microsoft.github.io/AzureTRE/latest/tre-templates/shared-services/nexus/).",
                "- Workspace VNets only reach approved mirrors via the firewall, preventing arbitrary internet installs (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
            ],
            "improvements": [
                "- Implement change control for approving additional repositories or relaxing mirrors.",
            ],
        },
        "2.1.14": {
            "score": "Partially supported",
            "response": [
                "- Non-standard compute like CycleCloud clusters are deployed into workspace subnets with controlled NSGs/UDRs (https://microsoft.github.io/AzureTRE/latest/tre-templates/shared-services/cyclecloud/).",
                "- Workspace VNets can be reprovisioned via Porter bundles, ensuring clean nodes between allocations.",
            ],
            "improvements": [
                "- Add automated node sanitization attestations for regulated workloads or external HPC integrations.",
            ],
        },
        "2.1.15": {
            "score": "Supported",
            "response": [
                "- CycleCloud shared service orchestrates HPC clusters tied to TRE networks for burst or large jobs (https://microsoft.github.io/AzureTRE/latest/tre-templates/shared-services/cyclecloud/).",
                "- Azure ML workspace service exposes autoscaling compute pools for analytics workloads (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspace-services/azure-ml/).",
            ],
            "improvements": [
                "- Define process for requesting/approving HPC quotas and tracking their cost recovery.",
            ],
        },
        "2.1.16": {
            "score": "Partially supported",
            "response": [
                "- User-resource templates allow admins to expose GPU VM sizes/custom gallery images when required (https://microsoft.github.io/AzureTRE/latest/tre-templates/user-resources/custom/).",
                "- Azure ML workspace service supports GPU-backed compute clusters inside TRE VNets (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspace-services/azure-ml/).",
            ],
            "improvements": [
                "- Pre-create GPU-enabled templates with documented approval and quota management steps.",
            ],
        },
        "2.1.17": {
            "score": "Supported",
            "response": [
                "- Workspace services exist for Azure SQL, MySQL, OHDSI, and other database platforms to host project data (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspace-services/azuresql/).",
                "- Each service deploys into the owning workspace’s resource group/VNet, isolating access to that project.",
            ],
            "improvements": [
                "- Layer database-specific auditing/data-masking policies per project.",
            ],
        },
        "2.1.18": {
            "score": "Supported",
            "response": [
                "- Azure Databricks workspace service integrates Spark clusters under TRE network controls (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspace-services/databricks/).",
                "- Azure ML pipelines and compute clusters handle large-scale processing inside private VNets (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspace-services/azure-ml/).",
            ],
            "improvements": [
                "- Establish sizing guidance and cost alerts for distributed compute jobs.",
            ],
        },
        "2.2.1": {
            "score": "Supported",
            "response": [
                "- Deployment docs detail manual Makefile procedures from provider registration through `make all` (https://microsoft.github.io/AzureTRE/latest/tre-admins/setup-instructions/manual-deployment/).",
                "- Prerequisite guidance clarifies tooling/tenant requirements before rollout (https://microsoft.github.io/AzureTRE/latest/tre-admins/setup-instructions/prerequisites/).",
            ],
            "improvements": [
                "- Tailor the runbook with organization-specific approvals and change tickets.",
            ],
        },
        "2.2.2": {
            "score": "Supported",
            "response": [
                "- Infrastructure is defined as Terraform + Porter bundles built/published via Make targets (https://github.com/microsoft/AzureTRE/tree/main/templates).",
                "- GitHub Actions workflow `deploy_tre.yml` automates repeatable deployments (https://microsoft.github.io/AzureTRE/latest/tre-admins/setup-instructions/workflows/).",
            ],
            "improvements": [
                "- Integrate pipeline approvals/tests required by your change-management process.",
            ],
        },
        "2.2.3": {
            "score": "Partially supported",
            "response": [
                "- Upgrading guidance explains how to plan/apply TRE updates and review Terraform plans beforehand (https://microsoft.github.io/AzureTRE/latest/tre-admins/upgrading-tre/).",
                "- CI/CD workflow setup covers service principals, secrets, and scripted deployments for controlled changes (https://microsoft.github.io/AzureTRE/latest/tre-admins/setup-instructions/workflows/).",
            ],
            "improvements": [
                "- Embed the TRE pipeline into the organization’s formal change advisory and rollback documentation.",
            ],
        },
        "2.2.4": {
            "score": "Partially supported",
            "response": [
                "- End-to-end tests (pytest) can be run locally or in CI via `make prepare-for-e2e` before production rollout (https://microsoft.github.io/AzureTRE/latest/tre-developers/end-to-end-tests/).",
                "- Templates and bundles are versioned, enabling validation in a staging TRE before promoting versions.",
            ],
            "improvements": [
                "- Stand up a non-prod TRE mirroring production and wire automated regression tests into CI.",
            ],
        },
        "2.2.5": {
            "score": "Partially supported",
            "response": [
                "- Deployment repo and workflows encourage separate dev/test TRE environments or subscriptions (https://microsoft.github.io/AzureTRE/latest/tre-admins/setup-instructions/workflows/).",
                "- TRE bundles are versioned so admins can promote tested templates between environments.",
            ],
            "improvements": [
                "- Formalize environment promotion and data migration procedures tied to your SDLC.",
            ],
        },
        "2.2.6": {
            "score": "Supported",
            "response": [
                "- `make tre-destroy` removes core resources and tidies lingering assets to enable clean redeployments (https://microsoft.github.io/AzureTRE/latest/tre-admins/tear-down/).",
                "- Workspace/service deletion via API tears down associated resource groups and identities automatically.",
            ],
            "improvements": [
                "- Extend teardown SOPs to include data-retention decisions and certificate revocation.",
            ],
        },
        "2.2.9": {
            "score": "Supported",
            "response": [
                "- Hub-spoke topology with Application Gateway + Azure Firewall enforces ingress/egress policy (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
                "- Firewall can be force-tunneled to enterprise appliances for additional inspection (https://microsoft.github.io/AzureTRE/latest/tre-admins/configure-firewall-force-tunneling/).",
            ],
            "improvements": [
                "- Define customer-specific firewall rule review cadence and change logging.",
            ],
        },
        "2.2.10": {
            "score": "Supported",
            "response": [
                "- Workspace VNets only peer with the TRE core and NSGs deny workspace-to-workspace connectivity (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
                "- Shared services rely on private endpoints and role assignments so only the owning workspace can access them.",
            ],
            "improvements": [
                "- Continuously monitor for accidental peerings/service endpoints outside TRE governance.",
            ],
        },
        "2.2.11": {
            "score": "Supported",
            "response": [
                "- Default routes force outbound traffic through Azure Firewall, which is deny-by-default except for listed service tags (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
                "- Package mirrors and jumpbox are the only components with explicit outbound exceptions, all controlled via Terraform.",
            ],
            "improvements": [
                "- Capture firewall rule reviews in organizational SSP/SOC change logs.",
            ],
        },
        "2.2.12": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Azure Network Watcher can record NSG flow logs and topology changes to spot network misconfigurations (https://learn.microsoft.com/azure/network-watcher/network-watcher-monitoring-overview).",
                "- Not part of accelerator; however, Microsoft Defender for Cloud evaluates Azure networking resources against best practices and surfaces remediation recommendations (https://learn.microsoft.com/azure/defender-for-cloud/defender-for-cloud-introduction).",
            ],
            "improvements": [
                "- Integrate these telemetry sources into your vulnerability management tooling for consolidated reporting.",
            ],
        },
        "2.2.13": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Connection Monitor provides continuous synthetic tests between TRE components to detect routing or DNS drift (https://learn.microsoft.com/azure/network-watcher/connection-monitor-overview).",
                "- Not part of accelerator; however, Azure Monitor alerts can be configured to raise incidents whenever Firewall or NSG logs show unexpected rule changes (https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-overview).",
            ],
            "improvements": [
                "- Define owners and review cadences for the generated network alerts.",
            ],
        },
        "2.2.14": {
            "score": "Partially supported",
            "response": [
                "- Cost API aggregates per-core, per-workspace, and per-service spend so admins can track active resources (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/cost-reporting/).",
                "- TRE UI surfaces cost labels on resource cards, giving visibility into number of workspaces/services in use.",
            ],
            "improvements": [
                "- Augment with activity telemetry (e.g., number of users/datasets) via custom dashboards.",
            ],
        },
        "2.2.16": {
            "score": "Partially supported",
            "response": [
                "- Cost reporting APIs expose per-workspace compute consumption so you can monitor utilization trends (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/cost-reporting/).",
                "- Not part of accelerator; however, data exports plug into Azure Cost Management for deeper usage analytics and forecasting (https://learn.microsoft.com/azure/cost-management-billing/costs/analyze-cost-data).",
            ],
            "improvements": [
                "- Extend collection to capture per-user or per-service telemetry where privacy policies allow.",
            ],
        },
        "2.3.1": {
            "score": "Partially supported",
            "response": [
                "- Cost reporting endpoints provide historical spend to inform project estimates before onboarding (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/cost-reporting/).",
                "- Workspace templates publish required Azure resources/SKUs so administrators can explain capacity/cost up front.",
            ],
            "improvements": [
                "- Build pre-project estimation worksheets that combine TRE costs with dataset handling fees.",
            ],
        },
        "2.3.3": {
            "score": "Partially supported",
            "response": [
                "- API + UI gate workspace/service creation behind role-based approvals, giving TRE admins a process to allocate quotas.",
                "- Workspace templates allow admins to choose VM sizes, SKUs, and optional services per request (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspaces/base/).",
            ],
            "improvements": [
                "- Add formal capacity/queue tracking outside TRE for scarce resources (e.g., GPUs/HPC).",
            ],
        },
        "2.3.4": {
            "score": "Partially supported",
            "response": [
                "- Cost APIs + tagging enforce visibility into spend by workspace/service, enabling budgets/chargeback (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/cost-reporting/).",
                "- Admins can start/stop core services to control baseline spend (`make tre-stop`/`tre-start`) (https://microsoft.github.io/AzureTRE/latest/tre-admins/start-stop/).",
            ],
            "improvements": [
                "- Combine TRE cost data with organizational financial systems for proactive budget alerts.",
            ],
        },
        "2.4.1": {
            "score": "Supported",
            "response": [
                "- Porter/Terraform templates under `templates/**` encode desired configuration for every resource (https://github.com/microsoft/AzureTRE/tree/main/templates).",
                "- Authoring guide documents schema/parameters that capture configuration intent (https://microsoft.github.io/AzureTRE/latest/tre-workspace-authors/authoring-workspace-templates/).",
            ],
            "improvements": [
                "- Capture organization-specific parameter defaults and change history alongside the templates.",
            ],
        },
        "2.4.2": {
            "score": "Supported",
            "response": [
                "- Configuration is applied via Porter actions and Terraform modules executed automatically by the Resource Processor (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/architecture/).",
                "- Make/GitHub workflows orchestrate bundle build/publish/apply steps so environments stay in sync (https://microsoft.github.io/AzureTRE/latest/tre-admins/setup-instructions/workflows/).",
            ],
            "improvements": [
                "- Add drift-detection pipelines (e.g., scheduled plan/apply in check mode) in the customer subscription.",
            ],
        },
        "2.4.3": {
            "score": "Partially supported",
            "response": [
                "- `make plan-core` and Terraform plan guidance let admins verify proposed changes before applying (https://microsoft.github.io/AzureTRE/latest/tre-admins/upgrading-tre/#check-infrastructure-changes-using-a-terraform-plan).",
                "- Porter bundles are idempotent and can be tested in non-prod TREs to validate configuration changes.",
            ],
            "improvements": [
                "- Implement automated compliance tests (e.g., Pester/Inspec) to validate workspace configs post-change.",
            ],
        },
        "2.4.4": {
            "score": "Partially supported",
            "response": [
                "- Resource Processor emits deployment status events and operations can be queried/audited via the API (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/architecture/).",
                "- Admins can rerun bundle upgrades/validations to ensure configuration matches template versions.",
            ],
            "improvements": [
                "- Schedule periodic configuration audits or drift detection scripts in production subscriptions.",
            ],
        },
        "2.4.5": {
            "score": "Supported",
            "response": [
                "- Because everything is infrastructure-as-code, you can redeploy a clean TRE/workspace from source templates to replace non-compliant instances quickly (https://microsoft.github.io/AzureTRE/latest/tre-admins/tear-down/).",
                "- Porter bundles support upgrade/repair actions, letting admins remediate drift without manual steps (https://microsoft.github.io/AzureTRE/latest/tre-admins/upgrading-resources/).",
            ],
            "improvements": [
                "- Combine redeploy scripts with documented data backup/restore procedures for regulated datasets.",
            ],
        },
        "2.5.1": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Azure Backup protects TRE storage accounts, managed disks, and databases when retention is allowed (https://learn.microsoft.com/azure/backup/backup-overview).",
                "- Not part of accelerator; however, managed disk snapshots give point-in-time copies of research VMs before high-risk changes (https://learn.microsoft.com/azure/virtual-machines/snapshot-copy-managed-disk).",
            ],
            "improvements": [
                "- Define which datasets can legally be backed up and set retention policies per data classification.",
            ],
        },
        "2.5.2": {
            "score": "Partially supported",
            "response": [
                "- Azure TRE runs in Azure regions that support Availability Zones and redundant storage tiers for resilient deployments (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/architecture/).",
                "- Not part of accelerator; however, Azure Availability Zones keep critical services online even if a datacenter fails (https://learn.microsoft.com/azure/reliability/availability-zones-overview).",
            ],
            "improvements": [
                "- Document which TRE components require zone-redundant deployments and how failover is executed.",
            ],
        },
        "2.5.3": {
            "score": "Supported",
            "response": [
                "- Porter and Terraform definitions for every TRE component are versioned in `templates/**` (https://github.com/microsoft/AzureTRE/tree/main/templates).",
                "- The workspace authoring guide enforces schema/parameter files so configuration states are preserved (https://microsoft.github.io/AzureTRE/latest/tre-workspace-authors/authoring-workspace-templates/).",
            ],
            "improvements": [
                "- Mirror these repositories into your enterprise Git system for disaster recovery.",
            ],
        },
        "2.5.4": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Azure Monitor alerts on metrics and logs from TRE components so responders get rapid signal (https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-overview).",
                "- Not part of accelerator; however, Defender for Cloud raises security incidents for TRE resources, feeding incident response workflows (https://learn.microsoft.com/azure/defender-for-cloud/defender-for-cloud-introduction).",
            ],
            "improvements": [
                "- Tie these alerts into the organization’s incident-response playbooks and ticketing tools.",
            ],
        },
        "2.5.6": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Defender for Cloud vulnerability assessment recommendations cover TRE VMs, registries, and SQL instances (https://learn.microsoft.com/azure/defender-for-cloud/concept-vulnerability-assessment-recommendations).",
                "- Not part of accelerator; however, Defender for Storage malware scanning augments Airlock to detect malicious payloads (https://learn.microsoft.com/azure/defender-for-cloud/defender-for-storage-introduction).",
            ],
            "improvements": [
                "- Define SLAs for remediating vulnerabilities flagged by Defender feeds.",
            ],
        },
        "2.5.7": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Azure Update Manager orchestrates security patch deployment across TRE-managed VMs (https://learn.microsoft.com/azure/update-manager/overview).",
                "- TRE upgrade guidance describes how to patch API, resource processor, and templates via Terraform/Porter (https://microsoft.github.io/AzureTRE/latest/tre-admins/upgrading-tre/).",
            ],
            "improvements": [
                "- Track third-party software updates inside each workspace alongside infrastructure patches.",
            ],
        },
        "2.5.8": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Azure Automanage enforces automatic patching baselines for Windows and Linux research VMs (https://learn.microsoft.com/azure/automanage/automanage-virtual-machines-overview).",
                "- Not part of accelerator; however, Update Manager maintenance configurations let you schedule recurring automatic patch cycles (https://learn.microsoft.com/azure/update-manager/maintenance-configurations).",
            ],
            "improvements": [
                "- Pilot automatic patching on lower environments before enabling it for regulated workspaces.",
            ],
        },
        "2.5.12": {
            "score": "Partially supported",
            "response": [
                "- Azure resources (Storage, Managed Disks, Cosmos, etc.) are encrypted at rest by default, and TRE optionally enables customer-managed keys (CMK) in config (https://microsoft.github.io/AzureTRE/latest/tre-admins/customer-managed-keys/).",
                "- Azure Storage encryption uses platform-managed AES-256 per Microsoft guidance (https://learn.microsoft.com/azure/storage/common/storage-service-encryption).",
            ],
            "improvements": [
                "- Document key-rotation cadence and ensure logs capture CMK administration activities.",
            ],
        },
        "2.5.13": {
            "score": "Supported",
            "response": [
                "- All ingress/egress traffic flows over HTTPS via Application Gateway and Azure Firewall (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
                "- Airlock storage SAS URLs use HTTPS and Defender for Storage scanning before data crosses the boundary (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
            ],
            "improvements": [
                "- Add TLS inspection/monitoring on enterprise firewalls for extra assurance.",
            ],
        },
        "2.5.14": {
            "score": "Partially supported",
            "response": [
                "- Internal service-to-service communication leverages Azure VNets/Private Link so traffic stays on the Microsoft backbone (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
                "- Shared services such as Azure ML private workspaces can be configured for HTTPS-only internal flows.",
            ],
            "improvements": [
                "- Enforce mutual TLS or IPSec for any custom workload components inside workspaces.",
            ],
        },
        "2.5.15": {
            "score": "Supported",
            "response": [
                "- Templates rely on Azure platform cryptography (AES-256) and optionally CMKs, aligning with Microsoft best practices (https://learn.microsoft.com/azure/storage/common/storage-service-encryption).",
                "- CMK guidance leverages Azure Key Vault which satisfies industry-accepted controls (https://microsoft.github.io/AzureTRE/latest/tre-admins/customer-managed-keys/).",
            ],
            "improvements": [
                "- Periodically review Microsoft cryptography roadmaps and update templates when algorithms deprecate.",
            ],
        },
        "2.5.16": {
            "score": "Partially supported",
            "response": [
                "- Keys can be stored in TRE-managed or external Azure Key Vaults with strict access controls (https://microsoft.github.io/AzureTRE/latest/tre-admins/customer-managed-keys/).",
                "- Azure recommends key management best practices such as role separation and logging (https://learn.microsoft.com/azure/key-vault/general/best-practices).",
            ],
            "improvements": [
                "- Define operational processes for key rotation, dual-control approvals, and HSM-backed keys if required.",
            ],
        },
        "2.5.18": {
            "score": "Partially supported",
            "response": [
                "- Azure TRE publishes its baseline compliance mappings so operators understand which regulations are addressed (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/compliance-info/).",
                "- Not part of accelerator; however, Azure provides formal compliance offerings and audit artifacts that can be referenced during TRE accreditation (https://learn.microsoft.com/azure/compliance/offerings/).",
            ],
            "improvements": [
                "- Map your regulator’s control objectives to specific TRE configurations and document any compensating controls.",
            ],
        },
        "3.1.4": {
            "score": "Supported",
            "response": [
                "- Airlock import workflow enforces Draft → Submit → Review → Approve states before data enters a workspace (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
                "- Review UI/API walk Airlock Managers through manual verification steps (https://microsoft.github.io/AzureTRE/latest/using-tre/tre-for-research/review-airlock-request/).",
            ],
            "improvements": [
                "- Integrate organizational IG checklists/approvals via Logic App triggers built on Airlock events.",
            ],
        },
        "3.1.5": {
            "score": "Supported",
            "response": [
                "- Airlock export follows the same multi-stage gate with manual approval, preventing uncontrolled egress (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
                "- Export reviewers must confirm policy compliance before outputs reach the approved storage account.",
            ],
            "improvements": [
                "- Extend the process with data-controller specific approval forms or redaction tooling.",
            ],
        },
        "3.1.6": {
            "score": "Supported",
            "response": [
                "- Airlock allows only workspace owners/Airlock Managers (as delegated by the Data Controller) to approve exports (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
                "- Roles are assigned via Entra ID, so approvals can be limited to controller-appointed individuals.",
            ],
            "improvements": [
                "- Record explicit delegation letters outside TRE to satisfy governance bodies.",
            ],
        },
        "3.1.7": {
            "score": "Partially supported",
            "response": [
                "- Airlock’s state machine + notifications can involve additional reviewers by wiring Logic Apps to status events (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
                "- The accelerator does not limit adding project-independent approvers, but customers must define the process.",
            ],
            "improvements": [
                "- Configure automation to notify external referees/data guardians for specified studies.",
            ],
        },
        "3.1.8": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Microsoft Purview catalogs can register datasets imported via Airlock, capturing ownership and lifecycle metadata (https://learn.microsoft.com/azure/purview/overview).",
                "- Airlock already tracks request IDs, submitters, and storage locations, providing a baseline inventory of TRE-held data (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
            ],
            "improvements": [
                "- Sync Airlock metadata into your enterprise data asset register for full lineage.",
            ],
        },
        "3.1.9": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Azure Storage lifecycle management rules can automatically expire or move blobs according to retention policies (https://learn.microsoft.com/azure/storage/blobs/storage-lifecycle-management-concepts).",
                "- TRE teardown guidance covers how to decommission workspaces and shared services, ensuring residual datasets are deleted (https://microsoft.github.io/AzureTRE/latest/tre-admins/tear-down/).",
            ],
            "improvements": [
                "- Align lifecycle rules with each Data Controller’s retention and destruction schedule.",
            ],
        },
        "3.1.10": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Azure Storage diagnostic logs record delete operations so you can prove when specific files were removed (https://learn.microsoft.com/azure/storage/blobs/monitor-blob-storage).",
                "- Airlock export workflows log the reviewer, timestamp, and final state, providing evidence that outputs were removed or released appropriately (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
            ],
            "improvements": [
                "- Forward deletion logs to an immutable log store for regulator-ready attestations.",
            ],
        },
        "3.1.11": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Purview lineage tooling records when datasets are transformed or overwritten, including the actors performing those actions (https://learn.microsoft.com/azure/purview/how-to-lineage-portal).",
                "- Not part of accelerator; however, Azure Storage logging captures blob write and update events for TRE storage accounts (https://learn.microsoft.com/azure/storage/blobs/monitor-blob-storage).",
            ],
            "improvements": [
                "- Tie lineage events to change-control tickets so reviewers can see why data was modified.",
            ],
        },
        "3.1.12": {
            "score": "Supported",
            "response": [
                "- Workspace GUIs disable clipboard/download by default and all ingress/egress must use Airlock containers (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspace-services/guacamole/).",
                "- Azure Firewall denies outbound traffic unless explicitly allowed (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
            ],
            "improvements": [
                "- Add user awareness and monitoring for attempted policy bypass (e.g., screen capture tools).",
            ],
        },
        "3.2.1": {
            "score": "Supported",
            "response": [
                "- Auth is entirely Entra ID-based; TRE never provisions shared accounts (https://microsoft.github.io/AzureTRE/latest/tre-admins/auth/).",
                "- Workspace roles are assigned per-user, ensuring accountability in audit logs.",
            ],
            "improvements": [
                "- Enforce policies that forbid shared credentials in customer SOPs and audit Entra assignments regularly.",
            ],
        },
        "3.2.2": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Entra ID Identity Governance workflows can require approvers to validate identity evidence before granting TRE access (https://learn.microsoft.com/entra/id-governance/entitlement-management-access-package-request-policy).",
                "- Not part of accelerator; however, Microsoft Entra ID Protection can flag risky sign-ins, prompting additional verification before credentials are issued (https://learn.microsoft.com/entra/id-protection/overview).",
            ],
            "improvements": [
                "- Document the manual ID checks (e.g., HR verification, ID scans) that accompany each access package approval.",
            ],
        },
        "3.2.3": {
            "score": "Supported",
            "response": [
                "- Workspace access is limited to users added to the corresponding app role or security group, enforcing least privilege (https://microsoft.github.io/AzureTRE/latest/tre-admins/auth/).",
                "- Network isolation plus RBAC ensures users can only reach datasets deployed to their workspaces (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
            ],
            "improvements": [
                "- Implement periodic access reviews for each workspace and document data-owner approvals.",
            ],
        },
        "3.2.4": {
            "score": "Partially supported",
            "response": [
                "- Authentication rides on Microsoft Entra ID, so you can enforce tenant-wide MFA/Conditional Access for all TRE apps (https://microsoft.github.io/AzureTRE/latest/tre-admins/auth/).",
                "- Not part of accelerator; however, Microsoft Learn documents recommended MFA options that tenants can enable centrally (https://learn.microsoft.com/entra/identity/authentication/concept-mfa-howitworks).",
            ],
            "improvements": [
                "- Mandate MFA/conditional access policies for every TRE Enterprise Application and monitor compliance.",
            ],
        },
        "3.2.5": {
            "score": "Supported",
            "response": [
                "- TRE relies on Microsoft Entra ID SSO, so researchers sign in with the same enterprise credentials used elsewhere (https://learn.microsoft.com/entra/identity/enterprise-apps/plan-sso-deployment).",
                "- The `make auth` automation registers TRE API/UI as standard Entra enterprise applications (https://microsoft.github.io/AzureTRE/latest/tre-admins/auth/).",
            ],
            "improvements": [
                "- Federate additional identity providers (e.g., academic IdPs) if cross-organization studies are expected.",
            ],
        },
        "3.2.6": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Conditional Access policies can restrict TRE Enterprise Apps to trusted named locations or compliant devices (https://learn.microsoft.com/entra/identity/conditional-access/location-condition).",
                "- Azure Firewall plus forced tunneling ensures workspace traffic only traverses approved network paths (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/networking/).",
            ],
            "improvements": [
                "- Coordinate with your security team to codify the list of permitted IP ranges and geographies.",
            ],
        },
        "3.3.3": {
            "score": "Supported",
            "response": [
                "- Airlock mandates manual review of every export/import, functioning as the documented disclosure-control process (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
                "- Malware scanning + review states ensure identified risks are mitigated before approval.",
            ],
            "improvements": [
                "- Capture statistical disclosure rules/checklists used during Airlock review in organizational policy.",
            ],
        },
        "3.3.4": {
            "score": "Supported",
            "response": [
                "- The Airlock Manager role is assigned per workspace, explicitly owning approval responsibilities (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/user-roles/).",
                "- API records each reviewer’s identity and decision, preserving accountability.",
            ],
            "improvements": [
                "- Assign backup reviewers and document escalation paths for urgent outputs.",
            ],
        },
        "3.3.5": {
            "score": "Partially supported",
            "response": [
                "- Airlock can block or quarantine files that cannot be adequately reviewed (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
                "- Customers must define which file types are unacceptable and how to evidence rejection.",
            ],
            "improvements": [
                "- Extend Airlock policies/scripts to auto-detect file categories requiring additional mitigations.",
            ],
        },
        "3.3.7": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Airlock events + storage automation can be extended with Logic Apps to perform scripted checks before reviewer approval.",
                "- Not part of accelerator; however, malware scanning with Defender for Storage already automates part of the review (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
            ],
            "improvements": [
                "- Build additional automated checks (statistical tests, metadata scans) triggered by Airlock status changes.",
            ],
        },
        "3.3.8": {
            "score": "Supported",
            "response": [
                "- Airlock enforces that only reviewer-approved files leave the TRE, keeping outputs to the documented minimum (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
                "- Workspace architectures encourage researchers to keep raw data internal and only export summaries/graphs.",
            ],
            "improvements": [
                "- Provide guidance/templates for acceptable output types per data classification.",
            ],
        },
        "3.4.1": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Microsoft Purview can expose searchable metadata catalogs without giving researchers direct dataset access (https://learn.microsoft.com/azure/purview/overview).",
                "- Airlock metadata and workspace templates provide descriptive context that can be surfaced to prospective users (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/airlock/).",
            ],
            "improvements": [
                "- Curate user-friendly catalogue views filtered by permissible audience.",
            ],
        },
        "3.5.1": {
            "score": "Partially supported",
            "response": [
                "- Azure TRE ships restricted vs. unrestricted workspace templates so operators can align security controls with data sensitivity (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspaces/unrestricted/).",
                "- Architecture docs describe the security controls (firewalls, Airlock, identity) that underpin each tier (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/architecture/).",
            ],
            "improvements": [
                "- Map organization data classifications to the provided templates and document required extensions.",
            ],
        },
        "3.5.2": {
            "score": "Partially supported",
            "response": [
                "- Workspace templates expose parameters for NSGs, firewall rules, and workspace services, letting you tailor control strength per project (https://microsoft.github.io/AzureTRE/latest/tre-workspace-authors/authoring-workspace-templates/).",
                "- Base workspace template guidance shows how to add or remove services to meet varying requirements (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspaces/base/).",
            ],
            "improvements": [
                "- Maintain a decision tree so requestors land in the correct template variant automatically.",
            ],
        },
        "3.5.3": {
            "score": "Supported",
            "response": [
                "- The solution already provides Restricted, Unrestricted, and Dedicated workspace template tiers with distinct controls (https://microsoft.github.io/AzureTRE/latest/tre-templates/workspaces/unrestricted/).",
                "- Administrators can publish additional Porter bundles to introduce new standard tiers without bespoke engineering (https://microsoft.github.io/AzureTRE/latest/tre-workspace-authors/authoring-workspace-templates/).",
            ],
            "improvements": [
                "- Document which datasets map to each tier and the approval needed to move between them.",
            ],
        },
        "3.6.1": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Purview business glossary and schema features let you describe datasets in a consistent metadata model (https://learn.microsoft.com/azure/purview/overview).",
                "- Workspace templates can include custom parameters/metadata that describe the datasets they host, aiding discoverability (https://microsoft.github.io/AzureTRE/latest/tre-workspace-authors/authoring-workspace-templates/).",
            ],
            "improvements": [
                "- Extend the glossary with domain-specific vocabularies and require authors to populate it during Airlock import.",
            ],
        },
        "3.8.1": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Immutable Storage for Azure Blob enforces write-once-read-many policies so archives stay read-only (https://learn.microsoft.com/azure/storage/blobs/immutable-storage-overview).",
                "- Not part of accelerator; however, Storage RBAC and ACLs can present archival containers as read-only to TRE workspaces (https://learn.microsoft.com/azure/storage/blobs/security-recommendations).",
            ],
            "improvements": [
                "- Define procedures for temporarily unlocking archives when regulators require updates.",
            ],
        },
        "3.8.2": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Azure Data Lake Storage Gen2 stores data using open, analytics-friendly formats like Parquet and CSV (https://learn.microsoft.com/azure/storage/blobs/data-lake-storage-introduction).",
                "- Workspace template parameters can mandate export formats for archival datasets (https://microsoft.github.io/AzureTRE/latest/tre-workspace-authors/authoring-workspace-templates/).",
            ],
            "improvements": [
                "- Publish a format catalogue that aligns each dataset type with its archival file standard.",
            ],
        },
        "4.4.2": {
            "score": "Supported",
            "response": [
                "- Cost APIs break down spend per workspace/service/user resource, satisfying chargeback requirements (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/cost-reporting/).",
                "- UI cost labels show ongoing month-to-date spend, helping project managers monitor budgets.",
            ],
            "improvements": [
                "- Integrate API data with finance systems for automated invoicing or recharge models.",
            ],
        },
        "4.4.1": {
            "score": "Partially supported",
            "response": [
                "- TRE cost reporting surfaces estimated monthly charges before a workspace/service is provisioned (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/cost-reporting/).",
                "- Not part of accelerator; however, Azure Cost Management budgets can be shared with project teams so they understand spending ceilings (https://learn.microsoft.com/azure/cost-management-billing/costs/budgets).",
            ],
            "improvements": [
                "- Include TRE cost projections in project initiation documents for formal acknowledgement.",
            ],
        },
        "4.4.3": {
            "score": "Partially supported",
            "response": [
                "- Not part of accelerator; however, Azure Cost Management best practices help TRE operators plan reserve capacity, chargeback, and forecasting (https://learn.microsoft.com/azure/cost-management-billing/costs/cost-mgt-best-practices).",
                "- Cost reporting APIs provide the detailed usage data needed to build recovery models (https://microsoft.github.io/AzureTRE/latest/azure-tre-overview/cost-reporting/).",
            ],
            "improvements": [
                "- Pair Azure telemetry with organizational finance tooling to prove 12-month funding runway.",
            ],
        },
        "4.4.4": {
            "score": "Partially supported",
            "response": [
                "- TRE administrators can stop or start shared services to minimize idle spend when projects pause (https://microsoft.github.io/AzureTRE/latest/tre-admins/start-stop/).",
                "- Not part of accelerator; however, Azure Cost Management recommendations highlight savings plans, rightsizing, and idle resources to optimise spend (https://learn.microsoft.com/azure/cost-management-billing/costs/cost-mgt-best-practices).",
            ],
            "improvements": [
                "- Review cost reports regularly and capture resulting optimization actions in change records.",
            ],
        },
    }

    default = {
        "score": "N/A (customer control)",
        "response": ["- Not applicable as an accelerator"],
        "improvements": ["- Customer must implement policy/process for this control."]
    }

    lines = TEMPLATE_PATH.read_text().splitlines()
    output_lines = []
    for line in lines:
        if not line.startswith("|") or line.startswith("| Section") or line.startswith("|----"):
            output_lines.append(line)
            continue

        parts = [p.strip() for p in line.strip().split("|")[1:-1]]
        if len(parts) != 8:
            output_lines.append(line)
            continue

        key = sanitize(parts[1])
        data = overrides.get(key, default)
        parts[5] = data["score"]  # type: ignore
        parts[6] = join_bullets(data["response"])  # type: ignore
        parts[7] = join_bullets(data["improvements"])  # type: ignore
        output_lines.append("| " + " | ".join(parts) + " |")

    OUTPUT_PATH.write_text("\n".join(output_lines) + "\n")


if __name__ == "__main__":
    main()
