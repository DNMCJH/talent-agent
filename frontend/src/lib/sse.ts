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
 * Subscribe to a backend SSE endpoint. Returns a cleanup function that closes
 * the connection — callers MUST invoke it (e.g. on unmount or session end) or
 * the EventSource leaks.
 *
 * Auth: token is appended as `?token=`. Other params are appended afterwards.
 * Caller is responsible for URL-encoding values in `params`.
 */
export function openSSE(
  path: string,
  token: string,
  params: Record<string, string>,
  handlers: StreamHandlers,
): () => void {
  const search = new URLSearchParams({ token, ...params });
  const url = `${API_BASE}${path}?${search.toString()}`;
  const es = new EventSource(url);
  let closed = false;

  const close = () => {
    if (closed) return;
    closed = true;
    es.close();
    handlers.onClose?.();
  };

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
    // EventSource auto-reconnects, but for our LLM streams we treat any error
    // before [DONE] as a hard failure (state on the server is one-shot).
    handlers.onNetworkError?.(new Error("connection lost"));
    close();
  };

  return close;
}
