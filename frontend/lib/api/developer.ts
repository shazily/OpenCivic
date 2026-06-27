function apiBaseUrl(): string {
  return (
    process.env.OPENCIVIC_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8100/api/v1"
  );
}

function developerToken(): string | undefined {
  return (
    process.env.OPENCIVIC_DEVELOPER_AUTH_TOKEN ||
    process.env.NEXT_PUBLIC_DEVELOPER_AUTH_TOKEN ||
    process.env.OPENCIVIC_DEV_AUTH_TOKEN
  );
}

async function developerFetch<T>(path: string): Promise<T> {
  const token = developerToken();
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

export async function listApiKeysServer(): Promise<{
  data: Array<{
    id: string;
    name: string;
    key_prefix: string;
    scopes: string[];
    revoked_at: string | null;
    created_at: string;
  }>;
  meta: { total_count?: number };
}> {
  return developerFetch("/api-keys/");
}

export async function getDeveloperSdkServer(): Promise<{
  data: { python: string; javascript: string; curl: string };
}> {
  return developerFetch("/api-keys/sdk-snippets");
}

export async function listWebhooksServer(): Promise<{
  data: Array<{
    id: string;
    url: string;
    events: string[];
    status: string;
    failure_count: number;
    created_at: string;
  }>;
}> {
  return developerFetch("/webhooks/");
}

export async function listRequestLogsServer(): Promise<{
  data: Array<{
    id: number;
    dataset_id: string | null;
    event_type: string;
    api_key_id: string | null;
    format: string | null;
    response_ms: number | null;
    created_at: string;
  }>;
}> {
  return developerFetch("/analytics/request-logs");
}

export async function getRateLimitGaugesServer(): Promise<{
  data: Array<{
    api_key_id: string;
    name: string;
    key_prefix: string;
    limit_per_minute: number;
    used_last_minute: number;
    remaining: number;
    utilization_pct: number;
  }>;
  meta: { total_count?: number; tenant_limit_per_minute?: number };
}> {
  return developerFetch("/analytics/rate-limits");
}
