import type { PipelineEvent, WorkflowStatus } from './types';

export interface SSESubscriptionOptions {
  onStatus?: (status: WorkflowStatus) => void;
  onEvent?: (event: PipelineEvent) => void;
  onError?: (err: Event) => void;
}

export function subscribeToPipelineEvents(
  projectId: number,
  options: SSESubscriptionOptions = {}
): () => void {
  const API_BASE = import.meta.env.VITE_API_URL || '/api';
  const url = `${API_BASE}/events/${projectId}`;
  const es = new EventSource(url);

  es.addEventListener('status', (e: MessageEvent) => {
    try {
      const data: WorkflowStatus = JSON.parse(e.data);
      options.onStatus?.(data);
    } catch (err) {
      console.error('Error parsing SSE status:', err);
    }
  });

  es.addEventListener('pipeline_event', (e: MessageEvent) => {
    try {
      const data: PipelineEvent = JSON.parse(e.data);
      options.onEvent?.(data);
    } catch (err) {
      console.error('Error parsing SSE pipeline_event:', err);
    }
  });

  es.onerror = (err) => {
    console.warn(`SSE connection error on project ${projectId}:`, err);
    options.onError?.(err);
  };

  // Return unsubscribe function
  return () => {
    es.close();
  };
}

