function apiBaseUrl(): string {
  return (
    process.env.OPENCIVIC_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8100/api/v1"
  );
}

function adminToken(): string | undefined {
  return process.env.OPENCIVIC_ADMIN_AUTH_TOKEN || process.env.OPENCIVIC_DEV_AUTH_TOKEN;
}

async function adminFetch<T>(path: string): Promise<T> {
  const token = adminToken();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${apiBaseUrl()}${path}`, { headers, cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API ${response.status} for ${path}`);
  }
  return response.json() as Promise<T>;
}

export interface AdminOverview {
  health: Record<string, string>;
  deployment_mode: string;
  version: string;
  connectors: Array<{
    id: string;
    name: string;
    type: string;
    status: string;
    circuit_state: string;
    failure_count: number;
    last_sync_at: string | null;
  }>;
  backup_status: string;
  backup_verified_at?: string | null;
  backup_message?: string | null;
  security_events_count: number;
}

export interface OrgUsageSummary {
  user_count: number;
  dataset_count: number;
  published_count: number;
  views: number;
  downloads: number;
  api_calls: number;
  ai_queries: number;
}

export async function getAdminOverviewServer(): Promise<{ data: AdminOverview }> {
  return adminFetch("/admin/overview");
}

export async function getOrgUsageSummaryServer(): Promise<{ data: OrgUsageSummary }> {
  return adminFetch("/analytics/org/summary");
}

export interface ConnectorListItem {
  id: string;
  name: string;
  type: string;
  status: string;
  circuit_state: string;
  failure_count: number;
  last_sync_at: string | null;
  next_sync_at?: string | null;
}

export async function listConnectorsServer(): Promise<{
  data: ConnectorListItem[];
}> {
  const response = await adminFetch<{ data: unknown[] }>("/connectors/");
  return { data: response.data as ConnectorListItem[] };
}

export interface JobsSummary {
  queues: Array<{
    name: string;
    depth: number;
    status: string;
    depth_trend?: number[];
  }>;
  source: string;
  total_depth: number;
  worker_count: number | null;
}

export async function getJobsSummaryServer(): Promise<{ data: JobsSummary }> {
  return adminFetch("/admin/jobs/summary");
}

export interface DeepHealth {
  status: string;
  version: string;
  deployment_mode: string;
  ai_mode: string;
  checks: Record<string, string>;
}

export async function getDeepHealthServer(): Promise<{ data: DeepHealth }> {
  return adminFetch("/health/deep");
}

export interface SecurityEvent {
  id: number;
  event_type: string;
  aggregate_id: string;
  aggregate_type: string;
  actor_id: string | null;
  actor_type: string;
  created_at: string;
  payload: Record<string, unknown>;
}

export async function getSecurityEventsServer(): Promise<{ data: SecurityEvent[] }> {
  return adminFetch("/admin/security-events?limit=50");
}
