import React, { useMemo, useState } from "react";
import {
  DefaultButton,
  DetailsList,
  DetailsListLayoutMode,
  Dropdown,
  IColumn,
  IDropdownOption,
  MessageBar,
  MessageBarType,
  SearchBox,
  SelectionMode,
  Stack,
  Text,
} from "@fluentui/react";
import { useBilling } from "../../contexts/BillingContext";
import { WorkspaceBudget, percentUsed, remaining, statusOf } from "../../models/billing";
import { formatCurrency, statusColor, statusLabel } from "./billingFormat";
import { ExportMenu, summarize } from "./ExportMenu";

interface BillingDashboardProps {
  onSelectWorkspace: (workspaceId: string) => void;
}

const StatusPill: React.FunctionComponent<{ budget: WorkspaceBudget }> = ({ budget }) => {
  const status = statusOf(budget);
  return (
    <span
      style={{
        background: statusColor[status],
        color: "white",
        borderRadius: 10,
        padding: "2px 10px",
        fontSize: 12,
        whiteSpace: "nowrap",
      }}
    >
      {statusLabel[status]}
    </span>
  );
};

export const BillingDashboard: React.FunctionComponent<BillingDashboardProps> = ({
  onSelectWorkspace,
}) => {
  const { budgets } = useBilling();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortKey, setSortKey] = useState<string>("name");
  const [sortDesc, setSortDesc] = useState(false);
  const [page, setPage] = useState(0);
  const pageSize = 15;

  const currencies = Array.from(new Set(budgets.map((b) => b.currency)));
  const multiCurrency = currencies.length > 1;

  const totals = summarize(budgets);

  const sortAccessor: Record<string, (b: WorkspaceBudget) => number | string> = useMemo(
    () => ({
      name: (b) => b.workspaceName.toLowerCase(),
      mode: (b) => b.fundingMode,
      allocated: (b) => b.allocated,
      consumed: (b) => b.consumed,
      remaining: (b) => remaining(b),
      used: (b) => percentUsed(b),
      enforcement: (b) => b.enforcement,
      status: (b) => percentUsed(b),
    }),
    [],
  );

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    let rows = budgets.filter((b) => {
      const matchesSearch =
        !term ||
        b.workspaceName.toLowerCase().includes(term) ||
        b.workspaceId.toLowerCase().includes(term);
      const matchesStatus = statusFilter === "all" || statusOf(b) === statusFilter;
      return matchesSearch && matchesStatus;
    });
    const accessor = sortAccessor[sortKey] ?? sortAccessor.name;
    rows = [...rows].sort((a, b) => {
      const va = accessor(a);
      const vb = accessor(b);
      const cmp = typeof va === "number" && typeof vb === "number"
        ? va - vb
        : String(va).localeCompare(String(vb));
      return sortDesc ? -cmp : cmp;
    });
    return rows;
  }, [budgets, search, statusFilter, sortKey, sortDesc, sortAccessor]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize);

  const onColumnClick = (_: any, column: IColumn) => {
    if (column.key === sortKey) {
      setSortDesc(!sortDesc);
    } else {
      setSortKey(column.key);
      setSortDesc(false);
    }
    setPage(0);
  };

  const sortProps = (key: string) => ({
    isSorted: sortKey === key,
    isSortedDescending: sortKey === key && sortDesc,
    onColumnClick,
  });

  const statusOptions: IDropdownOption[] = [
    { key: "all", text: "All statuses" },
    { key: "ok", text: statusLabel.ok },
    { key: "warning", text: statusLabel.warning },
    { key: "over", text: statusLabel.over },
    { key: "stopped", text: statusLabel.stopped },
  ];

  const columns: IColumn[] = [
    {
      key: "name",
      name: "Workspace",
      minWidth: 180,
      isResizable: true,
      ...sortProps("name"),
      onRender: (b: WorkspaceBudget) => (
        <a
          href="#budget"
          onClick={(e) => {
            e.preventDefault();
            onSelectWorkspace(b.workspaceId);
          }}
          data-testid={`ws-link-${b.workspaceId}`}
          style={{ color: "#0078d4", textDecoration: "none", fontWeight: 600 }}
        >
          {b.workspaceName}
        </a>
      ),
    },
    {
      key: "mode",
      name: "Mode",
      minWidth: 60,
      ...sortProps("mode"),
      onRender: (b: WorkspaceBudget) => <span>{b.fundingMode}</span>,
    },
    {
      key: "allocated",
      name: "Allocated",
      minWidth: 90,
      ...sortProps("allocated"),
      onRender: (b: WorkspaceBudget) => formatCurrency(b.allocated, b.currency),
    },
    {
      key: "consumed",
      name: "Consumed",
      minWidth: 90,
      ...sortProps("consumed"),
      onRender: (b: WorkspaceBudget) => formatCurrency(b.consumed, b.currency),
    },
    {
      key: "remaining",
      name: "Remaining",
      minWidth: 90,
      ...sortProps("remaining"),
      onRender: (b: WorkspaceBudget) => formatCurrency(remaining(b), b.currency),
    },
    {
      key: "used",
      name: "% used",
      minWidth: 70,
      ...sortProps("used"),
      onRender: (b: WorkspaceBudget) => `${Math.round(percentUsed(b))}%`,
    },
    {
      key: "enforcement",
      name: "Enforcement",
      minWidth: 90,
      ...sortProps("enforcement"),
      onRender: (b: WorkspaceBudget) => b.enforcement,
    },
    {
      key: "status",
      name: "Status",
      minWidth: 130,
      ...sortProps("status"),
      onRender: (b: WorkspaceBudget) => <StatusPill budget={b} />,
    },
  ];

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center" wrap>
        <Text variant="xxLarge" styles={{ root: { fontWeight: 600 } }}>
          Billing &amp; Budgets
        </Text>
        <ExportMenu budgets={filtered} />
      </Stack>

      {multiCurrency && (
        <MessageBar messageBarType={MessageBarType.error}>
          Multiple currencies exist ({currencies.join(", ")}) and are being rejected. All workspaces
          in a TRE instance must use a single billing currency.
        </MessageBar>
      )}

      <Stack horizontal tokens={{ childrenGap: 24 }} wrap>
        <SummaryCard label="Total allocated" value={totals.asString(totals.totalAllocated)} />
        <SummaryCard label="Total consumed" value={totals.asString(totals.totalConsumed)} />
        <SummaryCard
          label="Total remaining"
          value={totals.asString(Math.max(totals.totalAllocated - totals.totalConsumed, 0))}
        />
        <SummaryCard label="Workspaces" value={String(budgets.length)} />
      </Stack>

      <Stack horizontal tokens={{ childrenGap: 12 }} verticalAlign="end" wrap>
        <SearchBox
          placeholder="Search by workspace name or ID..."
          value={search}
          onChange={(_, v) => {
            setSearch(v || "");
            setPage(0);
          }}
          onClear={() => setSearch("")}
          styles={{ root: { width: 320 } }}
        />
        <Dropdown
          selectedKey={statusFilter}
          options={statusOptions}
          onChange={(_, opt) => {
            setStatusFilter((opt?.key as string) ?? "all");
            setPage(0);
          }}
          styles={{ root: { width: 200 } }}
        />
        <Text variant="small" styles={{ root: { color: "#605e5c", paddingBottom: 6 } }}>
          {filtered.length} of {budgets.length} workspaces
        </Text>
      </Stack>

      <DetailsList
        items={pageRows}
        columns={columns}
        selectionMode={SelectionMode.none}
        layoutMode={DetailsListLayoutMode.justified}
        compact
      />

      {pageCount > 1 && (
        <Stack horizontal verticalAlign="center" horizontalAlign="center" tokens={{ childrenGap: 12 }}>
          <DefaultButton
            text="Previous"
            iconProps={{ iconName: "ChevronLeft" }}
            disabled={safePage === 0}
            onClick={() => setPage(Math.max(0, safePage - 1))}
          />
          <Text>
            Page {safePage + 1} of {pageCount}
          </Text>
          <DefaultButton
            text="Next"
            iconProps={{ iconName: "ChevronRight" }}
            disabled={safePage >= pageCount - 1}
            onClick={() => setPage(Math.min(pageCount - 1, safePage + 1))}
          />
        </Stack>
      )}
    </Stack>
  );
};

const SummaryCard: React.FunctionComponent<{ label: string; value: string }> = ({
  label,
  value,
}) => (
  <Stack
    styles={{
      root: {
        padding: "12px 20px",
        border: "1px solid #edebe9",
        borderRadius: 6,
        minWidth: 160,
        background: "#faf9f8",
      },
    }}
  >
    <Text variant="small" styles={{ root: { color: "#605e5c" } }}>
      {label}
    </Text>
    <Text variant="xLarge" styles={{ root: { fontWeight: 600 } }}>
      {value}
    </Text>
  </Stack>
);
