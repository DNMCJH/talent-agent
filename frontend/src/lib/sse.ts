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

/**
 * Subscribe to a backend SSE stream.
 *
 * Two-step flow: the request body is POSTed to `preparePath` (normal Bearer
 * auth), which stages it server-side and returns an opaque `stream_id` plus a
 * short-lived stream token. The EventSource then connects to `streamPath` with
 * only those two values in the URL — no JD text or interview answers ever land
 * in access logs or browser history.
 *
 * Returns a cleanup function that closes the connection — callers MUST invoke
 * it (e.g. on unmount or session end) or the EventSource leaks.
 */
export function openSSE(
  preparePath: string,
  streamPath: string,
  token: string,
  payload: unknown,
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

  fetch(`${API_BASE}${preparePath}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  })
    .then(async (res) => {
      if (!res.ok) {
        let detail = `prepare failed: ${res.status}`;
        try {
          const body = await res.json();
          if (typeof body?.detail === "string") detail = body.detail;
        } catch {
          // ignore
        }
        throw new Error(detail);
      }
      return res.json() as Promise<{ stream_id: string; stream_token: string }>;
    })
    .then(({ stream_id, stream_token }) => {
      if (closed) return;
      const search = new URLSearchParams({ token: stream_token, stream_id });
      es = new EventSource(`${API_BASE}${streamPath}?${search.toString()}`);

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
