# Blocking Issues for FMP Work Merge (Commit 0bf2c44)

## Issue 1: PipelineOrchestratorService Arguments

**Problem:** Calls `orchestrate_workflow()` with zero arguments, at two sites in
`app/routes/analyze.py` (`_run_analysis_request` and the ARCH handler).
**Expected:** project_id, doc_ids, analysis_theme, rule_folder, count flags —
all of which are still read from the form immediately above the call, then
discarded.
**Impact:** The call cannot be analysing the selected project. Analysis broken on main.
**Fix:** Restore arguments to the call, or redesign the orchestrator to take them.

## Issue 2: emit_event bolt-on in compliance_orchestrator

**Problem:** `orchestrate_workflow` in
`app/modules/module4_comparator/compliance_orchestrator.py` ends with an
`emit_event(...)` call that hardcodes `project_id=0` and wraps itself in a bare
`except Exception: pass`.
**Impact:** The COMPLIANCE_COMPLETED event cannot be attributed to a project, and
any failure in it is silent. Low severity — nothing reads it back — but it is the
only `emit_event` call site that does not carry a real project id.
**Fix:** Thread the real project_id through, or drop the call until a consumer exists.

**Not an issue — recorded to prevent re-litigating it:** `emit_event` and the
`emit()` / `increment()` / `complete()` / `fail()` API are *not* competing designs.
Commit ab82bf2 layered `emit_event` calls *inside* those four functions, where they
use `tracker.project_id` correctly. The MM-001/XM-001 instrumentation on this branch
calls `emit()` / `increment()`, so on a merged tree it feeds the SSE event stream for
free. No API needs retiring; the tracker conflict is a plain text merge.

## Issue 3: Test Import Path

**File:** `tests/test_analysis_enhancement_split.py`
**Problem:** Imports from `app.modules.pipeline_services`; commit 0bf2c44 moved the
module to `app.services.pipeline_services` and updated `analyze.py` but not this test.
**Impact:** Collection error — the 8 tests never run on main. They pass on this branch.
**Fix:** Update the import path.

## FMP Work Status

- Branch: `ready/fmp-async-tracking`
- Commits: `b2315e5` (async analysis dispatch + redirect in `app/routes/analyze.py`),
  `c7819c1` (MM-001/XM-001 instrumentation, MC-001 status, workflow poller)
- Tests: 85 passed, 1 xfailed across test_pipeline_tracker (27),
  test_integration (16), test_phase_6c_corrosion_ui (42)
- Merge conflicts expected in three files, all textual:
  `app/routes/analyze.py`, `app/services/pipeline_tracker.py`,
  `app/modules/module4_comparator/compliance_orchestrator.py`.
  `static/js/workflow-poller.js` and `app/services/analysis_runner.py` are
  untouched upstream and merge free.
- Can merge once issues 1 and 3 are resolved; issue 2 is not a merge blocker.
