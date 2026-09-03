import type { PipelineEvent, WorkflowStatus } from "./types";

export interface SSESubscriptionOptions {
  onStatus?: (status: WorkflowStatus) => void;
  onEvent?: (event: PipelineEvent) => void;
  onError?: (err: Event) => void;
  /** Fires when the stream connects, and again on each automatic reconnect. */
  onOpen?: () => void;
}

export function subscribeToPipelineEvents(
  projectId: number,
  options: SSESubscriptionOptions = {},
): () => void {
  const API_BASE = import.meta.env.VITE_API_URL || "/api";
  const url = `${API_BASE}/events/${projectId}`;
  const es = new EventSource(url);

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

  // EventSource reconnects on its own; surfacing `open` lets the caller mark
  // the stream live as soon as it connects, rather than waiting for the first
  // message, and lets it clear a "reconnecting" state after a drop.
  es.onopen = () => {
    options.onOpen?.();
  };

  es.onerror = (err) => {
    console.warn(`SSE connection error on project ${projectId}:`, err);
    options.onError?.(err);
  };

  // Return unsubscribe function
  return () => {
    es.close();
  };
}
