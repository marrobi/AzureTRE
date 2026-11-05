export const formatDate = (value: string | null | undefined) => (value ? new Date(value).toLocaleString() : "");

export const formatShortDate = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }) : "";

export function formatDuration(start: string | null, end: string | null): string {
  if (!start) return "";
  const ms = (end ? new Date(end) : new Date()).getTime() - new Date(start).getTime();
  const total = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h ? `${h}h ${m}m` : m ? `${m}m ${s}s` : `${s}s`;
}

export function formatSize(size: number | null | undefined): string {
  if (size === null || size === undefined) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = size;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit++;
  }
  return unit === 0 ? `${value} B` : `${value.toFixed(1)} ${units[unit]}`;
}
