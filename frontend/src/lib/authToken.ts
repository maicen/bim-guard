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

/**
 * Add the current access token to a URL the browser will navigate to itself.
 *
 * A plain `<a href>` or `window.location.href` download and an `EventSource`
 * cannot carry an `Authorization` header, so the token rides as `?token=`
 * instead. `app/auth.py`'s `get_current_user_flexible` accepts either, and
 * prefers the header when both are present, so adding this to a URL that is
 * also fetched with `authHeaders()` changes nothing.
 *
 * Use this for every authenticated URL handed to the browser rather than to
 * `fetch`. Without it the navigation lands on
 * `{"detail":"Missing bearer token"}` instead of a file, which is what the
 * report exports did from 47cf29b until 2026-09-09.
 *
 * Returns the URL unchanged when there is no token: the caller is not signed
 * in, and an empty `token=` would only turn a 401 into a different 401.
 */
export function withAuthToken(url: string): string {
  if (!currentToken) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}token=${encodeURIComponent(currentToken)}`;
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
