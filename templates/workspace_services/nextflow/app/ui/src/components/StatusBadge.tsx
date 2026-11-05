import React from "react";
import { FontIcon, Spinner, SpinnerSize, Stack, Text } from "@fluentui/react";

const ACTIVE = ["submitted", "queued", "starting", "running"];
const LABELS: Record<string, string> = {
  submitted: "Submitted",
  queued: "Waiting for compute",
  starting: "Starting",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  cancelled: "Cancelled",
};
const ICONS: Record<string, { icon: string; colour: string }> = {
  succeeded: { icon: "CompletedSolid", colour: "#006600" },
  failed: { icon: "StatusErrorFull", colour: "#990000" },
  cancelled: { icon: "Blocked2Solid", colour: "#605e5c" },
};

export const StatusBadge: React.FunctionComponent<{ status: string }> = ({ status }) => {
  const label = LABELS[status] ?? status;
  if (ACTIVE.includes(status)) {
    return <Spinner size={SpinnerSize.small} label={label} labelPosition="right" className="nf-status" />;
  }
  const icon = ICONS[status] ?? { icon: "Unknown", colour: "#605e5c" };
  return (
    <Stack horizontal verticalAlign="center" tokens={{ childrenGap: 6 }} className="nf-status">
      <FontIcon iconName={icon.icon} style={{ color: icon.colour }} aria-hidden />
      <Text>{label}</Text>
    </Stack>
  );
};
