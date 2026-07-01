import React, { useContext } from "react";
import { MessageBar, MessageBarType, Stack } from "@fluentui/react";
import { WorkspaceContext } from "../../contexts/WorkspaceContext";
import { useBilling } from "../../contexts/BillingContext";
import { WorkspaceBudgetPanel } from "./WorkspaceBudgetPanel";

// Workspace-level budget view shown under the workspace left nav (Workspace Owner).
export const WorkspaceBudgetView: React.FunctionComponent = () => {
  const workspaceCtx = useContext(WorkspaceContext);
  const { getBudget } = useBilling();
  const budget = getBudget(workspaceCtx.workspace.id);

  return (
    <Stack className="tre-panel">
      {budget ? (
        <WorkspaceBudgetPanel budget={budget} />
      ) : (
        <MessageBar messageBarType={MessageBarType.info}>
          No budget has been configured for this workspace yet.
        </MessageBar>
      )}
    </Stack>
  );
};
