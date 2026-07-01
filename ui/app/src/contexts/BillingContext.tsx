// In-memory billing state for the demo. All mutations update local React state
// so the UI feels live (no backend, no network).

import React, { createContext, useCallback, useContext, useMemo, useState } from "react";
import {
  AuditEntry,
  BillingAlert,
  EnforcementLevel,
  FundingMode,
  TopUp,
  TopUpMethod,
  WorkspaceBudget,
  percentUsed,
} from "../models/billing";
import { buildMockBudgets, DEMO_USERS } from "../mocks/billingMockData";

export type DemoRole = "admin" | "owner" | "finance";

export interface RolePermissions {
  amendBudget: boolean;
  configureThresholds: boolean;
  requestTopUp: boolean;
  changeFundingMode: boolean;
  changeEnforcement: boolean;
  reconcile: boolean;
}

const permissionsFor = (role: DemoRole): RolePermissions => ({
  // Re-baselining the official allocation is a TRE-admin governance action.
  // Owners adjust their budget via soft-mode "Add to budget" or paid top-ups.
  amendBudget: role === "admin",
  configureThresholds: role === "admin" || role === "owner",
  requestTopUp: role === "admin" || role === "owner",
  // Funding mode & enforcement are TRE-admin governance controls.
  changeFundingMode: role === "admin",
  changeEnforcement: role === "admin",
  // Separation of duties: only Finance reconciles payments.
  reconcile: role === "finance",
});

interface BillingContextValue {
  budgets: WorkspaceBudget[];
  alerts: BillingAlert[];
  role: DemoRole;
  actor: string;
  can: RolePermissions;
  setRole: (r: DemoRole) => void;
  getBudget: (workspaceId: string) => WorkspaceBudget | undefined;
  amendBudget: (workspaceId: string, newAmount: number, reason: string) => void;
  switchMode: (workspaceId: string, mode: FundingMode) => void;
  setEnforcement: (workspaceId: string, level: EnforcementLevel) => void;
  setThresholds: (workspaceId: string, thresholds: number[]) => void;
  requestInvoice: (workspaceId: string, amount: number, note?: string) => TopUp;
  reconcileTopUp: (workspaceId: string, topUpId: string) => void;
  payInvoiceOnline: (workspaceId: string, topUpId: string) => void;
  dismissAlert: (alertId: string) => void;
}

const BillingContext = createContext<BillingContextValue | undefined>(undefined);

const now = () => new Date().toISOString();

// In mock/demo mode the initial role can be set via ?role=admin|owner|finance
// so the admin and workspace-owner experiences can be demonstrated separately.
const initialRole = (): DemoRole => {
  if (typeof window === "undefined") return "admin";
  const r = new URLSearchParams(window.location.search).get("role");
  return r === "owner" || r === "finance" || r === "admin" ? r : "admin";
};

const genRef = (workspaceId: string): string =>
  `PAY-${workspaceId.replace(/[^a-z0-9]/gi, "").toUpperCase().slice(0, 5)}-${Math.floor(
    1000 + Math.random() * 9000,
  )}`;

