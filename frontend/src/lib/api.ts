"use client";

import { useSession } from "next-auth/react";
import { useAuth } from "@/lib/auth-context";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function apiFetch<T>(
  path: string,
  token: string | undefined,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
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
  return {
    token,
    get: <T,>(p: string) => apiFetch<T>(p, token ?? undefined),
    post: <T,>(p: string, body: unknown) =>
      apiFetch<T>(p, token ?? undefined, { method: "POST", body: JSON.stringify(body) }),
    del: <T,>(p: string) =>
      apiFetch<T>(p, token ?? undefined, { method: "DELETE" }),
  };
}
