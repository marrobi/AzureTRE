import React, { useState } from "react";
import {
  Dropdown,
  IDropdownOption,
  Icon,
  MessageBar,
  MessageBarType,
  Stack,
  Text,
  initializeIcons,
} from "@fluentui/react";
import { BillingProvider, DemoRole, useBilling } from "../../contexts/BillingContext";
import { BillingDashboard } from "./BillingDashboard";
import { WorkspaceBudgetPanel } from "./WorkspaceBudgetPanel";

initializeIcons();

const roleOptions: IDropdownOption[] = [
  { key: "admin", text: "TRE Admin" },
  { key: "owner", text: "Workspace Owner" },
  { key: "finance", text: "Finance / Billing" },
];

const roleSummary: Record<DemoRole, string> = {
  admin: "Full access: governance (funding mode, enforcement), budgets, thresholds and top-up requests.",
  owner: "Can amend budgets, configure thresholds and request top-ups for their workspace. Cannot change governance or reconcile payments.",
  finance: "Separation of duties: can reconcile top-up payments only. Budget and governance controls are read-only.",
};

const RoleBanner: React.FunctionComponent = () => {
  const { role } = useBilling();
  return (
    <MessageBar
      messageBarType={MessageBarType.info}
      styles={{ root: { marginBottom: 12 } }}
      data-testid="role-banner"
    >
      <strong>{roleOptions.find((o) => o.key === role)?.text}</strong> — {roleSummary[role]}
    </MessageBar>
  );
};

const AlertsBar: React.FunctionComponent = () => {
  const { alerts, dismissAlert } = useBilling();
  if (alerts.length === 0) return null;
  return (
    <Stack tokens={{ childrenGap: 6 }} styles={{ root: { marginBottom: 12 } }}>
      {alerts.map((a) => (
        <MessageBar
          key={a.id}
          messageBarType={
            a.threshold >= 100 ? MessageBarType.severeWarning : MessageBarType.warning
          }
          onDismiss={() => dismissAlert(a.id)}
          data-testid="billing-alert"
        >
          <strong>{a.workspaceName}</strong> has reached {a.percentUsed}% of its budget (threshold{" "}
          {a.threshold}%). Event emitted to Event Grid — enforcement: <strong>{a.enforcement}</strong>
          .
        </MessageBar>
      ))}
    </Stack>
  );
};

const BillingDemoInner: React.FunctionComponent = () => {
  const { role, setRole, budgets } = useBilling();
  const [selectedWorkspace, setSelectedWorkspace] = useState<string | undefined>(undefined);
  const selectedBudget = budgets.find((b) => b.workspaceId === selectedWorkspace);

  return (
    <Stack styles={{ root: { minHeight: "100vh", background: "#ffffff" } }}>
      {/* Top bar */}
      <Stack
        horizontal
        verticalAlign="center"
        horizontalAlign="space-between"
        styles={{
          root: {
            background: "#243a5e",
            color: "white",
            padding: "0 20px",
            height: 50,
          },
        }}
      >
        <Stack horizontal verticalAlign="center" tokens={{ childrenGap: 10 }}>
          <Icon iconName="TestBeakerSolid" />
          <Text variant="mediumPlus" styles={{ root: { color: "white", fontWeight: 600 } }}>
            Azure TRE — Billing &amp; Budgets (demo)
          </Text>
        </Stack>
        <Stack horizontal verticalAlign="center" tokens={{ childrenGap: 8 }}>
          <Text variant="small" styles={{ root: { color: "white" } }}>
            Acting as:
          </Text>
          <Dropdown
            selectedKey={role}
            options={roleOptions}
            onChange={(_, opt) => setRole((opt?.key as DemoRole) ?? "admin")}
            styles={{ root: { width: 180 } }}
            data-testid="role-switcher"
          />
        </Stack>
      </Stack>

      {/* Body */}
      <Stack horizontal grow styles={{ root: { alignItems: "stretch" } }}>
        {/* Left nav */}
        <Stack
          styles={{
            root: {
              width: 220,
              borderRight: "1px solid #edebe9",
              padding: "16px 8px",
              background: "#faf9f8",
            },
          }}
          tokens={{ childrenGap: 4 }}
        >
          <NavLink
            icon="BarChartVertical"
            label="Overview"
            active={!selectedWorkspace}
            onClick={() => setSelectedWorkspace(undefined)}
            testId="nav-overview"
          />
          <Text variant="small" styles={{ root: { color: "#a19f9d", padding: "8px 12px 0" } }}>
            WORKSPACES
          </Text>
          {budgets.map((b) => (
            <NavLink
              key={b.workspaceId}
              icon="WebAppBuilderFragment"
              label={b.workspaceName}
              active={selectedWorkspace === b.workspaceId}
              onClick={() => setSelectedWorkspace(b.workspaceId)}
              testId={`nav-${b.workspaceId}`}
            />
          ))}
        </Stack>

        {/* Content */}
        <Stack grow styles={{ root: { padding: 24, maxWidth: 1100 } }}>
          <RoleBanner />
          <AlertsBar />
          {selectedBudget ? (
            <WorkspaceBudgetPanel budget={selectedBudget} />
          ) : (
            <BillingDashboard onSelectWorkspace={setSelectedWorkspace} />
          )}
        </Stack>
      </Stack>
    </Stack>
  );
};

const NavLink: React.FunctionComponent<{
  icon: string;
  label: string;
  active: boolean;
  onClick: () => void;
  testId: string;
}> = ({ icon, label, active, onClick, testId }) => (
  <Stack
    horizontal
    verticalAlign="center"
    tokens={{ childrenGap: 10 }}
    onClick={onClick}
    data-testid={testId}
    styles={{
      root: {
        cursor: "pointer",
        padding: "8px 12px",
        borderRadius: 4,
        background: active ? "#edebe9" : "transparent",
        selectors: { ":hover": { background: "#f3f2f1" } },
      },
    }}
  >
    <Icon iconName={icon} styles={{ root: { color: "#0078d4" } }} />
    <Text styles={{ root: { fontWeight: active ? 600 : 400 } }}>{label}</Text>
  </Stack>
);

export const BillingDemoApp: React.FunctionComponent = () => (
  <BillingProvider>
    <BillingDemoInner />
  </BillingProvider>
);
