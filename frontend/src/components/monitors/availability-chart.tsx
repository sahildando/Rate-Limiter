"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Check } from "@/lib/types";

interface AvailabilityChartProps {
  checks: Check[];
}

function bucketChecks(checks: Check[]) {
  const buckets = new Map<string, { total: number; success: number }>();

  for (const check of checks) {
    const date = new Date(check.checked_at);
    const key = `${date.toLocaleDateString()} ${date.getHours()}:00`;
    const current = buckets.get(key) ?? { total: 0, success: 0 };
    current.total += 1;
    if (check.success) current.success += 1;
    buckets.set(key, current);
  }

  return Array.from(buckets.entries()).map(([label, value]) => ({
    label,
    uptime: value.total === 0 ? 0 : Number(((value.success / value.total) * 100).toFixed(1)),
  }));
}

export function AvailabilityChart({ checks }: AvailabilityChartProps) {
  const data = bucketChecks(
    [...checks].sort(
      (a, b) => new Date(a.checked_at).getTime() - new Date(b.checked_at).getTime(),
    ),
  );

  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/40 text-sm text-slate-500">
        No availability data in this window
      </div>
    );
  }

  return (
    <div className="h-64 rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="label" stroke="#94a3b8" fontSize={11} />
          <YAxis stroke="#94a3b8" fontSize={12} domain={[0, 100]} unit="%" />
          <Tooltip
            contentStyle={{
              background: "#0f172a",
              border: "1px solid #334155",
              borderRadius: "0.75rem",
            }}
          />
          <Bar dataKey="uptime" fill="#34d399" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
