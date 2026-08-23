export type MonitorStatus = "UP" | "DOWN" | "PENDING" | "UNKNOWN";
export type HttpMethod = "GET" | "HEAD" | "POST" | "PUT" | "PATCH" | "DELETE";
export type StatsPeriod = "1h" | "24h" | "7d" | "30d";
export type CheckErrorType =
  | "TIMEOUT"
  | "CONNECTION"
  | "DNS"
  | "SSL"
  | "STATUS_CODE"
  | "INVALID_URL"
  | "UNKNOWN";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface Monitor {
  id: string;
  user_id: string;
  name: string;
  url: string;
  method: HttpMethod;
  expected_status_code: number;
  interval: number;
  timeout: number;
  enabled: boolean;
  status: MonitorStatus;
  latency_ms: number | null;
  failure_count: number;
  consecutive_failure_count: number;
  last_checked_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MonitorListResponse {
  items: Monitor[];
  total: number;
  offset: number;
  limit: number;
}

export interface MonitorCreatePayload {
  name: string;
  url: string;
  method?: HttpMethod;
  expected_status_code?: number;
  interval?: number;
  timeout?: number;
  enabled?: boolean;
}

export interface Check {
  id: string;
  monitor_id: string;
  status_code: number | null;
  response_time_ms: number | null;
  success: boolean;
  error_type: CheckErrorType | null;
  error_message: string | null;
  attempt_number: number;
  checked_at: string;
}

export interface CheckListResponse {
  items: Check[];
  next_cursor: string | null;
  limit: number;
}

export interface LatencyStats {
  latest: number | null;
  avg: number | null;
  min: number | null;
  max: number | null;
  p95: number | null;
}

export interface MonitorStats {
  monitor_id: string;
  period: StatsPeriod;
  from: string;
  to: string;
  total_checks: number;
  successful_checks: number;
  uptime_percentage: number | null;
  latency_ms: LatencyStats;
}

export interface DashboardSummary {
  period: StatsPeriod;
  from: string;
  to: string;
  total_monitors: number;
  up_monitors: number;
  down_monitors: number;
  overall_uptime_percentage: number | null;
  average_latency_ms: number | null;
}

export interface MonitorWithStats extends Monitor {
  uptime_percentage: number | null;
}
