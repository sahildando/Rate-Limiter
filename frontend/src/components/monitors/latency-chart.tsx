"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Check } from "@/lib/types";

interface LatencyChartProps {
  checks: Check[];
}

export function LatencyChart({ checks }: LatencyChartProps) {
  const data = [...checks]
    .filter((check) => check.success && check.response_time_ms !== null)
    .sort(
      (a, b) => new Date(a.checked_at).getTime() - new Date(b.checked_at).getTime(),
    )
    .map((check) => ({
      time: new Date(check.checked_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      latency: check.response_time_ms,
    }));

  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/40 text-sm text-slate-500">
        No latency data in this window
      </div>
    );
  }

  return (
    <div className="h-64 rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
          <YAxis stroke="#94a3b8" fontSize={12} unit="ms" />
          <Tooltip
            contentStyle={{
              background: "#0f172a",
              border: "1px solid #334155",
              borderRadius: "0.75rem",
            }}
          />
          <Line
            type="monotone"
            dataKey="latency"
            stroke="#22d3ee"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
