"use client";

import { useMemo } from "react";
import { useSession } from "next-auth/react";
import { useAuth } from "@/lib/auth-context";

export const API_BASE = "/api/backend";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function apiFetch<T>(
  path: string,
  token: string | undefined,
  init: RequestInit = {},
  timeoutMs?: number,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let signal = init.signal;
  let controller: AbortController | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  if (timeoutMs && !signal) {
    controller = new AbortController();
    signal = controller.signal;
    timer = setTimeout(() => controller!.abort(), timeoutMs);
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers, signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError(408, "请求超时，AI 响应较慢，请稍后重试");
    }
    throw new ApiError(0, "网络错误，请检查连接后重试");
  } finally {
    // Clear the timeout so a completed request does not leave a pending abort.
    if (timer) clearTimeout(timer);
  }

  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      const raw = body.detail ?? body;
      detail = typeof raw === "string" ? raw : JSON.stringify(raw);
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function useApi() {
  const { data: session } = useSession();
  const { token: emailToken } = useAuth();
  const token = emailToken || session?.backendJwt;
  // Memoize on `token` so the returned object is stable across renders —
  // otherwise consumers that put `api` in a useEffect dep array re-fire on
  // every parent render (e.g. the email-verify banner re-GETting /auth/me).
  return useMemo(() => ({
    token,
    get: <T,>(p: string) => apiFetch<T>(p, token ?? undefined),
    post: <T,>(p: string, body: unknown, timeoutMs?: number) =>
      apiFetch<T>(p, token ?? undefined, { method: "POST", body: JSON.stringify(body) }, timeoutMs),
    del: <T,>(p: string) =>
      apiFetch<T>(p, token ?? undefined, { method: "DELETE" }),
    upload: async <T,>(p: string, file: File, timeoutMs?: number): Promise<T> => {
      const headers = new Headers();
      if (token) headers.set("Authorization", `Bearer ${token}`);
      const form = new FormData();
      form.append("file", file);

      let signal: AbortSignal | undefined;
      let controller: AbortController | undefined;
      if (timeoutMs) {
        controller = new AbortController();
        signal = controller.signal;
        setTimeout(() => controller!.abort(), timeoutMs);
      }

      const res = await fetch(`${API_BASE}${p}`, {
        method: "POST",
        headers,
        body: form,
        signal,
      });
      if (!res.ok) {
        let detail = `${res.status}`;
        try {
          const body = await res.json();
          const raw = body.detail ?? body;
          detail = typeof raw === "string" ? raw : JSON.stringify(raw);
        } catch {}
        throw new ApiError(res.status, detail);
      }
      return res.json() as Promise<T>;
    },
  }), [token]);
}
