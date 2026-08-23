import { statusColor } from "@/lib/format";
import type { MonitorStatus } from "@/lib/types";

interface StatusBadgeProps {
  status: MonitorStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${statusColor(status)}`}
    >
      {status}
    </span>
  );
}
