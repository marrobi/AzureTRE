import React, { useState } from "react";
import {
  ChoiceGroup,
  DefaultButton,
  Dropdown,
  IChoiceGroupOption,
  IDropdownOption,
  MessageBar,
  MessageBarType,
  Pivot,
  PivotItem,
  PrimaryButton,
  Separator,
  SpinButton,
  Stack,
  Text,
  TextField,
  Toggle,
} from "@fluentui/react";
import { EnforcementLevel, WorkspaceBudget } from "../../models/billing";
import { useBilling } from "../../contexts/BillingContext";
import { BudgetGauge } from "./BudgetGauge";
import { SpendChart } from "./SpendChart";
import { TopUpPanel } from "./TopUpPanel";

interface WorkspaceBudgetPanelProps {
  budget: WorkspaceBudget;
}

const enforcementOptions: IChoiceGroupOption[] = [
  { key: "notify", text: "Notify only" },
  { key: "block", text: "Block new provisioning" },
  { key: "stop", text: "Stop (disable workspace)" },
];

export const WorkspaceBudgetPanel: React.FunctionComponent<WorkspaceBudgetPanelProps> = ({
  budget,
}) => {
  const { amendBudget, switchMode, setEnforcement, setThresholds, can } = useBilling();
  const [amendAmount, setAmendAmount] = useState(budget.allocated);
  const [amendReason, setAmendReason] = useState("");
  const [warnThreshold, setWarnThreshold] = useState(budget.thresholds[1] ?? 80);

  const thresholdOptions: IDropdownOption[] = [50, 60, 70, 75, 80, 90].map((v) => ({
    key: v,
    text: `${v}%`,
  }));

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Stack
        horizontal
        horizontalAlign="space-between"
        verticalAlign="center"
        wrap
        tokens={{ childrenGap: 16 }}
      >
        <Text variant="xxLarge" styles={{ root: { fontWeight: 600 } }}>
          {budget.workspaceName}
        </Text>
        <Text variant="small" styles={{ root: { color: "#605e5c" } }}>
          Payment reference: <strong>{budget.paymentReference}</strong>
        </Text>
      </Stack>

      <BudgetGauge budget={budget} />

      <Separator />

      <Pivot>
        <PivotItem headerText="Overview" itemIcon="BarChartVertical">
          <div style={{ paddingTop: 16 }}>
            <SpendChart budget={budget} />
          </div>
        </PivotItem>

        <PivotItem headerText="Budget & enforcement" itemIcon="Settings">
          <Stack tokens={{ childrenGap: 16 }} styles={{ root: { paddingTop: 16, maxWidth: 560 } }}>
            <Toggle
              label="Funding mode"
              onText="Paid (requires reconciled payment)"
              offText="Soft (governance / tracking only)"
              checked={budget.fundingMode === "paid"}
              disabled={!can.changeFundingMode}
              onChange={(_, checked) =>
                switchMode(budget.workspaceId, checked ? "paid" : "soft")
              }
              data-testid="funding-mode-toggle"
            />

            <Stack tokens={{ childrenGap: 8 }}>
              <Text variant="mediumPlus" styles={{ root: { fontWeight: 600 } }}>
                Enforcement severity
              </Text>
              <ChoiceGroup
                selectedKey={budget.enforcement}
                options={enforcementOptions}
                disabled={!can.changeEnforcement}
                onChange={(_, opt) =>
                  setEnforcement(budget.workspaceId, (opt?.key as EnforcementLevel) ?? "notify")
                }
                data-testid="enforcement-choice"
              />
            </Stack>

            <Dropdown
              label="Warning threshold"
              selectedKey={warnThreshold}
              options={thresholdOptions}
              disabled={!can.configureThresholds}
              styles={{ root: { maxWidth: 160 } }}
              onChange={(_, opt) => {
                const v = Number(opt?.key) || 80;
                setWarnThreshold(v);
                setThresholds(budget.workspaceId, [50, v, 100]);
              }}
              data-testid="threshold-dropdown"
            />

            <Separator />

            <Text variant="mediumPlus" styles={{ root: { fontWeight: 600 } }}>
              Amend allocation
            </Text>
            <MessageBar messageBarType={MessageBarType.info} isMultiline>
              Sets the workspace&apos;s <strong>total budget</strong> to a new figure (this replaces
              the current allocation — it is not added to it). Use this to correct or re-baseline the
              budget; every change is recorded in the audit log with the reason you provide.
              {budget.fundingMode === "paid" && (
                <>
                  {" "}In <strong>paid</strong> mode, increases normally come from a paid invoice on
                  the <strong>Top-ups</strong> tab — use amend here mainly for corrections or to
                  reduce the allocation.
                </>
              )}
            </MessageBar>
            <Stack horizontal tokens={{ childrenGap: 16 }} verticalAlign="end" wrap>
              <SpinButton
                label="New total allocation"
                value={String(amendAmount)}
                min={0}
                step={500}
                styles={{ root: { width: 180 } }}
                onChange={(_, v) => setAmendAmount(Number(v) || 0)}
              />
              <TextField
                label="Reason (audited)"
                value={amendReason}
                onChange={(_, v) => setAmendReason(v ?? "")}
                styles={{ root: { flexGrow: 1, minWidth: 220 } }}
                placeholder="e.g. Increase for additional cohort"
              />
            </Stack>
            <Stack horizontal>
              <PrimaryButton
                text="Save allocation"
                iconProps={{ iconName: "Save" }}
                disabled={!amendReason || !can.amendBudget}
                onClick={() =>
                  amendBudget(budget.workspaceId, amendAmount, amendReason || "No reason given")
                }
                data-testid="amend-budget"
              />
            </Stack>
          </Stack>
        </PivotItem>

        <PivotItem headerText="Top-ups" itemIcon="Money">
          <div style={{ paddingTop: 16, maxWidth: 640 }}>
            <TopUpPanel budget={budget} />
          </div>
        </PivotItem>

        <PivotItem headerText="Audit log" itemIcon="History">
          <Stack tokens={{ childrenGap: 8 }} styles={{ root: { paddingTop: 16 } }}>
            {budget.audit.map((a, i) => (
              <Stack
                key={i}
                horizontal
                tokens={{ childrenGap: 12 }}
                styles={{ root: { padding: "6px 0", borderBottom: "1px solid #f3f2f1" } }}
              >
                <Text variant="small" styles={{ root: { color: "#605e5c", width: 150 } }}>
                  {new Date(a.timestamp).toLocaleString()}
                </Text>
                <Text variant="small" styles={{ root: { fontWeight: 600, width: 160 } }}>
                  {a.action}
                </Text>
                <Text variant="small" styles={{ root: { flexGrow: 1 } }}>
                  {a.detail}
                </Text>
                <Text variant="small" styles={{ root: { color: "#a19f9d" } }}>
                  {a.actor}
                </Text>
              </Stack>
            ))}
          </Stack>
        </PivotItem>
      </Pivot>
    </Stack>
  );
};
