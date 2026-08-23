import type { DashboardSummary } from "@/lib/types";
import { formatLatency, formatUptime } from "@/lib/format";

interface SummaryCardsProps {
  summary: DashboardSummary;
}

const CARDS = [
  { key: "total_monitors", label: "Total Monitors", format: (v: number) => String(v) },
  { key: "up_monitors", label: "UP", format: (v: number) => String(v) },
  { key: "down_monitors", label: "DOWN", format: (v: number) => String(v) },
  {
    key: "average_latency_ms",
    label: "Avg Latency",
    format: (v: number | null) => formatLatency(v),
  },
  {
    key: "overall_uptime_percentage",
    label: "Overall Uptime",
    format: (v: number | null) => formatUptime(v),
  },
] as const;

export function SummaryCards({ summary }: SummaryCardsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {CARDS.map((card) => {
        const value = summary[card.key];
        return (
          <div
            key={card.key}
            className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg shadow-black/20"
          >
            <p className="text-sm text-slate-400">{card.label}</p>
            <p className="mt-2 text-2xl font-semibold text-white">
              {card.format(value as never)}
            </p>
          </div>
        );
      })}
    </div>
  );
}
