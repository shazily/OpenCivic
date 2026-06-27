/**
 * OpenCivic typed API client.
 * All requests include Authorization header from Keycloak access token.
 * Access tokens stored in memory (React state) — never localStorage.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost/api/v1";

interface ApiResponse<T> {
  data: T | null;
  meta: Record<string, unknown>;
  errors: Array<{ code: string; message: string; field?: string }>;
}

class ApiClient {
  private accessToken: string | null = null;

  setToken(token: string) { this.accessToken = token; }
  clearToken() { this.accessToken = null; }

  private async request<T>(
    method: string, path: string, body?: unknown
  ): Promise<ApiResponse<T>> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.accessToken) headers["Authorization"] = `Bearer ${this.accessToken}`;

    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!res.ok && res.status === 401) {
      this.clearToken();
      window.location.href = "/login";
    }

    return res.json();
  }

  get<T>(path: string) { return this.request<T>("GET", path); }
  post<T>(path: string, body?: unknown) { return this.request<T>("POST", path, body); }
  put<T>(path: string, body?: unknown) { return this.request<T>("PUT", path, body); }
  patch<T>(path: string, body?: unknown) { return this.request<T>("PATCH", path, body); }
  delete<T>(path: string) { return this.request<T>("DELETE", path); }

  // Datasets
  listDatasets(params?: Record<string, string>) {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return this.get<Dataset[]>(`/datasets${qs}`);
  }
  getDataset(id: string) { return this.get<Dataset>(`/datasets/${id}`); }
  getDatasetData(id: string, params?: Record<string, string>) {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return this.get<unknown[]>(`/datasets/${id}/data${qs}`);
  }
  searchDatasets(q: string, params?: Record<string, string>) {
    return this.get<Dataset[]>(`/search?q=${encodeURIComponent(q)}&${new URLSearchParams(params).toString()}`);
  }
}

export interface Dataset {
  id: string;
  title: string;
  slug: string;
  description: string | null;
  status: string;
  access_level: string;
  quality_score: number | null;
  staleness_state: string;
  tags: string[];
  row_count: number | null;
  published_at: string | null;
  last_refreshed_at: string | null;
}

export const apiClient = new ApiClient();
export default apiClient;
