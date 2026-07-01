import React, { useState } from "react";
import { DefaultButton, Stack } from "@fluentui/react";
import { useBilling } from "../../contexts/BillingContext";
import { BillingDashboard } from "./BillingDashboard";
import { WorkspaceBudgetPanel } from "./WorkspaceBudgetPanel";

// Top-level (TRE Admin) billing view shown under the root left nav.
export const BillingAdminView: React.FunctionComponent = () => {
  const { getBudget } = useBilling();
  const [selected, setSelected] = useState<string | undefined>(undefined);
  const budget = selected ? getBudget(selected) : undefined;

  return (
    <Stack className="tre-panel">
      {budget ? (
        <Stack tokens={{ childrenGap: 10 }}>
          <Stack.Item>
            <DefaultButton
              iconProps={{ iconName: "Back" }}
              text="All workspaces"
              onClick={() => setSelected(undefined)}
            />
          </Stack.Item>
          <WorkspaceBudgetPanel budget={budget} />
        </Stack>
      ) : (
        <BillingDashboard onSelectWorkspace={setSelected} />
      )}
    </Stack>
  );
};
