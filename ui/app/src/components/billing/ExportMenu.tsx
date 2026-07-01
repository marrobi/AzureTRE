import React from "react";
import { DefaultButton, IContextualMenuProps } from "@fluentui/react";
import { WorkspaceBudget, percentUsed, remaining, statusOf } from "../../models/billing";
import { formatCurrency, statusLabel } from "./billingFormat";

interface ExportMenuProps {
  budgets: WorkspaceBudget[];
}

const toCsv = (budgets: WorkspaceBudget[]): string => {
  const header = [
    "Workspace",
    "Currency",
    "Funding mode",
    "Allocated",
    "Consumed",
    "Remaining",
    "% used",
    "Enforcement",
    "Status",
  ];
  const rows = budgets.map((b) => [
    b.workspaceName,
    b.currency,
    b.fundingMode,
    b.allocated.toFixed(2),
    b.consumed.toFixed(2),
    remaining(b).toFixed(2),
    Math.round(percentUsed(b)).toString(),
    b.enforcement,
    statusLabel[statusOf(b)],
  ]);
  return [header, ...rows]
    .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","))
    .join("\n");
};

export const ExportMenu: React.FunctionComponent<ExportMenuProps> = ({ budgets }) => {
  const downloadCsv = () => {
    const blob = new Blob([toCsv(budgets)], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tre-billing-report.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const printPdf = () => window.print();

  const menuProps: IContextualMenuProps = {
    items: [
      {
        key: "csv",
        text: "Export as CSV",
        iconProps: { iconName: "ExcelDocument" },
        onClick: () => {
          downloadCsv();
          return true;
        },
      },
      {
        key: "pdf",
        text: "Export as PDF (print)",
        iconProps: { iconName: "PDF" },
        onClick: () => {
          printPdf();
          return true;
        },
      },
    ],
  };

  return (
    <DefaultButton
      text="Export"
      iconProps={{ iconName: "Download" }}
      menuProps={menuProps}
      data-testid="export-menu"
    />
  );
};

export const summarize = (budgets: WorkspaceBudget[]) => ({
  totalAllocated: budgets.reduce((a, b) => a + b.allocated, 0),
  totalConsumed: budgets.reduce((a, b) => a + b.consumed, 0),
  currency: budgets[0]?.currency ?? "USD",
  asString: (v: number) => formatCurrency(v, budgets[0]?.currency ?? "USD"),
});
