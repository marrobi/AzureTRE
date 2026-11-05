import React from "react";
import { Stack } from "@fluentui/react";

// The card style used by Azure TRE resource cards.
export const Card: React.FunctionComponent<React.PropsWithChildren<{ className?: string }>> = ({
  children,
  className,
}) => (
  <Stack className={`nf-card ${className ?? ""}`} tokens={{ childrenGap: 8 }}>
    {children}
  </Stack>
);
