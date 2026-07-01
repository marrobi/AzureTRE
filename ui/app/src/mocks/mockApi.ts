// In-memory mock of the TRE API used when VITE_MOCK=true. Routes the same calls
// that useAuthApiCall makes to mock responses so the full UI runs without auth.
import { mockWorkspaces, mockWorkspaceServices } from "./mockWorkspaces";
import { buildMockBudgets } from "./billingMockData";

const budgets = buildMockBudgets();
const CURRENCY = budgets[0]?.currency ?? "GBP";

const overallCostReport = () => ({
  core_services: [{ cost: 1234.56, currency: CURRENCY }],
  shared_services: [
    { id: "ss-firewall", name: "Firewall", costs: [{ cost: 320.0, currency: CURRENCY }] },
    { id: "ss-gitea", name: "Gitea", costs: [{ cost: 85.5, currency: CURRENCY }] },
    { id: "ss-nexus", name: "Nexus", costs: [{ cost: 142.3, currency: CURRENCY }] },
  ],
  workspaces: budgets.map((b) => ({
    id: b.workspaceId,
    name: b.workspaceName,
    costs: [{ cost: b.consumed, currency: b.currency }],
  })),
});

const workspaceCostReport = (id: string) => {
  const b = budgets.find((x) => x.workspaceId === id);
  if (!b) return { id, name: id, costs: [], workspace_services: [] };
  return {
    id: b.workspaceId,
    name: b.workspaceName,
    costs: [{ cost: b.consumed, currency: b.currency }],
    workspace_services: b.services.map((s) => ({
      id: s.id,
      name: s.name,
      costs: [{ cost: s.cost, currency: b.currency }],
      user_resources: s.userResources.map((ur) => ({
        id: ur.id,
        name: ur.name,
        costs: [{ cost: ur.cost, currency: b.currency }],
      })),
    })),
  };
};

type SetRoles = (roles: Array<string>) => void;

// Mirrors the useAuthApiCall callback signature.
export async function mockApiCall(
  endpoint: string,
  _method: string,
  _workspaceApplicationIdURI?: string,
  _body?: any,
  _resultType?: any,
  setRoles?: SetRoles,
  tokenOnly?: boolean,
  _etag?: string,
): Promise<any> {
  const e = endpoint.split("?")[0].replace(/\/$/, "");

  // Role resolution (token-only calls)
  if (tokenOnly && setRoles) {
    if (/^workspaces\/[^/]+$/.test(e)) {
      setRoles(["WorkspaceOwner"]);
    } else {
      // Root TRE roles. In demo mode ?role=owner downgrades to a non-admin user
      // so the admin-only chrome (Billing nav, Create) is hidden.
      const roleParam =
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search).get("role")
          : null;
      setRoles(roleParam === "owner" ? ["TREUser"] : ["TREAdmin"]);
    }
    return {};
  }

  if (e === "workspaces") return { workspaces: mockWorkspaces };
  if (/^workspaces\/[^/]+\/scopeid$/.test(e)) {
    return { workspaceAuth: { scopeId: "mock-scope" } };
  }
  if (/^workspaces\/[^/]+\/workspace-services$/.test(e)) {
    const id = e.split("/")[1];
    return { workspaceServices: mockWorkspaceServices[id] ?? [] };
  }
  if (/^workspaces\/[^/]+\/costs$/.test(e)) {
    return workspaceCostReport(e.split("/")[1]);
  }
  if (/^workspaces\/[^/]+\/workspace-services\/[^/]+$/.test(e)) {
    const [, wsId, , svcId] = e.split("/");
    const svc = (mockWorkspaceServices[wsId] ?? []).find((s) => s.id === svcId);
    return { workspaceService: svc };
  }
  if (/^workspaces\/[^/]+$/.test(e)) {
    const id = e.split("/")[1];
    return { workspace: mockWorkspaces.find((w) => w.id === id) };
  }
  if (e === "shared-services") return { sharedServices: [] };
  if (e === "costs") return overallCostReport();

  // Generic fallbacks so polling/list calls don't crash the UI.
  if (e.endsWith("operations")) return { operations: [] };
  if (e.endsWith("history")) return { history: [] };
  if (e.endsWith("users")) return { users: [] };
  if (e.endsWith("assignable-users")) return { assignableUsers: [] };
  if (e.endsWith("requests")) return { airlockRequests: [] };
  if (e.includes("templates")) return { templates: [] };
  return {};
}
