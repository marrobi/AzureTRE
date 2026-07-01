// Mock workspaces + workspace services derived from the billing mock data, so the
// full TRE UI (workspace list, workspace nav, services) renders in mock mode and
// stays in sync with the billing module.
import { Workspace } from "../models/workspace";
import { WorkspaceService } from "../models/workspaceService";
import { ResourceType } from "../models/resourceType";
import { User } from "../models/user";
import { buildMockBudgets } from "./billingMockData";

const nowEpoch = Math.floor(Date.now() / 1000);

const mockUser: User = {
  email: "tre-admin@contoso.org",
  id: "mock-user",
  name: "Demo Admin",
  roleAssignments: [],
  roles: [],
};

const budgets = buildMockBudgets();

const templateForService = (name: string): string => {
  const n = name.toLowerCase();
  if (n.includes("virtual desktop")) return "tre-service-guacamole";
  if (n.includes("ai foundry")) return "tre-service-ai-foundry";
  if (n.includes("machine learning")) return "tre-service-azureml";
  if (n.includes("databricks")) return "tre-service-databricks";
  return "tre-service-base";
};

export const mockWorkspaces: Workspace[] = budgets.map((b) => ({
  id: b.workspaceId,
  isEnabled: true,
  resourcePath: `/workspaces/${b.workspaceId}`,
  resourceVersion: 1,
  resourceType: ResourceType.Workspace,
  templateName: "tre-workspace-base",
  templateVersion: "2.1.0",
  availableUpgrades: [],
  deploymentStatus: "deployed",
  updatedWhen: nowEpoch,
  user: mockUser,
  history: [],
  _etag: `"mock-${b.workspaceId}"`,
  properties: {
    display_name: b.workspaceName,
    description: `${b.workspaceName} research workspace`,
    scope_id: `api://mock-${b.workspaceId}`,
    client_id: "mock-client",
    workspace_owner_object_id: "mock-owner",
    enable_airlock: true,
  },
  workspaceURL: "",
}));

export const mockWorkspaceServices: Record<string, WorkspaceService[]> = {};
budgets.forEach((b) => {
  mockWorkspaceServices[b.workspaceId] = b.services.map((s) => ({
    id: s.id,
    workspaceId: b.workspaceId,
    isEnabled: true,
    resourcePath: `/workspaces/${b.workspaceId}/workspace-services/${s.id}`,
    resourceVersion: 1,
    resourceType: ResourceType.WorkspaceService,
    templateName: templateForService(s.name),
    templateVersion: "1.0.0",
    availableUpgrades: [],
    deploymentStatus: "deployed",
    updatedWhen: nowEpoch,
    user: mockUser,
    history: [],
    _etag: `"mock-${s.id}"`,
    properties: {
      display_name: s.name,
      description: `${s.name} workspace service`,
    },
  }));
});
