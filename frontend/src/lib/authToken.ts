/**
 * Holds the current Supabase access token for api.ts to attach to requests.
 *
 * A standalone module rather than living on auth.svelte.ts: api.ts needs the
 * token, and auth.svelte.ts already imports api.ts's authApi — importing
 * auth.svelte.ts back from api.ts would be a cycle.
 */

let currentToken: string | null = null;
let currentOrgId: number | null = null;

/**
 * Resolves once the initial Supabase session lookup has settled (or auth
 * isn't configured at all), i.e. once `currentToken` reflects reality rather
 * than "not checked yet". Callers that need auth on their very first request
 * (api.ts's apiFetch, the IFC/BCF viewer) await this instead of firing
 * immediately: that lookup is async, and a request fired before it resolves
 * would race it into a guaranteed "missing bearer token" 401 with no token to
 * retry with.
 */
let markAuthReady: () => void;
export const authReady: Promise<void> = new Promise((resolve) => {
  markAuthReady = resolve;
});

export function setAuthReady(): void {
  markAuthReady();
}

export function setAuthToken(token: string | null): void {
  currentToken = token;
}

export function getAuthToken(): string | null {
  return currentToken;
}

export function setActiveOrgId(orgId: number | null): void {
  currentOrgId = orgId;
}

export function getActiveOrgId(): number | null {
  return currentOrgId;
}

/** `Authorization` and tenant headers for an authenticated fetch. */
export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (currentToken) {
    headers.Authorization = `Bearer ${currentToken}`;
  }
  if (currentOrgId != null) {
    headers["X-Organization-Id"] = String(currentOrgId);
  }
  return headers;
}
