import React from "react";
import { Stack, Text } from "@fluentui/react";
import { WorkspaceBudget, percentUsed, remaining, statusOf } from "../../models/billing";
import { formatCurrency, formatPercent, statusColor, statusLabel } from "./billingFormat";

interface BudgetGaugeProps {
  budget: WorkspaceBudget;
}

export const BudgetGauge: React.FunctionComponent<BudgetGaugeProps> = ({ budget }) => {
  const pct = percentUsed(budget);
  const status = statusOf(budget);
  const color = statusColor[status];
  const barPct = Math.min(pct, 100);

  return (
    <Stack tokens={{ childrenGap: 8 }}>
      <Stack horizontal horizontalAlign="space-between">
        <Text variant="xLarge" styles={{ root: { fontWeight: 600 } }}>
          {formatCurrency(budget.consumed, budget.currency)}
        </Text>
        <Text variant="large" styles={{ root: { color } }}>
          {formatPercent(pct)} used
        </Text>
      </Stack>
      <div
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        style={{
          position: "relative",
          height: 18,
          borderRadius: 9,
          background: "#edebe9",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${barPct}%`,
            height: "100%",
            background: color,
            transition: "width 0.4s ease",
          }}
        />
        {/* threshold ticks */}
        {budget.thresholds.map((t) => (
          <div
            key={t}
            title={`${t}% threshold`}
            style={{
              position: "absolute",
              left: `${Math.min(t, 100)}%`,
              top: 0,
              bottom: 0,
              width: 2,
              background: "#605e5c",
              opacity: 0.6,
            }}
          />
        ))}
      </div>
      <Stack horizontal horizontalAlign="space-between" tokens={{ childrenGap: 16 }}>
        <Text variant="small">
          Allocated: <strong>{formatCurrency(budget.allocated, budget.currency)}</strong>
        </Text>
        <Text variant="small">
          Remaining: <strong>{formatCurrency(remaining(budget), budget.currency)}</strong>
        </Text>
        <Text variant="small" styles={{ root: { color } }}>
          {statusLabel[status]}
        </Text>
      </Stack>
    </Stack>
  );
};
