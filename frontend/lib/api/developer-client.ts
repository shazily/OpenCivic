/**
 * Browser developer API client.
 */

import { getAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100/api/v1";

function developerToken(): string | null {
  if (typeof window !== "undefined") {
    return (
      getAccessToken() ||
      process.env.NEXT_PUBLIC_DEVELOPER_AUTH_TOKEN ||
      process.env.NEXT_PUBLIC_DEV_AUTH_TOKEN ||
      null
    );
  }
  return process.env.NEXT_PUBLIC_DEVELOPER_AUTH_TOKEN || null;
}

async function developerRequest<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const token = developerToken();
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

export async function createApiKeyClient(
  name: string,
  scopes: string[],
): Promise<{ data: { id: string; raw_key: string } }> {
  return developerRequest("POST", "/api-keys/", { name, scopes });
}

export async function revokeApiKeyClient(keyId: string): Promise<{ data: { id: string } }> {
  return developerRequest("DELETE", `/api-keys/${keyId}`);
}

export async function createWebhookClient(
  url: string,
  events: string[],
): Promise<{ data: { id: string; url: string } }> {
  return developerRequest("POST", "/webhooks/", { url, events });
}

export async function deleteWebhookClient(webhookId: string): Promise<{ data: { id: string } }> {
  return developerRequest("DELETE", `/webhooks/${webhookId}`);
}

export async function testWebhookClient(
  webhookId: string,
): Promise<{ data: { status: string; status_code?: number } }> {
  return developerRequest("POST", `/webhooks/${webhookId}/test`);
}
