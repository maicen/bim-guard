/**
 * Tracks in-flight analysis pipelines independent of whichever view is
 * currently on screen. Without this, navigating away from AnalyzeView /
 * ArchAnalyzeView / WorkflowView mid-run drops all visibility into whether
 * the run finished or failed — the SSE subscription lived only inside the
 * view that started it. `pipelineTracker` keeps one subscription alive per
 * tracked project for the lifetime of the run and reports completion via
 * a toast regardless of what the user is looking at.
 */

import { subscribeToPipelineEvents } from "../sse";
import type { WorkflowStatus } from "../types";
import { toasts } from "../toast.svelte";

export interface TrackedPipeline {
  projectId: number;
  projectName: string;
  status: WorkflowStatus | null;
  unsubscribe: () => void;
}

class PipelineTrackerStore {
  tracked = $state<TrackedPipeline[]>([]);

  isTracking(projectId: number): boolean {
    return this.tracked.some((t) => t.projectId === projectId);
  }

  /** Start following a project's pipeline. No-op if already tracked. */
  track(projectId: number, projectName: string) {
    if (this.isTracking(projectId)) return;
    const unsubscribe = subscribeToPipelineEvents(projectId, {
      onStatus: (status) => this.#handleStatus(projectId, status),
    });
    this.tracked.push({ projectId, projectName, status: null, unsubscribe });
  }

  /** Stop following a project's pipeline without waiting for it to finish. */
  untrack(projectId: number) {
    const entry = this.tracked.find((t) => t.projectId === projectId);
    if (!entry) return;
    entry.unsubscribe();
    this.tracked = this.tracked.filter((t) => t.projectId !== projectId);
  }

  #handleStatus(projectId: number, status: WorkflowStatus) {
    const entry = this.tracked.find((t) => t.projectId === projectId);
    if (!entry) return;
    entry.status = status;

    if (status.status === "complete") {
      toasts.success(`Analysis pipeline finished for "${entry.projectName}".`, "Pipeline complete");
      this.untrack(projectId);
    } else if (status.status === "failed") {
      toasts.error(`Analysis pipeline failed for "${entry.projectName}".`, "Pipeline failed");
      this.untrack(projectId);
    }
  }
}

export const pipelineTracker = new PipelineTrackerStore();

/** Average progress across a run's active engines, 0-100. */
export function avgPipelineProgress(status: WorkflowStatus | null | undefined): number {
  if (!status) return 0;
  const engines = Object.values(status.engines || {}).filter((e) => e.status !== "not_implemented");
  if (!engines.length) return 0;
  return Math.round(engines.reduce((acc, e) => acc + (e.progress_percent || 0), 0) / engines.length);
}
