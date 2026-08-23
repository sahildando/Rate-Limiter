"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { MonitorCard } from "@/components/dashboard/monitor-card";
import { SummaryCards } from "@/components/dashboard/summary-cards";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorAlert } from "@/components/ui/error-alert";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import type { DashboardSummary, MonitorWithStats } from "@/lib/types";

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [monitors, setMonitors] = useState<MonitorWithStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [summaryData, monitorList] = await Promise.all([
          api.getDashboardSummary("24h"),
          api.listMonitors(),
        ]);

        const monitorsWithStats = await Promise.all(
          monitorList.items.map(async (monitor) => {
            try {
              const stats = await api.getMonitorStats(monitor.id, "24h");
              return { ...monitor, uptime_percentage: stats.uptime_percentage };
            } catch {
              return { ...monitor, uptime_percentage: null };
            }
          }),
        );

        setSummary(summaryData);
        setMonitors(monitorsWithStats);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, []);

  if (loading) {
    return <LoadingSpinner label="Loading dashboard..." />;
  }

  if (error) {
    return <ErrorAlert message={error} title="Dashboard unavailable" />;
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
          <p className="mt-1 text-slate-400">Overview of your monitored endpoints</p>
        </div>
        <Link
          href="/monitors/new"
          className="inline-flex items-center justify-center rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-cyan-400"
        >
          Add monitor
        </Link>
      </div>

      {summary ? <SummaryCards summary={summary} /> : null}

      <section>
        <h2 className="mb-4 text-lg font-medium text-white">Monitors</h2>
        {monitors.length === 0 ? (
          <EmptyState
            title="No monitors yet"
            description="Create your first monitor to start tracking uptime and latency."
            action={
              <Link
                href="/monitors/new"
                className="inline-flex rounded-lg bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950"
              >
                Create monitor
              </Link>
            }
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {monitors.map((monitor) => (
              <MonitorCard key={monitor.id} monitor={monitor} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
