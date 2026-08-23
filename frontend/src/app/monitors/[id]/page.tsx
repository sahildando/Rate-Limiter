"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { AvailabilityChart } from "@/components/monitors/availability-chart";
import { CheckHistory } from "@/components/monitors/check-history";
import { LatencyChart } from "@/components/monitors/latency-chart";
import { StatusBadge } from "@/components/ui/status-badge";
import { ErrorAlert } from "@/components/ui/error-alert";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { formatDateTime, formatLatency, formatUptime } from "@/lib/format";
import type { Check, Monitor, MonitorStats, StatsPeriod } from "@/lib/types";

const PERIODS: StatsPeriod[] = ["1h", "24h", "7d", "30d"];

export default function MonitorDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const monitorId = params.id;

  const [monitor, setMonitor] = useState<Monitor | null>(null);
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [checks, setChecks] = useState<Check[]>([]);
  const [period, setPeriod] = useState<StatsPeriod>("24h");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setError(null);
      try {
        const [monitorData, statsData, checksData] = await Promise.all([
          api.getMonitor(monitorId),
          api.getMonitorStats(monitorId, period),
          api.listChecks(monitorId, 100),
        ]);
        if (cancelled) return;
        setMonitor(monitorData);
        setStats(statsData);
        setChecks(checksData.items);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load monitor");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [monitorId, period]);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const [monitorData, statsData, checksData] = await Promise.all([
        api.getMonitor(monitorId),
        api.getMonitorStats(monitorId, period),
        api.listChecks(monitorId, 100),
      ]);
      setMonitor(monitorData);
      setStats(statsData);
      setChecks(checksData.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load monitor");
    }
  }, [monitorId, period]);

  async function handleCheckNow() {
    setActionLoading(true);
    try {
      await api.triggerCheck(monitorId);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Check failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this monitor? This cannot be undone.")) return;
    setActionLoading(true);
    try {
      await api.deleteMonitor(monitorId);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
      setActionLoading(false);
    }
  }

  if (loading) {
    return <LoadingSpinner label="Loading monitor..." />;
  }

  if (error && !monitor) {
    return <ErrorAlert message={error} title="Monitor unavailable" />;
  }

  if (!monitor) {
    return <ErrorAlert message="Monitor not found" title="Not found" />;
  }

  const failures = checks.filter((check) => !check.success);

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <Link href="/dashboard" className="text-sm text-slate-400 hover:text-slate-200">
            ← Back to dashboard
          </Link>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold text-white">{monitor.name}</h1>
            <StatusBadge status={monitor.status} />
          </div>
          <p className="mt-2 text-slate-400">{monitor.url}</p>
          <p className="mt-1 text-sm text-slate-500">
            Last checked {formatDateTime(monitor.last_checked_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleCheckNow}
            disabled={actionLoading}
            className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-cyan-400 disabled:opacity-60"
          >
            {actionLoading ? "Running..." : "Check now"}
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={actionLoading}
            className="rounded-lg border border-rose-500/40 px-4 py-2 text-sm text-rose-300 hover:bg-rose-500/10 disabled:opacity-60"
          >
            Delete
          </button>
        </div>
      </div>

      {error ? <ErrorAlert message={error} /> : null}

      <div className="flex flex-wrap gap-2">
        {PERIODS.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setPeriod(value)}
            className={`rounded-lg px-3 py-1.5 text-sm ${
              period === value
                ? "bg-cyan-500 text-slate-950"
                : "border border-slate-700 text-slate-300 hover:bg-slate-900"
            }`}
          >
            {value}
          </button>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Uptime" value={formatUptime(stats?.uptime_percentage)} />
        <StatCard label="Latest latency" value={formatLatency(stats?.latency_ms.latest)} />
        <StatCard label="Avg latency" value={formatLatency(stats?.latency_ms.avg)} />
        <StatCard label="P95 latency" value={formatLatency(stats?.latency_ms.p95)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-lg font-medium text-white">Response time</h2>
          <LatencyChart checks={checks} />
        </section>
        <section>
          <h2 className="mb-3 text-lg font-medium text-white">Availability</h2>
          <AvailabilityChart checks={checks} />
        </section>
      </div>

      <section>
        <h2 className="mb-3 text-lg font-medium text-white">Recent checks</h2>
        <CheckHistory checks={checks.slice(0, 20)} />
      </section>

      <section>
        <h2 className="mb-3 text-lg font-medium text-white">
          Recent failures ({failures.length})
        </h2>
        <CheckHistory checks={failures.slice(0, 10)} />
      </section>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}
