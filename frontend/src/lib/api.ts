import { clearToken, getToken } from "@/lib/auth";
import type {
  ApiErrorBody,
  Check,
  CheckListResponse,
  DashboardSummary,
  Monitor,
  MonitorCreatePayload,
  MonitorListResponse,
  MonitorStats,
  StatsPeriod,
  TokenResponse,
  User,
} from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
    if (response.status === 401 && typeof window !== "undefined") {
      clearToken();
    }
    throw new ApiError(
      body?.error?.code ?? "UNKNOWN",
      body?.error?.message ?? response.statusText,
      response.status,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  register(email: string, password: string): Promise<User> {
    return request<User>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  login(email: string, password: string): Promise<TokenResponse> {
    return request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  getMe(): Promise<User> {
    return request<User>("/api/v1/auth/me");
  },

  listMonitors(offset = 0, limit = 50): Promise<MonitorListResponse> {
    return request<MonitorListResponse>(
      `/api/v1/monitors?offset=${offset}&limit=${limit}`,
    );
  },

  getMonitor(id: string): Promise<Monitor> {
    return request<Monitor>(`/api/v1/monitors/${id}`);
  },

  createMonitor(payload: MonitorCreatePayload): Promise<Monitor> {
    return request<Monitor>("/api/v1/monitors", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  deleteMonitor(id: string): Promise<void> {
    return request<void>(`/api/v1/monitors/${id}`, { method: "DELETE" });
  },

  triggerCheck(id: string): Promise<Check> {
    return request<Check>(`/api/v1/monitors/${id}/check`, { method: "POST" });
  },

  listChecks(id: string, limit = 100): Promise<CheckListResponse> {
    return request<CheckListResponse>(
      `/api/v1/monitors/${id}/checks?limit=${limit}`,
    );
  },

  getMonitorStats(id: string, period: StatsPeriod = "24h"): Promise<MonitorStats> {
    return request<MonitorStats>(`/api/v1/monitors/${id}/stats?period=${period}`);
  },

  getDashboardSummary(period: StatsPeriod = "24h"): Promise<DashboardSummary> {
    return request<DashboardSummary>(`/api/v1/dashboard/summary?period=${period}`);
  },
};
