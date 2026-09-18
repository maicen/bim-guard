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
  /**
   * Whether a `running` frame has arrived since tracking began. Until one has,
   * a `complete`/`failed` frame describes the *previous* run — the backend
   * keeps a finished run readable for its TTL, and the SSE stream's first
   * frame is that snapshot — so it must not end tracking of the new one.
   */
  sawRunning: boolean;
  unsubscribe: () => void;
}

/** What a status frame means for a tracked run. */
export type PipelineOutcome = "complete" | "failed" | null;

/**
 * Decide whether `status` ends a tracked run.
 *
 * Returns `"complete"` or `"failed"` only for a terminal frame that follows a
 * `running` one (`sawRunning`); anything else — including a terminal frame
 * left over from the previous run — returns `null` and tracking continues.
 * A run that finishes before the stream ever reports it running is left to
 * the view that started it, which untracks when its request settles.
 */
export function pipelineOutcome(status: WorkflowStatus, sawRunning: boolean): PipelineOutcome {
  if (!sawRunning) return null;
  if (status.status === "complete" || status.status === "failed") return status.status;
  return null;
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
    this.tracked.push({ projectId, projectName, status: null, sawRunning: false, unsubscribe });
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
    if (status.status === "running") entry.sawRunning = true;

    const outcome = pipelineOutcome(status, entry.sawRunning);
    if (outcome === "complete") {
      toasts.success(`Analysis pipeline finished for "${entry.projectName}".`, "Pipeline complete");
      this.untrack(projectId);
    } else if (outcome === "failed") {
      toasts.error(`Analysis pipeline failed for "${entry.projectName}".`, "Pipeline failed");
      this.untrack(projectId);
    }
  }
}

export const pipelineTracker = new PipelineTrackerStore();

/**
 * Engine statuses that mean the engine actually started. A `pending` engine
 * carries no `progress_percent` at all, so counting it dragged the average
 * down by a constant: a finished corrosion run (GC-001 + CC-001 at 100)
 * averaged against three idle engines reported 40% and stopped there.
 */
const STARTED = new Set(["running", "complete", "failed"]);

/**
 * Average progress across the engines of the run currently reporting, 0-100.
 *
 * Scoped two ways, because a project can have more than one analysis tracked
 * at once — the backend keys trackers by project *and* run, so a seismic run
 * and a corrosion run on one project are both in the payload:
 *
 *   - to engines that have started, so idle engines do not cap the bar; and
 *   - to `status.run_key`, the run that reported most recently, so a seismic
 *     run does not read as 83% because a corrosion run finished ten minutes
 *     ago and is still inside the tracker's TTL.
 *
 * An engine with no `run_key` is treated as part of the active run, so a
 * payload from before the runs were merged still averages the way it used to.
 */
export function avgPipelineProgress(status: WorkflowStatus | null | undefined): number {
  if (!status) return 0;
  const activeRun = status.run_key ?? "default";
  const engines = Object.values(status.engines || {}).filter(
    (e) => STARTED.has(e.status) && (e.run_key ?? activeRun) === activeRun,
  );
  if (!engines.length) return 0;
  return Math.round(engines.reduce((acc, e) => acc + (e.progress_percent || 0), 0) / engines.length);
}
