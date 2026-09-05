/**
 * Holds the current Supabase access token for api.ts to attach to requests.
 *
 * A standalone module rather than living on auth.svelte.ts: api.ts needs the
 * token, and auth.svelte.ts already imports api.ts's authApi — importing
 * auth.svelte.ts back from api.ts would be a cycle.
 */

let currentToken: string | null = null;
let currentOrgId: number | null = null;

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
