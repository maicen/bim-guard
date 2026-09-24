import type { PipelineEvent, WorkflowStatus } from "./types";
import { withAuthToken, refreshAuthToken } from "./authToken";

export interface SSESubscriptionOptions {
  onStatus?: (status: WorkflowStatus) => void;
  onEvent?: (event: PipelineEvent) => void;
  onError?: (err: Event) => void;
  /** Fires when the stream connects, and again on each automatic reconnect. */
  onOpen?: () => void;
}

//: Bounds the token-refresh reconnect loop below -- a genuinely signed-out
//: user (refreshAuthToken keeps returning null) must not retry forever.
const MAX_TOKEN_REFRESH_RECONNECTS = 3;
//: EventSource retries a plain network blip on its own; only a stream that
//: never opens across this many consecutive errors is treated as stuck on a
//: stale token rather than a transient drop.
const CONSECUTIVE_ERRORS_BEFORE_REFRESH = 2;

export function subscribeToPipelineEvents(
  projectId: number,
  options: SSESubscriptionOptions = {},
): () => void {
  const API_BASE = import.meta.env.VITE_API_URL || "/api";
  let es: EventSource;
  let closed = false;
  let consecutiveErrors = 0;
  let refreshReconnectsUsed = 0;

  function connect() {
    // EventSource can't set an Authorization header, so the token rides
    // along as a query param instead -- app/api/events.py's dependency
    // accepts either. This is a snapshot taken at connect time: if the
    // token expires over a very long-lived stream, a 401 either fails the
    // connection outright (readyState -> CLOSED, no browser-level retry) or
    // the browser keeps retrying the same now-stale URL -- both dead ends
    // handled below by refreshing the token and reconnecting manually with
    // a fresh URL, instead of looping 401s forever.
    const url = withAuthToken(`${API_BASE}/events/${projectId}`);
    es = new EventSource(url);

    es.addEventListener("status", (e: MessageEvent) => {
      try {
        const data: WorkflowStatus = JSON.parse(e.data);
        options.onStatus?.(data);
      } catch (err) {
        console.error("Error parsing SSE status:", err);
      }
    });

    es.addEventListener("pipeline_event", (e: MessageEvent) => {
      try {
        const data: PipelineEvent = JSON.parse(e.data);
        options.onEvent?.(data);
      } catch (err) {
        console.error("Error parsing SSE pipeline_event:", err);
      }
    });

    // EventSource reconnects on its own; surfacing `open` lets the caller
    // mark the stream live as soon as it connects, rather than waiting for
    // the first message, and lets it clear a "reconnecting" state after a
    // drop. A real open also means the token was fine, so the refresh
    // budget resets for the next drop.
    es.onopen = () => {
      consecutiveErrors = 0;
      refreshReconnectsUsed = 0;
      options.onOpen?.();
    };

    es.onerror = (err) => {
      if (closed) return;
      console.warn(`SSE connection error on project ${projectId}:`, err);
      consecutiveErrors += 1;

      const stuckOnStaleToken =
        es.readyState === EventSource.CLOSED || consecutiveErrors >= CONSECUTIVE_ERRORS_BEFORE_REFRESH;

      if (stuckOnStaleToken && refreshReconnectsUsed < MAX_TOKEN_REFRESH_RECONNECTS) {
        refreshReconnectsUsed += 1;
        consecutiveErrors = 0;
        es.close();
        refreshAuthToken()
          .then(() => {
            if (!closed) connect();
          })
          .catch(() => {
            // refreshAuthToken already swallows and logs its own failures
            // (see authToken.ts) -- nothing further to recover here beyond
            // reporting the original error below.
          });
      }

      options.onError?.(err);
    };
  }

  connect();

  // Return unsubscribe function
  return () => {
    closed = true;
    es.close();
  };
}
