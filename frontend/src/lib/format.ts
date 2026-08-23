import type { MonitorStatus } from "@/lib/types";

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (Number.isInteger(ms)) return `${ms}ms`;
  return `${ms.toFixed(1)}ms`;
}

export function formatUptime(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(2)}%`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export function statusLabel(status: MonitorStatus): string {
  return status;
}

export function statusColor(status: MonitorStatus): string {
  switch (status) {
    case "UP":
      return "text-emerald-400 bg-emerald-400/10 ring-emerald-400/30";
    case "DOWN":
      return "text-rose-400 bg-rose-400/10 ring-rose-400/30";
    case "PENDING":
      return "text-amber-400 bg-amber-400/10 ring-amber-400/30";
    default:
      return "text-slate-400 bg-slate-400/10 ring-slate-400/30";
  }
}
