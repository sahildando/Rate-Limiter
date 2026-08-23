import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatLatency, formatUptime } from "@/lib/format";
import type { MonitorWithStats } from "@/lib/types";

interface MonitorCardProps {
  monitor: MonitorWithStats;
}

export function MonitorCard({ monitor }: MonitorCardProps) {
  const subtitle =
    monitor.status === "DOWN" && monitor.latency_ms === null
      ? monitor.last_failure_at
        ? "Failed recently"
        : "Timeout"
      : formatLatency(monitor.latency_ms);

  return (
    <Link
      href={`/monitors/${monitor.id}`}
      className="group block rounded-2xl border border-slate-800 bg-slate-900/60 p-5 transition hover:border-cyan-500/40 hover:bg-slate-900"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-medium text-white group-hover:text-cyan-300">{monitor.name}</h3>
          <p className="mt-1 truncate text-sm text-slate-500">{monitor.url}</p>
        </div>
        <StatusBadge status={monitor.status} />
      </div>
      <div className="mt-6 flex items-end justify-between">
        <div>
          <p className="text-2xl font-semibold text-white">{subtitle}</p>
          <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">Latency</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-semibold text-cyan-300">
            {formatUptime(monitor.uptime_percentage)}
          </p>
          <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">Uptime (24h)</p>
        </div>
      </div>
    </Link>
  );
}
