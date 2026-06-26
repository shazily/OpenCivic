/**
 * Browser API client for publisher actions (create dataset, upload).
 * Uses in-memory session token when available.
 */

import { getAccessToken } from "@/lib/auth/session";
import type {
  ApiResponse,
  Dataset,
  DatasetEnvelope,
  DatasetListEnvelope,
  LineageEdge,
  LineageGraphEnvelope,
  LineageNode,
  UploadEnvelope,
} from "@/lib/api/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100/api/v1";

function devToken(): string | null {
  return process.env.NEXT_PUBLIC_DEV_AUTH_TOKEN || null;
}

function stewardToken(): string | null {
  return process.env.NEXT_PUBLIC_STEWARD_AUTH_TOKEN || devToken();
}

function authToken(): string | null {
  if (typeof window !== "undefined") {
    return getAccessToken() || devToken();
  }
  return devToken();
}

async function request<T>(
  method: string,
  path: string,
  options?: { body?: unknown; formData?: FormData; token?: string | null },
): Promise<T> {
  const headers: Record<string, string> = {};
  const token = options?.token === undefined ? authToken() : options.token;
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const init: RequestInit = { method, headers };
  if (options?.formData) {
    init.body = options.formData;
  } else if (options?.body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(`${API_BASE}${path}`, init);
  const json = (await response.json()) as T;
  if (!response.ok) {
    const envelope = json as ApiResponse<unknown>;
    const message = envelope.errors?.[0]?.message || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return json;
}

export async function createDataset(payload: {
  title: string;
  slug: string;
  description?: string;
}): Promise<DatasetEnvelope> {
  return request<DatasetEnvelope>("POST", "/datasets/", { body: payload });
}

export async function uploadDatasetFile(
  datasetId: string,
  file: File,
): Promise<UploadEnvelope> {
  const CHUNK_SIZE = 5 * 1024 * 1024;
  if (file.size > CHUNK_SIZE) {
    return uploadDatasetFileChunked(datasetId, file, CHUNK_SIZE);
  }
  const formData = new FormData();
  formData.append("file", file);
  return request<UploadEnvelope>("POST", `/datasets/${datasetId}/upload`, { formData });
}

export async function uploadDatasetFileChunked(
  datasetId: string,
  file: File,
  chunkSize = 5 * 1024 * 1024,
): Promise<UploadEnvelope> {
  const session = await request<{
    data: { session_id: string; chunk_size: number; total_chunks: number };
  }>("POST", `/datasets/${datasetId}/upload/sessions`, {
    body: { filename: file.name, total_size: file.size },
  });
  const { session_id: sessionId, total_chunks: totalChunks } = session.data;
  for (let index = 0; index < totalChunks; index += 1) {
    const start = index * chunkSize;
    const end = Math.min(start + chunkSize, file.size);
    const chunk = file.slice(start, end);
    const formData = new FormData();
    formData.append("file", chunk, `chunk-${index}.bin`);
    await request(
      "PUT",
      `/datasets/${datasetId}/upload/sessions/${sessionId}/chunks/${index}`,
      { formData },
    );
  }
  return request<UploadEnvelope>(
    "POST",
    `/datasets/${datasetId}/upload/sessions/${sessionId}/complete`,
  );
}

export async function getPublisherSummaryClient(): Promise<{
  data: {
    dataset_count: number;
    published_count: number;
    views: number;
    downloads: number;
    api_calls: number;
    ai_queries: number;
  };
}> {
  return request("GET", "/analytics/publisher/summary");
}

export async function getPublisherWorkflowTimelineClient(): Promise<{
  data: Array<{
    id: number;
    event_type: string;
    dataset_id: string;
    created_at: string;
    payload: Record<string, unknown>;
  }>;
}> {
  return request("GET", "/workflow/publisher/timeline");
}

export async function getDatasetClient(id: string): Promise<DatasetEnvelope> {
  return request<DatasetEnvelope>("GET", `/datasets/${id}`);
}

export async function getDatasetDataClient(
  id: string,
  pageSize = 50,
): Promise<{ data: Record<string, unknown>[] }> {
  return request("GET", `/datasets/${id}/data?page_size=${pageSize}`);
}

export async function listMyDatasets(): Promise<DatasetListEnvelope> {
  return request<DatasetListEnvelope>("GET", "/datasets/?page_size=100&mine=true");
}

export async function chatWithDatasetClient(
  datasetId: string,
  question: string,
): Promise<{
  data: {
    answer: string;
    confidence?: number;
    ai_assisted?: boolean;
    watermark?: string | null;
    citation?: { query?: string | null; columns?: string[]; rows?: unknown[] };
  };
}> {
  return request("POST", `/datasets/${datasetId}/chat`, {
    body: { question },
    token: null,
  });
}

export async function suggestMetadataClient(
  datasetId: string,
): Promise<{
  data: {
    description?: string;
    tags?: string[];
    metadata?: Record<string, unknown>;
    ai_assisted?: boolean;
  };
}> {
  return request("POST", `/datasets/${datasetId}/suggest-metadata`);
}

export async function getDownloadUrlClient(
  datasetId: string,
  format: "parquet" | "csv" | "json" = "parquet",
): Promise<{ data: { url: string; expires_in: number } }> {
  return request("GET", `/datasets/${datasetId}/download-url?format=${format}`, { token: null });
}

export async function updateDatasetMetadata(
  datasetId: string,
  payload: {
    title?: string;
    description?: string;
    tags?: string[];
    metadata?: Record<string, unknown>;
  },
): Promise<DatasetEnvelope> {
  return request<DatasetEnvelope>("PATCH", `/datasets/${datasetId}`, { body: payload });
}

export async function submitDatasetForReview(
  datasetId: string,
  notes = "",
): Promise<{ data: { id: string; status: string } }> {
  return request("POST", `/datasets/${datasetId}/submit`, { body: { notes } });
}

export async function approveSubmission(
  submissionId: string,
  notes = "",
): Promise<{ data: { status: string } }> {
  const adminToken =
    process.env.NEXT_PUBLIC_ADMIN_AUTH_TOKEN ||
    (typeof window !== "undefined"
      ? localStorage.getItem("opencivic_access_token")
      : null) ||
    devToken();
  return request("POST", `/workflow/${submissionId}/approve`, {
    body: { notes },
    token: adminToken,
  });
}

export async function scheduleDatasetEmbargo(
  datasetId: string,
  embargoUntil: string,
): Promise<DatasetEnvelope> {
  return request<DatasetEnvelope>("POST", `/datasets/${datasetId}/schedule`, {
    body: { embargo_until: embargoUntil },
    token: stewardToken() || authToken(),
  });
}

export async function getLineageClient(datasetId: string): Promise<LineageGraphEnvelope> {
  return request<LineageGraphEnvelope>("GET", `/datasets/${datasetId}/lineage`, {
    token: stewardToken() || authToken(),
  });
}

export async function submitFeedbackClient(payload: {
  dataset_id: string;
  type: string;
  rating?: number;
  content?: string;
}): Promise<{ data: { id: string } }> {
  return request("POST", "/feedback/", { body: payload, token: null });
}

export async function listFeedbackForDataset(
  datasetId: string,
): Promise<{
  data: Array<{
    id: string;
    dataset_id: string;
    type: string;
    rating: number | null;
    content: string | null;
    status: string;
    created_at: string;
  }>;
}> {
  return request("GET", `/feedback/?dataset_id=${datasetId}`);
}

export async function recordDatasetDownload(
  datasetId: string,
  format: "csv" | "json" | "parquet",
): Promise<void> {
  await request("POST", `/datasets/${datasetId}/download`, {
    body: { format },
    token: null,
  });
}

export async function reviewSubmission(
  submissionId: string,
  action: "approve" | "reject" | "request_changes",
  notes = "",
): Promise<{ data: { status: string } }> {
  return request("POST", `/workflow/${submissionId}/review`, {
    body: { action, notes },
    token: stewardToken() || authToken(),
  });
}

export type { Dataset };
