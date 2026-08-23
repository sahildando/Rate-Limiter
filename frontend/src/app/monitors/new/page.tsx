"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { ErrorAlert } from "@/components/ui/error-alert";
import type { HttpMethod } from "@/lib/types";

export default function NewMonitorPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [url, setUrl] = useState("https://");
  const [method, setMethod] = useState<HttpMethod>("GET");
  const [interval, setInterval] = useState(60);
  const [timeout, setTimeout] = useState(5000);
  const [expectedStatusCode, setExpectedStatusCode] = useState(200);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const monitor = await api.createMonitor({
        name,
        url,
        method,
        interval,
        timeout,
        expected_status_code: expectedStatusCode,
      });
      router.push(`/monitors/${monitor.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create monitor");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link href="/dashboard" className="text-sm text-slate-400 hover:text-slate-200">
          ← Back to dashboard
        </Link>
        <h1 className="mt-3 text-3xl font-semibold text-white">New monitor</h1>
        <p className="mt-1 text-slate-400">Add an HTTP endpoint to monitor</p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-5 rounded-2xl border border-slate-800 bg-slate-900/60 p-6"
      >
        {error ? <ErrorAlert message={error} title="Could not create monitor" /> : null}

        <div>
          <label htmlFor="name" className="mb-1 block text-sm text-slate-300">
            Name
          </label>
          <input
            id="name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none ring-cyan-500 focus:ring-2"
          />
        </div>

        <div>
          <label htmlFor="url" className="mb-1 block text-sm text-slate-300">
            URL
          </label>
          <input
            id="url"
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none ring-cyan-500 focus:ring-2"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="method" className="mb-1 block text-sm text-slate-300">
              Method
            </label>
            <select
              id="method"
              value={method}
              onChange={(e) => setMethod(e.target.value as HttpMethod)}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none ring-cyan-500 focus:ring-2"
            >
              {["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="status" className="mb-1 block text-sm text-slate-300">
              Expected status
            </label>
            <input
              id="status"
              type="number"
              min={100}
              max={599}
              value={expectedStatusCode}
              onChange={(e) => setExpectedStatusCode(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none ring-cyan-500 focus:ring-2"
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="interval" className="mb-1 block text-sm text-slate-300">
              Interval (seconds)
            </label>
            <input
              id="interval"
              type="number"
              min={10}
              max={86400}
              value={interval}
              onChange={(e) => setInterval(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none ring-cyan-500 focus:ring-2"
            />
          </div>
          <div>
            <label htmlFor="timeout" className="mb-1 block text-sm text-slate-300">
              Timeout (ms)
            </label>
            <input
              id="timeout"
              type="number"
              min={1000}
              max={60000}
              value={timeout}
              onChange={(e) => setTimeout(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none ring-cyan-500 focus:ring-2"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-cyan-500 px-4 py-2.5 font-medium text-slate-950 transition hover:bg-cyan-400 disabled:opacity-60"
        >
          {loading ? "Creating..." : "Create monitor"}
        </button>
      </form>
    </div>
  );
}