export const BillingProvider: React.FunctionComponent<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [budgets, setBudgets] = useState<WorkspaceBudget[]>(() => buildMockBudgets());
  const [alerts, setAlerts] = useState<BillingAlert[]>([]);
  const [role, setRole] = useState<DemoRole>(initialRole);

  const actor = DEMO_USERS[role];
  const can = permissionsFor(role);

  const pushAudit = (b: WorkspaceBudget, entry: AuditEntry): WorkspaceBudget => ({
    ...b,
    audit: [entry, ...b.audit],
  });

  const maybeRaiseAlerts = useCallback(
    (b: WorkspaceBudget) => {
      const pct = percentUsed(b);
      const crossed = b.thresholds.filter((t) => pct >= t);
      if (crossed.length === 0) return;
      const top = Math.max(...crossed);
      setAlerts((prev) => {
        // avoid duplicate alert for same workspace+threshold
        if (prev.some((a) => a.workspaceId === b.workspaceId && a.threshold === top)) {
          return prev;
        }
        const alert: BillingAlert = {
          id: `al-${b.workspaceId}-${top}-${Date.now()}`,
          workspaceId: b.workspaceId,
          workspaceName: b.workspaceName,
          threshold: top,
          percentUsed: Math.round(pct),
          timestamp: now(),
          enforcement: b.enforcement,
        };
        return [alert, ...prev];
      });
    },
    [],
  );

  const updateBudget = useCallback(
    (workspaceId: string, mutate: (b: WorkspaceBudget) => WorkspaceBudget) => {
      setBudgets((prev) =>
        prev.map((b) => {
          if (b.workspaceId !== workspaceId) return b;
          const updated = mutate(b);
          maybeRaiseAlerts(updated);
          return updated;
        }),
      );
    },
    [maybeRaiseAlerts],
  );

  const getBudget = useCallback(
    (workspaceId: string) => budgets.find((b) => b.workspaceId === workspaceId),
    [budgets],
  );

  const amendBudget = useCallback(
    (workspaceId: string, newAmount: number, reason: string) => {
      updateBudget(workspaceId, (b) => {
        const direction = newAmount >= b.allocated ? "increased" : "decreased";
        return pushAudit(
          {
            ...b,
            allocated: newAmount,
            allocationHistory: [
              ...b.allocationHistory,
              { date: now(), amount: newAmount },
            ],
          },
          {
            timestamp: now(),
            actor,
            action: `Budget ${direction}`,
            detail: `Allocation set to £${newAmount.toLocaleString()} — ${reason}`,
          },
        );
      });
    },
    [actor, updateBudget],
  );

  const switchMode = useCallback(
    (workspaceId: string, mode: FundingMode) => {
      updateBudget(workspaceId, (b) =>
        pushAudit(
          { ...b, fundingMode: mode },
          {
            timestamp: now(),
            actor,
            action: "Funding mode changed",
            detail: `Switched to ${mode} mode`,
          },
        ),
      );
    },
    [actor, updateBudget],
  );

  const setEnforcement = useCallback(
    (workspaceId: string, level: EnforcementLevel) => {
      updateBudget(workspaceId, (b) =>
        pushAudit(
          { ...b, enforcement: level },
          {
            timestamp: now(),
            actor,
            action: "Enforcement changed",
            detail: `Enforcement set to ${level}`,
          },
        ),
      );
    },
    [actor, updateBudget],
  );

  const setThresholds = useCallback(
    (workspaceId: string, thresholds: number[]) => {
      updateBudget(workspaceId, (b) =>
        pushAudit(
          { ...b, thresholds },
          {
            timestamp: now(),
            actor,
            action: "Thresholds updated",
            detail: `Alert thresholds set to ${thresholds.join("%, ")}%`,
          },
        ),
      );
    },
    [actor, updateBudget],
  );

  const requestInvoice = useCallback(
    (workspaceId: string, amount: number, note?: string): TopUp => {
      const topUp: TopUp = {
        id: `tu-${Date.now()}`,
        amount,
        reference: genRef(workspaceId),
        status: "awaiting_payment",
        requestedBy: actor,
        requestedDate: now(),
        note,
      };
      updateBudget(workspaceId, (b) =>
        pushAudit(
          { ...b, topUps: [topUp, ...b.topUps] },
          {
            timestamp: now(),
            actor,
            action: "Invoice requested",
            detail: `£${amount.toLocaleString()} invoice raised (ref ${topUp.reference}, awaiting payment)`,
          },
        ),
      );
      return topUp;
    },
    [actor, updateBudget],
  );

  const settleInvoice = useCallback(
    (workspaceId: string, topUpId: string, method: TopUpMethod) => {
      updateBudget(workspaceId, (b) => {
        const topUp = b.topUps.find((t) => t.id === topUpId);
        if (!topUp || topUp.status === "reconciled") return b;
        const updatedTopUps = b.topUps.map((t) =>
          t.id === topUpId
            ? {
                ...t,
                method,
                status: "reconciled" as const,
                reconciledBy: actor,
                reconciledDate: now(),
              }
            : t,
        );
        const via =
          method === "online" ? "online payment provider" : "bank transfer (reconciled by Finance)";
        const newAllocated = b.allocated + topUp.amount;
        return pushAudit(
          {
            ...b,
            topUps: updatedTopUps,
            allocated: newAllocated,
            allocationHistory: [
              ...b.allocationHistory,
              { date: now(), amount: newAllocated },
            ],
          },
          {
            timestamp: now(),
            actor,
            action: "Invoice paid",
            detail: `+£${topUp.amount.toLocaleString()} applied via ${via} (ref ${topUp.reference})`,
          },
        );
      });
    },
    [actor, updateBudget],
  );

  // Finance confirms a received bank transfer.
  const reconcileTopUp = useCallback(
    (workspaceId: string, topUpId: string) => settleInvoice(workspaceId, topUpId, "bank"),
    [settleInvoice],
  );

  // Payer settles the invoice instantly via a (simulated) online payment provider.
  const payInvoiceOnline = useCallback(
    (workspaceId: string, topUpId: string) => settleInvoice(workspaceId, topUpId, "online"),
    [settleInvoice],
  );

  const dismissAlert = useCallback((alertId: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== alertId));
  }, []);

  const value = useMemo<BillingContextValue>(
    () => ({
      budgets,
      alerts,
      role,
      actor,
      can,
      setRole,
      getBudget,
      amendBudget,
      switchMode,
      setEnforcement,
      setThresholds,
      requestInvoice,
      reconcileTopUp,
      payInvoiceOnline,
      dismissAlert,
    }),
    [
      budgets,
      alerts,
      role,
      actor,
      can,
      getBudget,
      amendBudget,
      switchMode,
      setEnforcement,
      setThresholds,
      requestInvoice,
      reconcileTopUp,
      payInvoiceOnline,
      dismissAlert,
    ],
  );

  return <BillingContext.Provider value={value}>{children}</BillingContext.Provider>;
};

export const useBilling = (): BillingContextValue => {
  const ctx = useContext(BillingContext);
  if (!ctx) {
    throw new Error("useBilling must be used within a BillingProvider");
  }
  return ctx;
};
