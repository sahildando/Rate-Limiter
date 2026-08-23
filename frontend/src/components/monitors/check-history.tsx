import { formatDateTime } from "@/lib/format";
import type { Check } from "@/lib/types";

interface CheckHistoryProps {
  checks: Check[];
}

export function CheckHistory({ checks }: CheckHistoryProps) {
  if (checks.length === 0) {
    return (
      <p className="rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-8 text-center text-sm text-slate-500">
        No checks recorded yet
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800">
      <table className="min-w-full divide-y divide-slate-800 text-sm">
        <thead className="bg-slate-900/80 text-left text-slate-400">
          <tr>
            <th className="px-4 py-3 font-medium">Time</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Code</th>
            <th className="px-4 py-3 font-medium">Latency</th>
            <th className="px-4 py-3 font-medium">Error</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 bg-slate-950/40">
          {checks.map((check) => (
            <tr key={check.id}>
              <td className="px-4 py-3 text-slate-300">{formatDateTime(check.checked_at)}</td>
              <td className="px-4 py-3">
                <span
                  className={
                    check.success ? "text-emerald-400" : "text-rose-400"
                  }
                >
                  {check.success ? "Success" : "Failed"}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-300">{check.status_code ?? "—"}</td>
              <td className="px-4 py-3 text-slate-300">
                {check.response_time_ms !== null ? `${check.response_time_ms}ms` : "—"}
              </td>
              <td className="px-4 py-3 text-slate-400">
                {check.error_type ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
