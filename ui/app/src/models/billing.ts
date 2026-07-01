// Models for the Workspace Billing & Budget demo module.
// These types are intentionally self-contained for the mocked demo experience.

export type FundingMode = "soft" | "paid";

// Enforcement severity ladder (locked decision #1):
// notify-only -> block new provisioning -> stop (disable workspace)
export type EnforcementLevel = "notify" | "block" | "stop";

export type BudgetStatus = "ok" | "warning" | "over" | "stopped";

export type TopUpMethod = "bank" | "online";

// Invoice lifecycle: an invoice is raised (awaiting payment), then paid
// either by bank transfer (Finance reconciles) or online (simulated, instant).
export type TopUpStatus = "awaiting_payment" | "reconciled" | "rejected";

export interface SpendPoint {
  date: string; // ISO date
  cost: number;
}

// A change to the workspace's total allocation, effective from `date`.
export interface AllocationPoint {
  date: string; // ISO date the allocation took effect
  amount: number; // total allocation from this date
}

export interface ServiceSpend {
  name: string;
  cost: number;
}

export interface UserResourceCost {
  id: string;
  name: string;
  owner: string;
  cost: number;
}

export interface WorkspaceServiceCost {
  id: string;
  name: string; // template/display name e.g. "Guacamole", "Azure ML"
  cost: number; // service cost excluding user resources
  userResources: UserResourceCost[];
}

export interface TopUp {
  id: string;
  amount: number;
  method?: TopUpMethod; // set when the invoice is paid
  reference: string; // short generated payment reference mapped to the workspace
  status: TopUpStatus;
  requestedBy: string;
  requestedDate: string;
  reconciledBy?: string;
  reconciledDate?: string;
  note?: string;
}

export interface AuditEntry {
  timestamp: string;
  actor: string;
  action: string;
  detail: string;
}

export interface WorkspaceBudget {
  workspaceId: string;
  workspaceName: string;
  currency: string; // ISO currency code; multi-currency is rejected
  fundingMode: FundingMode;
  allocated: number;
  consumed: number;
  enforcement: EnforcementLevel;
  thresholds: number[]; // percentages e.g. [50, 80, 100]
  paymentReference: string; // short ref mapped to the workspace (not the raw GUID)
  dailySpend: SpendPoint[];
  allocationHistory: AllocationPoint[];
  serviceBreakdown: ServiceSpend[];
  services: WorkspaceServiceCost[];
  topUps: TopUp[];
  audit: AuditEntry[];
}

export interface BillingAlert {
  id: string;
  workspaceId: string;
  workspaceName: string;
  threshold: number;
  percentUsed: number;
  timestamp: string;
  enforcement: EnforcementLevel;
}

export const remaining = (b: WorkspaceBudget): number =>
  Math.max(b.allocated - b.consumed, 0);

export const percentUsed = (b: WorkspaceBudget): number =>
  b.allocated > 0 ? Math.min((b.consumed / b.allocated) * 100, 999) : 0;

export const statusOf = (b: WorkspaceBudget): BudgetStatus => {
  const pct = percentUsed(b);
  if (pct >= 100 && b.enforcement === "stop") return "stopped";
  if (pct >= 100) return "over";
  if (pct >= (b.thresholds[1] ?? 80)) return "warning";
  return "ok";
};
