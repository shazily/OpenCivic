/**
 * Resumable TUS upload via tus-js-client.
 */

import * as tus from "tus-js-client";

import { getAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";

export interface TusSession {
  endpoint: string;
  storage_key: string;
  upload_metadata: Record<string, string>;
}

export async function createTusSession(datasetId: string, filename: string): Promise<TusSession> {
  const token = getAccessToken();
  const response = await fetch(`${API_BASE}/datasets/${datasetId}/upload/tus-session`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ filename }),
  });
  const body = (await response.json()) as {
    data: TusSession;
    errors?: { message: string }[];
  };
  if (!response.ok) {
    throw new Error(body.errors?.[0]?.message ?? `TUS session failed (${response.status})`);
  }
  return body.data;
}

export function uploadFileWithTus(
  file: File,
  session: TusSession,
  onProgress?: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const upload = new tus.Upload(file, {
      endpoint: session.endpoint,
      metadata: session.upload_metadata,
      retryDelays: [0, 1000, 3000, 5000],
      onError: (error) => reject(error),
      onProgress: (bytesSent, bytesTotal) => {
        if (bytesTotal > 0 && onProgress) {
          onProgress(Math.round((bytesSent / bytesTotal) * 100));
        }
      },
      onSuccess: () => resolve(),
    });
    upload.start();
  });
}
