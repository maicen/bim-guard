import {
  authHeaders,
  authReady,
  getAuthToken,
  refreshAuthToken,
} from "../authToken";

export const API_BASE = import.meta.env.VITE_API_URL || "/api";

/** An `Error` from a non-OK response, carrying the HTTP status that caused it. */
export interface ApiError extends Error {
  status?: number;
  /** The request URL that produced this failure, for copyable diagnostic logs. */
  url?: string;
  /** When this failure was observed client-side, for copyable diagnostic logs. */
  timestamp?: string;
  /**
   * True when `fetch` itself failed to get a response at all (DNS failure,
   * connection refused, request aborted) rather than the server responding
   * with a non-OK status. `status` is unset in this case -- there was no
   * response to read one from.
   */
  isNetworkError?: boolean;
}

/**
 * `fetch` rejects with a bare `TypeError` (message varies by browser: "Failed
 * to fetch", "NetworkError when attempting to fetch resource.", "Load
 * failed") when no HTTP response arrives at all -- offline, DNS failure, a
 * dropped connection, CORS rejection. That shape is indistinguishable from a
 * caller's own bug by `err.message` alone, and carries none of `ApiError`'s
 * fields (`status`, `url`), so a catch site expecting one (`err?.status ===
 * 403`, an errorLog entry) silently gets nothing useful. This normalizes it
 * into the same `ApiError` shape `handleResponse` produces for a non-OK HTTP
 * response, so every catch site downstream of `apiFetch` sees one consistent
 * error type regardless of which layer failed.
 */
export function toNetworkError(err: unknown, url: string): ApiError {
  if (err instanceof DOMException && err.name === "AbortError") {
    const failure = new Error("Request was cancelled.") as ApiError;
    failure.url = url;
    failure.timestamp = new Date().toISOString();
    return failure;
  }
  const offline = typeof navigator !== "undefined" && navigator.onLine === false;
  const failure = new Error(
    offline
      ? "You appear to be offline. Check your connection and try again."
      : "Couldn't reach the BIM-Guard server. Check your connection and try again.",
  ) as ApiError;
  failure.url = url;
  failure.timestamp = new Date().toISOString();
  failure.isNetworkError = true;
  return failure;
}

export async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    // `res.statusText` is always "" over HTTP/2 (no reason phrase in the
    // protocol, e.g. behind the Cloudflare Tunnel), so it's not a reliable
    // fallback on its own -- pair it with the numeric status so a non-JSON
    // error body (a proxy timeout page, an unhandled exception) still shows
    // something other than a bare "unknown error".
    let errorDetail = res.statusText ? `${res.statusText} (${res.status})` : `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      const detail = errJson.detail ?? errJson.error;
      if (Array.isArray(detail)) {
        // FastAPI's default 422 validation shape: a list of {loc, msg, ...}.
        errorDetail =
          detail
            .map((d: any) => {
              const field = Array.isArray(d?.loc) ? d.loc.slice(1).join(".") : "";
              return field ? `${field}: ${d.msg}` : d?.msg || JSON.stringify(d);
            })
            .join("; ") || errorDetail;
      } else if (detail) {
        errorDetail = typeof detail === "string" ? detail : JSON.stringify(detail);
      }
    } catch {
      // not json
    }
    if (res.status === 524 && errorDetail.startsWith("HTTP 524")) {
      errorDetail =
        "Network proxy timeout (HTTP 524). The server took longer than 100 seconds to respond — this usually occurs when converting large documents (such as building codes) to DocLang. Turn off “Convert to DocLang now” to upload immediately, or use “Limit to a page range”.";
    } else if (res.status === 504 && errorDetail.startsWith("HTTP 504")) {
      errorDetail = "Gateway timeout (HTTP 504). The server took too long to process the request.";
    }
    // The status rides along so a caller can tell a rejected request apart
    // from a failed one — a 422 means the query this client built was wrong,
    // which is a bug to report rather than a condition to show the user.
    const failure = new Error(errorDetail) as ApiError;
    failure.status = res.status;
    failure.url = res.url;
    failure.timestamp = new Date().toISOString();
    throw failure;
  }
  if (res.status === 204) {
    return {} as T;
  }
  return res.json();
}

/**
 * Drop-in replacement for `fetch` against this app's own API: every call
 * below goes through this so the caller's Supabase token (if any) rides
 * along automatically. Endpoints that don't require auth simply ignore the
 * header; projects/rules (the ones that do) need it on every request.
 *
 * Awaiting `authReady` first closes the startup race: the initial Supabase
 * session lookup is async, and a request fired before it resolves would go
 * out with no Authorization header at all -- a guaranteed 401 with nothing
 * to retry, since no token exists yet at that instant. `authReady` resolves
 * (once, synchronously with `setAuthToken`) as soon as that lookup settles,
 * so by the time this awaits past it the token -- if any -- is already set;
 * after startup the promise is long since resolved and this await is a
 * same-microtask no-op.
 */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  await authReady;
  const headers = { ...authHeaders(), ...(init.headers as Record<string, string> | undefined) };
  let res: Response;
  try {
    res = await fetch(input, { ...init, headers });
  } catch (err) {
    throw toNetworkError(err, input);
  }

  // If 401 Unauthorized and a token was attached, the token may have expired.
  // Attempt to refresh the session token once and retry with the new token.
  if (res.status === 401 && getAuthToken()) {
    const newToken = await refreshAuthToken();
    if (newToken) {
      const retryHeaders = {
        ...authHeaders(),
        ...(init.headers as Record<string, string> | undefined),
        Authorization: `Bearer ${newToken}`,
      };
      try {
        res = await fetch(input, { ...init, headers: retryHeaders });
      } catch (err) {
        throw toNetworkError(err, input);
      }
    }
  }

  return res;
}

/** True when a rejection is an aborted fetch rather than a real failure. */
export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}
