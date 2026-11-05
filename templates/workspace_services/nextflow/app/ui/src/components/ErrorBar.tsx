import React from "react";
import { MessageBar, MessageBarType } from "@fluentui/react";

export const ErrorBar: React.FunctionComponent<{ error?: string | null; onDismiss?: () => void }> = ({
  error,
  onDismiss,
}) =>
  error ? (
    <MessageBar messageBarType={MessageBarType.error} isMultiline onDismiss={onDismiss}>
      {error}
    </MessageBar>
  ) : null;
