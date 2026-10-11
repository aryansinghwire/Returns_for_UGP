import type { Role, Tenant } from "./types";

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  role_label: string;
  /** null only for the platform admin, who works across every company. */
  tenant_slug: string | null;
  tenant_name: string | null;
}

export interface SignupInput {
  tenant_slug: string;
  email: string;
  password: string;
  role: Role;
}

export interface DemoCredentials {
  email: string;
  password: string;
  notice: string;
}

export class AuthError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * Login requests don't use api/client.ts, on purpose. Here, "not logged in" or
 * "wrong password" is a normal answer, not an expired login - so it mustn't
 * trigger the "you've been logged out" handling and send the user to the login
 * page they're already on.
 */
async function authRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/auth${path}`, {
    credentials: "include",
    ...init,
    headers: init.body !== undefined ? { "Content-Type": "application/json" } : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (data?.detail) {
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // The reply wasn't JSON - keep the plain error message.
    }
    throw new AuthError(res.status, detail);
  }

  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>);
}

export const authApi = {
  me: (signal?: AbortSignal) => authRequest<AuthUser>("/me", { signal }),
  login: (email: string, password: string) =>
    authRequest<AuthUser>("/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  signup: (input: SignupInput) =>
    authRequest<AuthUser>("/signup", { method: "POST", body: JSON.stringify(input) }),
  logout: () => authRequest<void>("/logout", { method: "POST" }),
  /** Works without logging in: the signup form needs the list of companies first. */
  tenants: () => authRequest<Tenant[]>("/tenants"),
  /** Works without logging in: the login page shows these. They come from the
   *  server, so they always match the real demo account. */
  demoCredentials: () => authRequest<DemoCredentials>("/demo-credentials"),
};
