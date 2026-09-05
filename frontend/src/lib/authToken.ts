/**
 * Holds the current Supabase access token for api.ts to attach to requests.
 *
 * A standalone module rather than living on auth.svelte.ts: api.ts needs the
 * token, and auth.svelte.ts already imports api.ts's authApi — importing
 * auth.svelte.ts back from api.ts would be a cycle.
 */

let currentToken: string | null = null;

export function setAuthToken(token: string | null): void {
  currentToken = token;
}

export function getAuthToken(): string | null {
  return currentToken;
}

/** `Authorization` header for an authenticated fetch, or {} when signed out. */
export function authHeaders(): Record<string, string> {
  return currentToken ? { Authorization: `Bearer ${currentToken}` } : {};
}
