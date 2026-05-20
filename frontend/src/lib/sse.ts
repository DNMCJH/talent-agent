"use client";

import { API_BASE } from "./api";

export type SSEEvent =
  | { type: "delta"; text: string }
  | { type: "done"; [key: string]: unknown }
  | { type: "error"; status?: number; message: string };

type StreamHandlers = {
  onEvent: (event: SSEEvent) => void;
  onClose?: () => void;
  /** Called when the network drops before [DONE] arrives. */
  onNetworkError?: (err: Error) => void;
};

async function fetchStreamToken(sessionToken: string): Promise<string> {
  const res = await fetch(`${API_BASE}/auth/stream-token`, {
    method: "POST",
    headers: { Authorization: `Bearer ${sessionToken}` },
  });
  if (!res.ok) throw new Error(`stream-token failed: ${res.status}`);
  const data = await res.json();
  return data.token;
}

/**
 * Subscribe to a backend SSE endpoint. Returns a cleanup function that closes
 * the connection — callers MUST invoke it (e.g. on unmount or session end) or
 * the EventSource leaks.
 *
 * Auth: fetches a short-lived stream token, then appends it as `?token=`.
 * Caller is responsible for URL-encoding values in `params`.
 */
export function openSSE(
  path: string,
  token: string,
  params: Record<string, string>,
  handlers: StreamHandlers,
): () => void {
  let closed = false;
  let es: EventSource | null = null;

  const close = () => {
    if (closed) return;
    closed = true;
    es?.close();
    handlers.onClose?.();
  };

  fetchStreamToken(token)
    .then((streamToken) => {
      if (closed) return;
      const search = new URLSearchParams({ token: streamToken, ...params });
      const url = `${API_BASE}${path}?${search.toString()}`;
      es = new EventSource(url);

      es.onmessage = (e) => {
        if (e.data === "[DONE]") {
          close();
          return;
        }
        try {
          const event = JSON.parse(e.data) as SSEEvent;
          handlers.onEvent(event);
          if (event.type === "error") close();
        } catch {
          // Malformed event — skip.
        }
      };

      es.onerror = () => {
        if (closed) return;
        handlers.onNetworkError?.(new Error("connection lost"));
        close();
      };
    })
    .catch((err) => {
      if (closed) return;
      handlers.onNetworkError?.(err);
      close();
    });

  return close;
}
