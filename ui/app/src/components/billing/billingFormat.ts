export const formatCurrency = (value: number, currency = "USD"): string =>
  new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);

export const formatPercent = (value: number): string => `${Math.round(value)}%`;

export const statusColor: Record<string, string> = {
  ok: "#107c10", // green
  warning: "#f7630c", // orange
  over: "#d13438", // red
  stopped: "#5c2e91", // purple
};

export const statusLabel: Record<string, string> = {
  ok: "On track",
  warning: "Approaching limit",
  over: "Over budget",
  stopped: "Stopped",
};
