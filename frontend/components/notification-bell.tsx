"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { getAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";
const SSE_RETRY_MS = 5000;

function parseSseEvents(buffer: string): { events: Array<{ type: string; data: string }>; rest: string } {
  const events: Array<{ type: string; data: string }> = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";

  for (const block of blocks) {
    if (!block.trim() || block.startsWith(":")) {
      continue;
    }
    let eventType = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (dataLines.length > 0) {
      events.push({ type: eventType, data: dataLines.join("\n") });
    }
  }

  return { events, rest };
}

export function NotificationBell() {
  const [unread, setUnread] = useState(0);
  const retryTimerRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      return;
    }

    let cancelled = false;

    const fetchUnread = async () => {
      try {
        const response = await fetch(`${API_BASE}/notifications/unread-count`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          return;
        }
        const body = (await response.json()) as { data: { unread_count: number } };
        if (!cancelled) {
          setUnread(body.data.unread_count);
        }
      } catch {
        if (!cancelled) {
          setUnread(0);
        }
      }
    };

    const scheduleReconnect = () => {
      if (cancelled || retryTimerRef.current !== null) {
        return;
      }
      retryTimerRef.current = window.setTimeout(() => {
        retryTimerRef.current = null;
        void connectStream();
      }, SSE_RETRY_MS);
    };

    const connectStream = async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(`${API_BASE}/notifications/stream`, {
          headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          scheduleReconnect();
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (!cancelled) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          const parsed = parseSseEvents(buffer);
          buffer = parsed.rest;
          for (const event of parsed.events) {
            if (event.type === "heartbeat" || event.type === "connected") {
              try {
                const payload = JSON.parse(event.data) as { unread_count?: number };
                if (typeof payload.unread_count === "number" && !cancelled) {
                  setUnread(payload.unread_count);
                }
              } catch {
                void fetchUnread();
              }
            }
          }
        }
        if (!cancelled) {
          scheduleReconnect();
        }
      } catch {
        if (!cancelled) {
          scheduleReconnect();
        }
      }
    };

    void fetchUnread();
    void connectStream();

    return () => {
      cancelled = true;
      abortRef.current?.abort();
      if (retryTimerRef.current !== null) {
        window.clearTimeout(retryTimerRef.current);
      }
    };
  }, []);

  if (!getAccessToken()) {
    return null;
  }

  return (
    <Link
      href="/portal/notifications"
      className="relative inline-flex items-center rounded-full bg-[var(--color-background-secondary)] px-2 py-0.5 text-xs hover:opacity-90"
      aria-label={`${unread} unread notifications`}
    >
      Notifications
      {unread > 0 ? (
        <span className="ml-1 rounded-full bg-[var(--color-danger)] px-1.5 text-[10px] text-white">
          {unread}
        </span>
      ) : null}
    </Link>
  );
}
