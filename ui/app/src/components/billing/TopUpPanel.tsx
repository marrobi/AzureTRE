import React, { useState } from "react";
import {
  DefaultButton,
  MessageBar,
  MessageBarType,
  PrimaryButton,
  SpinButton,
  Stack,
  Text,
  TextField,
} from "@fluentui/react";
import { TopUp, WorkspaceBudget } from "../../models/billing";
import { useBilling } from "../../contexts/BillingContext";
import { formatCurrency } from "./billingFormat";

interface TopUpPanelProps {
  budget: WorkspaceBudget;
}

export const TopUpPanel: React.FunctionComponent<TopUpPanelProps> = ({ budget }) => {
  const { requestInvoice, reconcileTopUp, payInvoiceOnline, amendBudget, can } = useBilling();
  const [amount, setAmount] = useState(1000);
  const [note, setNote] = useState("");
  const [lastRequested, setLastRequested] = useState<TopUp | undefined>(undefined);
  const [added, setAdded] = useState<number | undefined>(undefined);

  const onRequest = () => {
    const invoice = requestInvoice(budget.workspaceId, amount, note || undefined);
    setLastRequested(invoice);
    setNote("");
  };

  const onDirectAdd = () => {
    amendBudget(
      budget.workspaceId,
      budget.allocated + amount,
      note || "Budget increase (soft mode, no payment)",
    );
    setAdded(amount);
    setNote("");
  };

  const outstanding = budget.topUps.filter((t) => t.status === "awaiting_payment");
  const isPaid = budget.fundingMode === "paid";

  // ---- Soft mode: direct amend, no payment instrument ----
  if (!isPaid) {
    return (
      <Stack tokens={{ childrenGap: 12 }}>
        <MessageBar messageBarType={MessageBarType.info} isMultiline>
          This workspace is in <strong>soft</strong> funding mode — budget is for tracking and
          governance only. You can add to the budget directly; <strong>no payment</strong> is
          required and provisioning is never blocked. Switch to <strong>paid</strong> mode (Budget
          &amp; enforcement tab) to require an invoice and payment.
        </MessageBar>

        <Text variant="mediumPlus" styles={{ root: { fontWeight: 600 } }}>
          Add to budget
        </Text>
        <Stack horizontal tokens={{ childrenGap: 16 }} verticalAlign="end" wrap>
          <SpinButton
            label="Amount to add"
            value={String(amount)}
            min={100}
            step={100}
            styles={{ root: { width: 180 } }}
            onChange={(_, v) => setAmount(Number(v) || 0)}
          />
          <TextField
            label="Reason (audited)"
            value={note}
            onChange={(_, v) => setNote(v ?? "")}
            styles={{ root: { flexGrow: 1, minWidth: 220 } }}
            placeholder="e.g. Reallocation from central R&D fund"
          />
        </Stack>
        <Stack horizontal>
          <PrimaryButton
            text="Add to budget"
            iconProps={{ iconName: "Add" }}
            onClick={onDirectAdd}
            disabled={!can.requestTopUp || amount <= 0}
            data-testid="soft-add-budget"
          />
        </Stack>

        {added !== undefined && (
          <MessageBar messageBarType={MessageBarType.success}>
            Added {formatCurrency(added, budget.currency)} to the budget (soft mode, no payment).
            New allocation: {formatCurrency(budget.allocated, budget.currency)}.
          </MessageBar>
        )}
      </Stack>
    );
  }

  // ---- Paid mode: request an invoice, then pay it (bank transfer or online) ----
  return (
    <Stack tokens={{ childrenGap: 12 }}>
      <MessageBar messageBarType={MessageBarType.info} isMultiline>
        This workspace is in <strong>paid</strong> funding mode. Request an <strong>invoice</strong>{" "}
        for the amount you need — the budget only increases once the invoice is paid. An invoice can
        be settled by <strong>bank transfer</strong> (quote the payment reference; Finance reconciles
        when the funds arrive) or paid instantly via an <strong>online payment link</strong>.
      </MessageBar>

      <Text variant="mediumPlus" styles={{ root: { fontWeight: 600 } }}>
        Request invoice
      </Text>
      <Stack horizontal tokens={{ childrenGap: 16 }} verticalAlign="end" wrap>
        <SpinButton
          label="Amount"
          value={String(amount)}
          min={100}
          step={100}
          styles={{ root: { width: 160 } }}
          onChange={(_, v) => setAmount(Number(v) || 0)}
        />
        <TextField
          label="Note (optional)"
          value={note}
          onChange={(_, v) => setNote(v ?? "")}
          styles={{ root: { flexGrow: 1, minWidth: 240 } }}
          placeholder="e.g. Additional GPU capacity for Q3"
        />
      </Stack>
      <Stack horizontal>
        <PrimaryButton
          text="Request invoice"
          iconProps={{ iconName: "TextDocument" }}
          onClick={onRequest}
          disabled={!can.requestTopUp}
          data-testid="request-invoice"
        />
      </Stack>

      {lastRequested && (
        <MessageBar messageBarType={MessageBarType.success} isMultiline>
          Invoice raised for {formatCurrency(lastRequested.amount, budget.currency)} (reference{" "}
          <strong data-testid="payment-reference">{lastRequested.reference}</strong>). Pay it below
          by bank transfer or online — the budget increases once it is settled.
        </MessageBar>
      )}

      {outstanding.length > 0 && (
        <Stack tokens={{ childrenGap: 8 }}>
          <Text variant="mediumPlus" styles={{ root: { fontWeight: 600 } }}>
            Outstanding invoices ({outstanding.length})
          </Text>
          {outstanding.map((t) => (
            <Stack
              key={t.id}
              tokens={{ childrenGap: 8 }}
              styles={{
                root: {
                  padding: "10px 12px",
                  border: "1px solid #edebe9",
                  borderRadius: 4,
                },
              }}
            >
              <Stack horizontal horizontalAlign="space-between" verticalAlign="center" wrap>
                <Stack>
                  <Text styles={{ root: { fontWeight: 600 } }}>
                    {formatCurrency(t.amount, budget.currency)} — invoice {t.reference}
                  </Text>
                  <Text variant="small" styles={{ root: { color: "#605e5c" } }}>
                    Requested by {t.requestedBy} · awaiting payment
                  </Text>
                </Stack>
              </Stack>

              <Stack horizontal tokens={{ childrenGap: 12 }} verticalAlign="center" wrap>
                {/* Online payment — payer self-service, instant */}
                <PrimaryButton
                  text="Pay now (online)"
                  iconProps={{ iconName: "PaymentCard" }}
                  onClick={() => payInvoiceOnline(budget.workspaceId, t.id)}
                  disabled={!can.requestTopUp}
                  data-testid="pay-online"
                />

                {/* Bank transfer — Finance reconciles when funds arrive */}
                {can.reconcile ? (
                  <DefaultButton
                    text="Reconcile bank transfer"
                    iconProps={{ iconName: "Accept" }}
                    onClick={() => reconcileTopUp(budget.workspaceId, t.id)}
                    data-testid="reconcile-topup"
                  />
                ) : (
                  <Text variant="small" styles={{ root: { color: "#a19f9d" } }}>
                    Or pay by bank transfer quoting {t.reference} — Finance will reconcile on receipt.
                  </Text>
                )}
              </Stack>
            </Stack>
          ))}
        </Stack>
      )}
    </Stack>
  );
};
