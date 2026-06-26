/**
 * Browser admin API client (uses session token from staff login).
 */

import { getAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100/api/v1";

function adminToken(): string | null {
  if (typeof window !== "undefined") {
    return getAccessToken() || process.env.NEXT_PUBLIC_ADMIN_AUTH_TOKEN || null;
  }
  return process.env.NEXT_PUBLIC_ADMIN_AUTH_TOKEN || null;
}

async function adminRequest<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const token = adminToken();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const init: RequestInit = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const response = await fetch(`${API_BASE}${path}`, init);
  const json = (await response.json()) as T & { errors?: Array<{ message: string }> };
  if (!response.ok) {
    throw new Error(json.errors?.[0]?.message || `Request failed (${response.status})`);
  }
  return json;
}

export async function createConnectorClient(payload: {
  name: string;
  type: string;
  config: Record<string, unknown>;
}): Promise<{ data: { id: string } }> {
  return adminRequest("POST", "/connectors/", payload);
}

export async function testConnectorClient(
  connectorId: string,
): Promise<{ data: { ok: boolean; message: string } }> {
  return adminRequest("POST", `/connectors/${connectorId}/test`);
}

export async function syncConnectorClient(
  connectorId: string,
): Promise<{ data: { job_id: string; status: string } }> {
  return adminRequest("POST", `/connectors/${connectorId}/sync`);
}

export interface BrandingData {
  tenant_id: string;
  slug: string;
  display_name: string;
  branding: {
    primary_color?: string;
    primary_hover_color?: string;
    accent_color?: string;
    logo_url?: string;
    display_name?: string;
  };
}

export async function getAdminBranding(): Promise<{ data: BrandingData }> {
  return adminRequest("GET", "/admin/branding");
}

export async function patchAdminBranding(payload: {
  display_name?: string;
  primary_color?: string;
  primary_hover_color?: string;
  accent_color?: string;
  logo_url?: string;
}): Promise<{ data: BrandingData }> {
  return adminRequest("PATCH", "/admin/branding", payload);
}
