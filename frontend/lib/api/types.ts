/** Shared API types for the OpenCivic portal. */

export interface ApiError {
  code: string;
  message: string;
  field?: string | null;
}

export interface ApiResponse<T> {
  data: T | null;
  meta: Record<string, unknown>;
  errors: ApiError[];
}

export interface PaginationMeta {
  has_more: boolean;
  next_cursor: string | null;
  total_count: number;
}

export interface DatasetConnectorStatus {
  id: string;
  name: string;
  type: string;
  status: string;
  circuit_state: string;
  last_sync_at: string | null;
  next_sync_at?: string | null;
  sync_frequency?: string | null;
}

export interface Dataset {
  id: string;
  tenant_id: string;
  title: string;
  slug: string;
  description: string | null;
  status: string;
  access_level: string;
  licence_id: string | null;
  publisher_id: string;
  quality_score: number | null;
  staleness_state: string;
  row_count: number | null;
  file_size_bytes: number | null;
  schema_snapshot: { columns: Array<{ name: string; type: string; nullable: boolean }> } | null;
  tags: string[];
  metadata?: Record<string, unknown>;
  created_at: string;
  published_at: string | null;
}

export interface DatasetListEnvelope {
  data: Dataset[];
  meta: PaginationMeta;
  errors: ApiError[];
}

export interface DatasetEnvelope {
  data: Dataset;
  meta: Record<string, unknown>;
  errors: ApiError[];
}

export interface DatasetDataEnvelope {
  data: Record<string, unknown>[];
  meta: PaginationMeta;
  errors: ApiError[];
}

export interface UploadEnvelope {
  data: {
    job_id: string;
    storage_key: string;
    status: string;
  };
  meta: Record<string, unknown>;
  errors: ApiError[];
}

export interface WorkflowSubmission {
  id: string;
  dataset_id: string;
  maker_id: string;
  checker_id: string | null;
  status: string;
  maker_notes: string | null;
  checker_notes?: string | null;
  submitted_at: string;
  review_due_at: string | null;
  sla_breached?: boolean;
}

export interface GovernanceSummaryEnvelope {
  data: {
    pending_review: number;
    pending_approval: number;
    changes_requested: number;
    sla_breached: number;
    published_last_30_days: number;
  };
  meta: Record<string, unknown>;
  errors: unknown[];
}

export interface WorkflowQueueEnvelope {
  data: WorkflowSubmission[];
  meta: { total_count?: number };
  errors: ApiError[];
}

export interface LineageNode {
  id: string;
  type: string;
  label: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface LineageEdge {
  id: string;
  from_node_id: string;
  to_node_id: string;
  relationship: string;
  created_at: string;
}

export interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

export interface LineageGraphEnvelope {
  data: LineageGraph;
  meta: Record<string, unknown>;
  errors: ApiError[];
}
