# BIMGUARD E2E Test Results

Date: 2026-08-30
Commit: (see `git log -1`)
Harness: `scripts/e2e_server.py` + `scripts/e2e_suite.py`, manifest `e2e-models.json`
Machine results: `test-results.json`

## Summary

**13 passed, 1 failed, 18 skipped.**

The run is **incomplete, and the reason is not the code**: the test dataset does
not exist yet, and one analysis cannot run without a database. Both blockers are
described below. Nothing in this document is marked passed unless it was
actually executed.

| Category | Status | Why |
| --- | --- | --- |
| 1. Piping — gating & cache | **PASS** (1 model) | Ran on the one IFC available in-repo |
| 2. Seismic | **PASS** (1 model) | Ran on the same model — first live verification |
| 3. Architecture | **BLOCKED** | Rule pack lives in the database; none here |
| 4. Schema robustness (IFC2x3/IFC4) | **BLOCKED** | Twin models unavailable |
| 5. Geometry robustness (BREP/parametric) | **BLOCKED** | Models unavailable |
| 6. Performance baseline | **BLOCKED** | Sized models unavailable |

## Blocker 1 — the test dataset is empty

`https://github.com/maicen/bimguard-test-models` exists and is public, but it
has **no commits**: `git clone` reports "you appear to have cloned an empty
repository" and `git ls-remote` returns no refs (checked three times). None of
the 38 models are there, so every test naming one is SKIP, not PASS.

The harness is written and wired to the exact paths the plan named. When the
models are pushed, this is the whole procedure:

```bash
git clone https://github.com/maicen/bimguard-test-models.git test-models
BIMGUARD_E2E_MODELS="$(python3 -c "import json;print(json.dumps(json.load(open('e2e-models.json'))['models']))")" \
  uv run python scripts/e2e_server.py --port 8010 &
uv run python scripts/e2e_suite.py --manifest e2e-models.json --out test-results.json
```

`e2e-models.json` already maps every model the plan listed; only the files need
to arrive.

## Blocker 2 — architecture needs a database

The Part 9 ruleset is served from the `static_data_assets` table
(`ruleset:BUILDING-CODE-PART9`), not from the repository. Without Supabase
credentials the pack cannot be loaded, so the architectural analysis cannot be
verified on this machine at all — with or without the test models. GC-001,
CC-001 and MC-001 have the same arrangement, but their engines carry built-in
catalogs and still run; the database rules only override them. MM-001 and
XM-001 ship as files under `data/rulesets/` and seeded normally (117 and 18
rules).

**A defect this surfaced, now fixed.** The missing pack is loaded at module
import time and raised, so `POST /api/analyze/run` with `slug=architecture`
answered **HTTP 500 with a stack trace**. That breaks the contract
`analysis_runner` opens with — "errors cross this boundary as values, not
exceptions". `_run_architecture` now catches it and returns a failure result,
so the same request answers:

```
400 {"detail":"The architectural analysis could not be run: Missing static asset ruleset:BUILDING-CODE-PART9"}
```

Regression tests: `tests/test_analysis_runner_architecture.py` (5 tests).

## What did run

Model: `data/test_hospital_mep_scenario.ifc` (13 KB, IFC4, 4 elements). Small,
but it exercises the whole stack over real HTTP against a real uvicorn server.

### 1. Piping — engine gating (all PASS)

| Check | Selection | Findings by ruleset |
| --- | --- | --- |
| 1a | all five | `GC-001: 4, CC-001: 4, MC-001: 4, MM-001: 4` |
| 1b | GC/CC/MC | `GC-001: 4, CC-001: 4, MC-001: 4` — no MM/XM |
| 1c | MM/XM | `MM-001: 4` — no GC/CC/MC |
| 1d | GC only | `GC-001: 4` |
| 1d2 | none | no findings, as selected |

XM-001 runs and reports nothing on this model: it needs dissimilar-metal
couples, and this one has none. Its verdicts are covered by unit tests against
the synthetic piping network. MM-001's four findings are `data_quality`
("environment unclassified"), not verdicts — honest output for a model that
does not classify its environments.

### 1e. Cache separation (PASS)

Miss, then a different selection, then the original selection again: the third
run returned findings identical to the first and was faster. This model is too
small for the timings to mean anything (0.01 s); the separation is what the
check proves. Cache-key separation is also covered by
`tests/test_analysis_runner_engines.py`.

### 1f + 2c. Exports (all PASS)

| Analysis | CSV | JSON | BCF |
| --- | --- | --- | --- |
| corrosion (all engines) | 200, 16 rows = 16 findings | 200, parses | 200, 50 entries, 16 markup, 16 viewpoints |
| seismic | 200, 4 rows = 4 findings | 200, parses | 200, 14 entries, 4 markup, 4 viewpoints |

### 2. Seismic (PASS — first live verification)

`POST /api/analyze/run` with `slug=seismic`: **4 findings — 1 critical, 3
medium**, no data-quality gaps, in 0.01 s. BCF export carries a viewpoint per
finding. This is the live confirmation the analysis was missing; it had only
unit coverage before.

Not verified: that the findings are *correct* against DIN 4149 / EN 1998-1 on a
real structural model. That needs the structural models from the dataset.

## Known issues / notes

1. **The plan's API calls do not match the shipped API.** Whatever runs the
   full suite later needs to know:
   - There is no `model_file` parameter anywhere. A run analyses the IFC
     attached to the project; the harness maps project ids to files instead.
   - The slug is `architecture`, and the route is `POST /api/analyze/run`
     (or `/api/analyze/arch`) — there is no `/api/analyze/architecture`.
   - `/api/analyze/corrosion` takes form fields, not a JSON body.
   - Engine codes accept `GC` or `GC-001`; both resolve to the same engine.
2. **`/api/analyze/upload` requires Supabase Storage** with no local fallback,
   which is why the harness patches model retrieval rather than uploading. That
   is the only boundary it stands in for.
3. **Rule-pack coverage on this machine is partial**: GC/CC/MC ran on built-in
   catalogs rather than database rules, so this run does not exercise
   database-driven rule overrides.
4. The 29 failing unit tests are the long-standing baseline, all missing
   Supabase or missing static assets — unchanged by this work.

## Submission readiness

| Claim | Status |
| --- | --- |
| Piping analysis production-ready | Verified E2E, but on one 13 KB model only |
| Seismic analysis production-ready | Runs E2E and exports correctly; findings not validated against a real structural model |
| Architecture analysis production-ready | **Not verified** — needs a database |
| Exports working | Verified for corrosion and seismic; not for architecture |
| Performance acceptable | **Unknown** — no model here is large enough to measure |

**Ready for submission: NEEDS WORK** — not because a test failed, but because
the evidence does not exist yet. Two things unblock it: push the 38 models, and
run the suite against an environment with Supabase credentials.
