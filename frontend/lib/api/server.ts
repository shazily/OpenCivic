/**
 * Server-side API fetch for SSR pages.
 * Public catalog calls never send auth tokens — RLS returns published public datasets only.
 */

import type {
  DatasetConnectorStatus,
  DatasetDataEnvelope,
  DatasetEnvelope,
  DatasetListEnvelope,
  LineageGraphEnvelope,
  GovernanceSummaryEnvelope,
  WorkflowQueueEnvelope,
} from "@/lib/api/types";

function apiBaseUrl(): string {
  return (
    process.env.OPENCIVIC_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8100/api/v1"
  );
}

interface FetchOptions extends RequestInit {
  authToken?: string | null;
}

async function serverFetch<T>(path: string, init?: FetchOptions): Promise<T> {
  const { authToken, ...requestInit } = init ?? {};
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(requestInit.headers as Record<string, string> | undefined),
  };

  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...requestInit,
    headers,
    next: { revalidate: 30 },
  });

  if (!response.ok) {
    throw new Error(`API ${response.status} for ${path}`);
  }

  return response.json() as Promise<T>;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export interface PublicCatalogParams {
  pageSize?: number;
  cursor?: string;
  tag?: string;
  sort?: string;
}

/** Public catalog list — no auth; published datasets only. */
export async function listPublicDatasetsServer(
  params: PublicCatalogParams = {},
): Promise<DatasetListEnvelope> {
  const { pageSize = 20, cursor, tag, sort } = params;
  const query = buildQuery({
    page_size: pageSize,
    cursor,
    "filter[tag]": tag,
    sort,
  });
  return serverFetch<DatasetListEnvelope>(`/datasets${query}`, { authToken: null });
}

/** Public catalog search — no auth; published datasets only. */
export async function searchPublicDatasetsServer(
  q: string,
  params: PublicCatalogParams = {},
): Promise<DatasetListEnvelope> {
  const { pageSize = 20, cursor, tag } = params;
  const query = buildQuery({
    q,
    page_size: pageSize,
    cursor,
    "filter[tag]": tag,
  });
  return serverFetch<DatasetListEnvelope>(`/search${query}`, { authToken: null });
}

export async function getPublicDatasetServer(id: string): Promise<DatasetEnvelope> {
  return serverFetch<DatasetEnvelope>(`/datasets/${id}`, { authToken: null });
}

export async function getPublicDatasetDataServer(
  id: string,
  pageSize = 50,
): Promise<DatasetDataEnvelope> {
  return serverFetch<DatasetDataEnvelope>(
    `/datasets/${id}/data?page_size=${pageSize}`,
    { authToken: null },
  );
}

export async function getPublicLineageServer(id: string): Promise<LineageGraphEnvelope> {
  return serverFetch<LineageGraphEnvelope>(`/datasets/${id}/lineage`, { authToken: null });
}

export async function getPublicDatasetStatsServer(id: string): Promise<{
  data: {
    views: number;
    downloads: number;
    api_calls: number;
    feedback_count: number;
    average_rating: number | null;
  };
}> {
  return serverFetch(`/analytics/datasets/${id}/summary`, { authToken: null });
}

export async function getPublicDatasetTrendServer(id: string): Promise<{
  data: Array<{
    date: string;
    views: number;
    downloads: number;
    total: number;
  }>;
}> {
  return serverFetch(`/analytics/datasets/${id}/trend`, { authToken: null });
}

export async function getPublicDatasetConnectorServer(id: string): Promise<{
  data: DatasetConnectorStatus | null;
}> {
  return serverFetch(`/datasets/${id}/connector`, { authToken: null });
}

/** Staff-only: list all tenant datasets (includes drafts when authenticated). */
export async function listDatasetsServer(pageSize = 20): Promise<DatasetListEnvelope> {
  const token = process.env.OPENCIVIC_DEV_AUTH_TOKEN;
  return serverFetch<DatasetListEnvelope>(`/datasets/?page_size=${pageSize}`, {
    authToken: token,
  });
}

export async function searchDatasetsServer(
  query: string,
  pageSize = 20,
): Promise<DatasetListEnvelope> {
  const token = process.env.OPENCIVIC_DEV_AUTH_TOKEN;
  return serverFetch<DatasetListEnvelope>(
    `/search/?q=${encodeURIComponent(query)}&page_size=${pageSize}`,
    { authToken: token },
  );
}

export async function getDatasetServer(id: string): Promise<DatasetEnvelope> {
  const token = process.env.OPENCIVIC_DEV_AUTH_TOKEN;
  return serverFetch<DatasetEnvelope>(`/datasets/${id}`, { authToken: token });
}

export async function getDatasetDataServer(
  id: string,
  pageSize = 50,
): Promise<DatasetDataEnvelope> {
  const token = process.env.OPENCIVIC_DEV_AUTH_TOKEN;
  return serverFetch<DatasetDataEnvelope>(`/datasets/${id}/data?page_size=${pageSize}`, {
    authToken: token,
  });
}

export async function listWorkflowQueueServer(): Promise<WorkflowQueueEnvelope> {
  const token =
    process.env.OPENCIVIC_STEWARD_AUTH_TOKEN || process.env.OPENCIVIC_DEV_AUTH_TOKEN;
  return serverFetch<WorkflowQueueEnvelope>("/workflow/queue", { authToken: token });
}

export async function getGovernanceSummaryServer(): Promise<GovernanceSummaryEnvelope> {
  const token =
    process.env.OPENCIVIC_STEWARD_AUTH_TOKEN || process.env.OPENCIVIC_DEV_AUTH_TOKEN;
  return serverFetch<GovernanceSummaryEnvelope>("/workflow/governance/summary", {
    authToken: token,
  });
}

export async function listApprovalQueueServer(): Promise<WorkflowQueueEnvelope> {
  const token =
    process.env.OPENCIVIC_ADMIN_AUTH_TOKEN || process.env.OPENCIVIC_DEV_AUTH_TOKEN;
  return serverFetch<WorkflowQueueEnvelope>("/workflow/approval-queue", { authToken: token });
}
