"""Overall run status for a project's workflow payload.

WHY THIS EXISTS

    Clients follow an analysis through ``WorkflowStatus.status`` -- the
    frontend's global pipeline tracker toasts and stops following a run when it
    reads ``"complete"`` or ``"failed"`` there. Nothing ever sent either value:
    ``GET /api/status/{id}`` only ever answered ``"running"`` or ``"idle"``, and
    the SSE ``status`` frames carried no top-level ``status`` at all. A finished
    run was therefore followed until the view that started it cleaned up, and
    the completion toast could not fire.

    The per-engine cells already know everything needed -- each touched engine
    reports ``running`` / ``complete`` / ``failed`` and the ``run_key`` it ran
    under -- so the overall status is derived from :func:`merged_snapshot`
    rather than by teaching :mod:`app.services.pipeline_tracker` a new concept.

HOW THE STATUS IS DERIVED

    * ``running`` -- any touched engine, under any run key, is still running.
      Checked across every run so a graph pass that starts after the corrosion
      engines finish keeps the project reading as busy.
    * Otherwise the verdict comes from the engines of the *active* run (the
      payload's ``run_key``, the run that reported last), so a corrosion run
      that finished ten minutes ago -- still inside the tracker's TTL -- cannot
      colour the verdict on a seismic run that just ended:
      ``failed`` if any of them failed, ``complete`` if every one completed.
    * ``idle`` -- nothing has been tracked for this project.

    Untouched engines carry their declared status (``pending``,
    ``not_implemented``) and no ``run_key``; they are not part of any run and
    never hold a verdict back. Otherwise the uninstrumented MM-001 / XM-001
    cells would leave every corrosion run ``running`` forever.
"""

from __future__ import annotations

from typing import Any

from app.services.pipeline_tracker import merged_snapshot

#: Overall states a workflow payload can report.
IDLE = "idle"
RUNNING = "running"
COMPLETE = "complete"
FAILED = "failed"


def overall_status(snapshot: dict[str, Any]) -> str:
    """Return the overall run status for a :func:`merged_snapshot` payload.

    Args:
        snapshot: A payload shaped like :func:`merged_snapshot`'s -- a
            ``run_key`` and an ``engines`` mapping of per-engine cells.

    Returns:
        One of ``"idle"``, ``"running"``, ``"complete"`` or ``"failed"``.
    """
    engines = [e for e in (snapshot.get("engines") or {}).values() if isinstance(e, dict)]
    # A touched engine always carries its run_key; untracked cells never do.
    touched = [e for e in engines if e.get("run_key")]
    if any(e.get("status") == RUNNING for e in touched):
        return RUNNING

    active = snapshot.get("run_key")
    in_run = [e for e in touched if e.get("run_key") == active]
    if not in_run:
        return IDLE
    if any(e.get("status") == FAILED for e in in_run):
        return FAILED
    if all(e.get("status") == COMPLETE for e in in_run):
        return COMPLETE
    return RUNNING


def status_snapshot(project_id: int) -> dict[str, Any]:
    """Return :func:`merged_snapshot` for ``project_id`` plus a top-level ``status``.

    The payload each SSE ``status`` frame sends, and (reshaped into its
    contract) what ``GET /api/analyze/status/{id}`` returns.
    ``GET /api/workflow/{id}`` keeps its pinned four-key shape and does not
    carry it.
    """
    snap = merged_snapshot(project_id)
    snap["status"] = overall_status(snap)
    return snap
