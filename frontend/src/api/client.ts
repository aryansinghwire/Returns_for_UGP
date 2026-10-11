// Sends requests to the server. In development they go through Vite's proxy
// (see vite.config.ts) to the server at http://127.0.0.1:8000.
//
// The login is a cookie the browser sends by itself - this code can't read it
// and doesn't send any login details of its own. The `tenant` setting isn't
// about who you are: it's which company a platform admin is looking at.
//
// Logging in and out deliberately doesn't use this file - see api/auth.ts.

import { emitUnauthorized } from "./authEvents";

const BASE_URL = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface RequestContext {
  tenant: string | null; // the company being *viewed*, or null for all companies
}

function buildQuery(params: Record<string, unknown> | undefined, tenant: string | null): string {
  const search = new URLSearchParams();
  if (tenant) search.set("tenant", tenant);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        search.set(key, String(value));
      }
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function request<T>(
  method: "GET" | "POST" | "PATCH",
  path: string,
  ctx: RequestContext,
  options: { params?: Record<string, unknown>; body?: unknown; skipTenant?: boolean } = {},
): Promise<T> {
  const query = buildQuery(options.params, options.skipTenant ? null : ctx.tenant);
  const res = await fetch(`${BASE_URL}${path}${query}`, {
    method,
    // Send the login cookie with the request. Saying so explicitly keeps this
    // working even if the server is ever on a different address.
    credentials: "include",
    headers: options.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!res.ok) {
    if (res.status === 401) {
      // Every request goes through here, so this is where an expired login is
      // noticed. It tells AuthProvider through authEvents (importing AuthProvider
      // directly would create a loop between the two files).
      emitUnauthorized();
    }
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data?.detail ? JSON.stringify(data.detail) : detail;
    } catch {
      // The reply wasn't JSON - keep the plain error message.
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, ctx: RequestContext, params?: Record<string, unknown>, skipTenant?: boolean) =>
    request<T>("GET", path, ctx, { params, skipTenant }),
  post: <T>(path: string, ctx: RequestContext, body?: unknown, params?: Record<string, unknown>) =>
    request<T>("POST", path, ctx, { body, params }),
  patch: <T>(path: string, ctx: RequestContext, body?: unknown, params?: Record<string, unknown>) =>
    request<T>("PATCH", path, ctx, { body, params }),
};
