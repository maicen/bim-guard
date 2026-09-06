# FINAL AUDIT — BIMGUARD AI Piping and Seismic, read-only

Audit run: 2026-09-05 21:36 – 23:47 local (Windows 11, single machine).
No code was changed, nothing was committed. The only files created are this report and
`docs/validation/screenshots/final-audit/*.png`.

**Port**: `:8000` was already in use at the start of the session (`netstat` showed
`TCP 127.0.0.1:8000 LISTENING 39900`), so **this audit's backend ran on port 8001** and every
API call in steps 4–8 used `http://127.0.0.1:8001/api`. Step 9's frontend was served with
`VITE_API_URL` pointed at port 8001 (see step 9 note on the auth harness).

---

## 1. Baseline

| Item | Measured |
| --- | --- |
| Commit | `756b938`, branch `main` |
| Working tree | **Dirty** — modified: `.claude/settings.local.json`, `docs/validation/data/{CC,GC,MC}-001_validation_demo_asset_register.csv`; untracked: `docs/validation/VALIDATION_REPORT.md`, `docs/validation/data/engine-matrix.json` |
| Concurrent writer in the same tree | `tests/test_api_analyze.py` changed (+203 / −50) at **23:11**, mid-audit, by a process outside this audit — consistent with the other session that held port 8000. Not touched by this audit; noted because it means the tree was not stable for the whole run |
| `git fetch origin` | clean, no new remote commits |
| Root `.env` | **present** (2 lines: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, plus `FIRECRAWL_API_KEY`) |
| `frontend/.env` | **MISSING** — only `frontend/.env.example` exists, and it ships placeholders |
| Test suite (`uv run pytest -q`) | **1610 passed, 0 failed, 15 skipped, 4 xfailed**, 189.64 s wall (baseline expectation was 1,572 passed; measured count is higher, zero failures) |
| Frontend build (`npx vite build`) | **PASS**, 36.11 s, 3588 modules, `dist/index.html` 2.00 kB + `assets/index-*.js` 1,236.62 kB |
| Ruleset source | **Supabase** (not fallback) — see §2 |

## 2. Ruleset source — Supabase, not `_FALLBACK_RULESETS`

Evidence, all from this session's startup log (`backend8001.log`):

- 34 Supabase REST requests during boot, including
  `GET /rest/v1/static_data_assets?asset_key=eq.ruleset:BIMGUARD-GC-001 → 200 OK`
  and the same for `CC-001`, `MC-001`, `MM-001`, `XM-001`, `BUILDING-CODE-PART9`.
- **0** occurrences of `Using hardcoded fallback ruleset` (the warning emitted at
  `app/services/corrosion_rule_catalog.py:170`).
- **0** occurrences of `Static ruleset asset lookup failed`.
- `app/services/persistence.py:191` — `DB_BACKEND = "supabase"`.
- UI confirms live rule counts per ruleset: `BIMGUARD-GC-001 (195)`, `CC-001 (45)`,
  `MC-001 (57)`, `MM-001 (117)`, `XM-001 (18)`.

**PASS** — verdicts in this audit came from database catalogs, not the reduced offline tables.

## 3. Test models on disk

`uv run python scripts/fetch_test_model.py --set {west-riverside,clinic,duplex}` — all nine
files already present and hash-verified, nothing re-downloaded.

| File | Bytes | Schema |
| --- | --- | --- |
| `west_riverside_hospital_plumb_ifc4.ifc` | 23,762,808 | IFC4 |
| `west_riverside_hospital_mech_ifc4.ifc` | 73,047,260 | IFC4 |
| `west_riverside_hospital_str_ifc4.ifc` | 6,484,576 | IFC4 |
| `west_riverside_hospital_plumb_ifc2x3.ifc` | 24,998,920 | IFC2X3 |
| `Clinic_Plumbing.ifc` | 55,834,520 | IFC2X3 |
| `Clinic_HVAC.ifc` | 26,914,597 | IFC2X3 |
| `Clinic_Structural.ifc` | 19,058,175 | IFC2X3 |
| `Duplex_Plumbing_20121113.ifc` | 31,556,138 | IFC2X3 |
| `Duplex_MEP_20110907.ifc` | 17,871,432 | IFC2X3 |
| `Duplex_A_20110907.ifc` | 2,380,763 | IFC2X3 |

The fetch script's own measurement for the West Riverside set: **0.0 % materials resolved**
in all three files, 8,539 piping elements in the plumbing model.

---

## 4. Full check table

Every row is a number measured in this session.

### Step 1–3 — baseline, ruleset source, models

| # | Check | Result | Measured number |
| --- | --- | --- | --- |
| 1.1 | `git rev-parse --short HEAD` on `main` | PASS | `756b938` |
| 1.2 | Working tree clean | **FAIL** | 4 modified + 2 untracked files |
| 1.3 | Root `.env` exists | PASS | 1 file, 3 keys |
| 1.4 | `frontend/.env` exists | **FAIL** | 0 files (only `.env.example`) |
| 1.5 | `uv run pytest -q` | PASS | 1610 passed / 0 failed / 15 skipped / 4 xfailed, 189.64 s |
| 1.6 | `npx vite build` | PASS | exit 0, 36.11 s |
| 2.1 | Rulesets from Supabase, not fallback | PASS | 34 Supabase reads, 0 fallback warnings |
| 3.1 | Test models present with schema | PASS | 10 IFC files, schemas as tabled above |

### Step 4 — Piping audit, West Riverside plumbing IFC4 (project **1540**, created fresh)

| # | Check | Result | Measured number |
| --- | --- | --- | --- |
| 4.1 | Upload via `POST /api/projects/1540/upload` | PASS | HTTP 201, 19.41 s, 23,762,808 bytes stored |
| 4.2 | Parse | PASS | `schema=IFC4 elements=8539 piping=8539 types=2 warnings=1`; 157 s from storage-cache to parsed |
| 4.3 | `POST /api/analyze/corrosion`, 5 engines, `include_low=true` | PASS (ran) | HTTP 200, **282.36 s**, 29,181 issues |
| 4.4 | GET `/results` total findings | PASS (returned) | **29,181** issues |
| 4.5 | Scored verdicts per engine (Critical/High/Medium/Low) | **FAIL** | GC-001 0/0/0/0 · CC-001 0/0/0/0 · MC-001 0/0/0/0 · MM-001 0/0/0/0 · XM-001 0/0/0/0 — **0 scored verdicts in total** |
| 4.6 | Data-quality issues per engine | — | GC-001 8,539 · CC-001 8,539 · MC-001 8,539 · MM-001 3,563 · XM-001 1 |
| 4.7 | Data-quality by check/reason | — | `material_unresolved` 8,539 (GC-001) + 8,539 (CC-001); `hydraulics_unavailable` 8,539 (MC-001); `material_normalisation` 3,563 (MM-001); `material_not_in_series` 1 (XM-001) |
| 4.8 | Defect A regression (dominant band+score share ≤ 90 %) | **N/A — 0 scored elements** | GC 0, CC 0, MC 0, MM 0, XM 0 scored elements; the uniform-verdict test has no population to run against on this model |
| 4.9 | Provenance: `material_source` on 5 sampled findings | PASS | 5 of 5 (`absent` on all five) |
| 4.10 | Provenance: `environment_source` | PASS | 5 of 5 (`default_indoor`, confidence `low`) |
| 4.11 | Provenance: `temperature_source` | **FAIL** | 1 of 5 (MM-001 only; absent on GC-001, CC-001, MC-001, XM-001 — MC-001 reports `operating_temp_c: null` with no source field) |
| 4.12 | Provenance: `ruleset_version` | **FAIL** | 0 of 5 on this model's findings (all are data-quality notes) |
| 4.13 | Provenance: GC-001 `galvanic_couple` | **FAIL** | 0 of 1 GC-001 findings on this model (no couple could be formed) |

### Step 5 — Piping audit, `data/test_hospital_mep_scenario.ifc` (project **1541**)

Analysis: HTTP 200, **8.53 s**, 4 elements, 14 issues.

| # | Check | Result | Measured number |
| --- | --- | --- | --- |
| 5.1 | GC-001 bands | PASS | Critical 0 / High 0 / Medium 0 / **Low 4**; data_quality 0 |
| 5.2 | CC-001 bands | PASS | Critical 0 / High 0 / **Medium 4** / Low 0; data_quality 0 |
| 5.3 | MC-001 bands | **0 verdicts** | 0/0/0/0 scored; **4 data_quality** (`hydraulics_unavailable`) |
| 5.4 | MM-001 bands | PASS | 0/0/**1**/0; 1 data_quality (`unmapped_pairing`) |
| 5.5 | XM-001 bands | **0 issues at all** | 0 scored, 0 data_quality — XM-001 emitted nothing on this model |
| 5.6 | Engines with ≥1 non-Undetermined verdict | — | **GC-001, CC-001, MM-001** produced scored verdicts (9 total). **MC-001 produced none (0)** — expectation confirmed. **XM-001 produced none (0)** |
| 5.7 | Defect A on scored elements | **FAIL as measured** | GC-001 4/4 = 100 % at `(low, 0.0)`; CC-001 4/4 = 100 % at `(medium, 0.37)`; MM-001 1/1 = 100 % at `(medium, 0.46)`. Populations are 4, 4 and 1 elements — above the 90 % threshold, but too small to distinguish a uniform-verdict defect from a homogeneous 4-element fixture |
| 5.8 | `ruleset_version` on scored findings | PASS | present on GC-001 (`BIMGUARD-GC-001 v1.0.0`) and CC-001 (`BIMGUARD-CC-001 v1.0.0`); **absent on the MM-001 scored finding** |
| 5.9 | `galvanic_couple` on scored GC-001 | PASS | present — `single_material_self_couple` |

### Step 6 — Piping exports (project 1540)

| # | Check | Result | Measured number |
| --- | --- | --- | --- |
| 6.1 | `fmt=csv&include_low=true` | HTTP 200 | **29,183 rows**, 11,440,681 bytes, 165.5 s |
| 6.2 | CSV rows == Low+Medium+High+Critical from step 4 | **FAIL** | CSV 29,183 vs scored-band total **0**. Every row is `is_data_quality=yes`, band `low`. Per prefix: CC 8,539 · GC 8,539 · MC 8,539 · MM 3,565 · XM 1 |
| 6.3 | `fmt=json` parses | PASS | 34,590,424 bytes, valid JSON, 3.9 s |
| 6.4 | JSON finding count == CSV count | **FAIL** | JSON `findings` = **0**; the 29,183 records sit under a separate `data_quality` key. Counting `findings + data_quality` gives 29,183 = CSV |
| 6.5 | `fmt=bcf` topic count | HTTP 200 | **29,183 topics**, 54,849,989 bytes, 29.9 s, 87,551 zip entries |
| 6.6 | BCF topics == Medium+High+Critical from step 4 | **FAIL** | 29,183 topics vs expected **0**. Low/data-quality notes are emitted as BCF topics with `Priority=Minor` |
| 6.7 | `validate_bcf_corpus.py` XSD violations | PASS | **0** violations, 1/1 archives valid, 29,183 topics validated |
| 6.8 | Every Component `IfcGuid` is a 22-char IFC GUID | PASS | **58,366** `IfcGuid` attributes checked, **0** non-conforming |

### Step 7 — Seismic

| # | Check | Result | Measured number |
| --- | --- | --- | --- |
| 7.1 | Attach all three West Riverside discipline models (project **1542**) | **FAIL** | HTTP 500 — `west_riverside_hospital_mech_ifc4.ifc could not be stored: {'statusCode': 413, 'error': Payload too large}`. 2 of 3 attached (plumb IFC4 23.8 MB, str IFC4 6.5 MB); the 69.7 MB mech model could not be uploaded |
| 7.2 | Federated seismic run | PASS (ran) | HTTP 200, **852.17 s**; log: `models=2 elements=10547 in_class=4308 braced=789 below_threshold=3519 unmeasurable=0 threshold_mm=63.0 clashes=2937` |
| 7.3 | Federated clash count | — | **2,937** (Critical 783 / High 314 / Medium 1,840 / Low 0 / data_quality 0) |
| 7.4 | Per-file clash counts | — | halo source `west_riverside_hospital_plumb_ifc4.ifc` = 2,937 (the structural model contributes clash candidates, not halos) |
| 7.5 | Cross-model clashes | — | **886** (`plumb_ifc4` halo vs `primary model`); intra-model 2,051 |
| 7.6 | Matches the recorded federated 19,552 | **FAIL — does not match** | measured **2,937** vs recorded 19,552. The runs are not comparable: this federation is 2 models, not the 3 named buildings, because 7.1 blocked the 69.7 MB mech model |
| 7.7 | `plumb_ifc2x3` alone (project 1591) | PASS | **2,403** clashes (recorded 2,403 — **matches exactly**), 815.78 s, `models=1 elements=9121` |
| 7.8 | `plumb_ifc4` alone (project 1540) | PASS | **2,051** clashes (recorded 2,051 — **matches exactly**), 768.53 s, `models=1 elements=7650` |
| 7.9 | Seismic CSV export | PASS | 2,937 rows, 1,328,453 bytes, 0.45 s |
| 7.10 | CSV `overlap_volume_mm3` non-empty | PASS | **2,937 of 2,937** rows |
| 7.11 | CSV `clearance_mm` non-empty | PASS | **2,937 of 2,937** rows |
| 7.12 | Seismic BCF export | PASS | **2,937 topics**, 5,512,029 bytes, 2.9 s |
| 7.13 | Seismic BCF XSD violations | PASS | **0** violations, 1/1 archives valid, 2,937 topics validated |
| 7.14 | Seismic BCF `IfcGuid` conformance | PASS | **5,874** attributes, **0** non-conforming |

### Step 8 — Cache honesty

| # | Check | Result | Measured number |
| --- | --- | --- | --- |
| 8.1 | Identical `POST /api/analyze/corrosion` re-run returns `cached=true` | **FAIL** | `cached=false`, **140.96 s** recompute. `app/api/analyze.py:501` hard-codes `use_cache=False`, so this endpoint can never report a hit |
| 8.2 | Identical re-run has identical band counts | **FAIL** | scored bands identical (all 0), but totals differ across runs of the same model+engines: **29,181** (first run) / **29,183** (export run) / **29,181** (re-run). MM-001 alone moved 3,563 → 3,565 → 3,563 |
| 8.3 | Dropping XM-001 gives `cached=false` and a recompute | PASS | `cached=false`, **98.83 s**, 29,182 issues (`GC 8,539 · CC 8,539 · MC 8,539 · MM 3,565`), log confirms a fresh `Corrosion analysis complete … mechanisms=GC-001,CC-001,MC-001,MM-001` |
| 8.4 | Cache does work somewhere | PASS | `GET /api/analyze/results/1540/corrosion?use_cache=true…` returned `cached=true` in **354 ms** and again in **309 ms**, identical stats (data_quality 29,183, all verdict bands 0) |

### Step 9 — Signed-in UI smoke test (dev server on :5173, backend :8001)

| # | Check | Result | Measured number / failure text |
| --- | --- | --- | --- |
| 9.1 | "Sign in as dev test user" button present | PASS with `VITE_DEV_AUTH_*` supplied | 1 button on `/#/login` |
| 9.2 | Clicking it signs in | **FAIL** | `POST https://…supabase.co/auth/v1/token?grant_type=password → 401`, body: `"Forbidden use of secret API key in browser"`. `frontend/.env` is missing and `frontend/.env.example` ships placeholders (`VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co`, `VITE_SUPABASE_ANON_KEY` = an 18-char `sb_publishab…` stub), so no usable browser key exists in this checkout |
| 9.3 | Signed-in shell renders | PASS (harness) | Achieved by running the dev server with Supabase auth left unconfigured and `VITE_API_URL` pointed at a local reverse proxy on `:8002` that attaches the real `dev@bim-guard.local` JWT. Nothing in the app was modified |
| 9.4 | Projects list renders | PASS | **10** table rows (`GET /api/projects` → `total: 34`) |
| 9.5 | Piping audit page for project 1540 renders findings | PASS | **50** rows on page 1; header reads "Audit Findings 29,181 of 29,181" |
| 9.6 | Stat cards show non-zero numbers | PASS on the literal check, **but** | the only non-zero tile is **DATA QUALITY 29,181**. TOTAL FINDINGS 0, CRITICAL 0, HIGH RISK 0, MEDIUM RISK 0, LOW RISK 0 |
| 9.7 | Toggling an engine chip changes the table | **FAIL** | Clicked the `XM-001` chip; after 30 s: rows 50 → 50, row content unchanged, and no re-query had completed. A results page load on this project takes **412 s** server-side, so a chip-driven refetch cannot land inside any reasonable interaction window |
| 9.8 | CSV download from the UI | PASS | `bimguard-corrosion-project-1540.csv` = **11,439,771 bytes** |
| 9.9 | BCF download from the UI | PASS | `bimguard-corrosion-project-1540.bcf` = **54,844,871 bytes** |
| 9.10 | Seismic page shows the completed run for project 1542 | **FAIL** | Page renders correctly (project bound, "MODEL READY") but the body reads **"No Analysis Run Loaded"** — 0 rows after waiting 900 s, despite a completed 2,937-clash run for that project |
| 9.11 | Seismic clashes render after pressing "Run Audit" in the UI | PASS | **50** rows, page shows clearance values |
| 9.12 | Screenshots captured | PASS | 7 PNGs in `docs/validation/screenshots/final-audit/` (01-login, 02-after-signin, 02b-signed-in, 03-projects, 04-piping-audit, 05-piping-chip-toggled, 06-seismic) |

---

## 5. FAILURES

Each with the error as observed and the file:line held responsible. No fixes proposed.

**F1 — Every JWT-authenticated endpoint returns HTTP 500 on a default checkout.**
`RuntimeError: SUPABASE_JWKS_URL is not configured` — `app/auth.py:43`, reached from
`app/auth.py:51` → `app/auth.py:76`. The root `.env` in this checkout carries only
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `FIRECRAWL_API_KEY`. `GET /api/auth/me` and
`POST /api/projects` both returned `Internal Server Error` until the variable was supplied
through the process environment. Steps 4–9 were run with it supplied.

**F2 — `frontend/.env` absent and `frontend/.env.example` contains placeholders.**
`frontend/.env.example` lines 5–6: `VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co`
and an 18-character `sb_publishab…` stub for `VITE_SUPABASE_ANON_KEY`. `CLAUDE.md` states the
example "already ships working … values for the shared dev account". It does not, so the
documented one-step local sign-in cannot work on any machine. Consequence recorded at 9.2.

**F3 — Sign-in via the dev button is rejected by Supabase.**
`401 {"message":"Forbidden use of secret API key in browser"}` from
`/auth/v1/token?grant_type=password`, triggered from
`frontend/src/lib/auth.svelte.ts:136-137`. Any key available in this checkout is a secret key,
which GoTrue refuses from a browser origin. Downstream of F2.

**F4 — A 69.7 MB IFC cannot be attached; the endpoint 500s and half-attaches.**
`storage3.exceptions.StorageApiError: {'statusCode': 413, 'error': Payload too large}` raised at
`app/services/object_storage.py:54`, propagated at `app/modules/phase_6/phase_6a_upload.py:233`,
surfaced by `POST /api/projects/{id}/upload` as HTTP 500 with
`"… could not be stored: … 1 of 3 models were attached."`. This is what prevented the three-model
federated seismic comparison at 7.6.

**F5 — The same model and the same engines do not produce the same issue count.**
29,181 → 29,183 → 29,181 across three runs of project 1540 with all five engines, and MM-001's
own count moved 3,563 → 3,565 → 3,563. MM-001 emits one issue per element that bands Medium+ or
cannot be scored (`app/modules/comparator/material_media.py:431-435`), so the varying quantity is
the set of elements MM-001 considers scoreable, which is decided upstream in
`app/modules/ifc_reader/piping_producer.py:_build_element:1847-1888` (material / environment /
temperature resolution). No `random` or thread-pool use is present in either path.

**F6 — `POST /api/analyze/corrosion` can never report a cache hit.**
`app/api/analyze.py:501` passes `use_cache=False` unconditionally, so the endpoint recomputes on
every call (140.96 s measured) and always answers `cached=false`. The cache itself is functional —
`GET /api/analyze/results/…?use_cache=true` returned `cached=true` in 354 ms (8.4).

**F7 — Exports recompute the whole analysis instead of reading the stored result.**
`GET /api/analyze/export?fmt=csv` on project 1540 took 165.5 s and the server logged a fresh
`Corrosion analysis complete elements=8539 issues=29183` for it
(`app/modules/phase_6/phase_6c_corrosion_ui.py:1009`), i.e. the export ran the engines again and
produced a count two issues different from the run it was meant to export.

**F8 — BCF and CSV exports do not honour the documented band contract.**
The rulesets state Low → "Asset register only — no BCF issue"
(`app/services/corrosion_rule_catalog.py`, `risk_bands` entries). The step-6 archive contains
**29,183 topics** for a run whose Medium+High+Critical total is **0**; each is a data-quality note
written with `Priority=Minor` at `app/services/bcf_exporter.py:221`. The CSV likewise emits
29,183 rows against 0 scored verdicts.

**F9 — JSON export splits findings from data-quality, so `findings` reads 0.**
`export4.json` has `findings: []` and `data_quality: [29,183 records]`. Any consumer counting
`findings` sees an empty audit for a run that produced 29,183 records. Written by
`app/modules/phase_6/phase_6e_export.py`.

**F10 — The Seismic view does not load an existing completed run.**
Opening `/#/seismic?project_id=1542` after a successful 2,937-clash run renders
"No Analysis Run Loaded" and 0 rows (waited 900 s). Pressing "Run Audit" recomputes and then
renders 50 rows. `frontend/src/routes/AnalyzeView.svelte` (the shared Piping/Seismic view,
mounted at `App.svelte:512-520`).

**F11 — Engine chip toggling does not change the table in usable time.**
Clicking the `XM-001` chip left the table byte-identical after 30 s. The underlying results
request for this project measured **412 s** server-side
(`GET /api/analyze/results/1540/corrosion … duration_ms=412291.3`), because the cached entry
expires after `TTL_SECONDS = 1800.0` (`app/services/analysis_cache.py:57`) and every miss reruns
all five engines. `toggleEngine` → `reloadAfterFilterChange` at
`frontend/src/routes/AnalyzeView.svelte:117-122`.

**F12 — Authenticated endpoints degraded to HTTP 500 on a long-lived backend process.**
After two ~280 s corrosion analyses on the same uvicorn process, `GET /api/auth/me` and
`POST /api/projects` — both of which had succeeded on that process 7 minutes earlier — returned
`Internal Server Error` on every subsequent attempt. Restarting the process restored them
immediately. The traceback was lost when the process was killed (stdout was block-buffered), so
the responsible line is not established; the dependency involved is `app/auth.py:76`
(`get_current_user`, executed via `run_in_threadpool`).

**F13 — Zero scored verdicts on the primary real model.**
On `west_riverside_hospital_plumb_ifc4.ifc` all 29,181 outputs are data-quality notes and no
engine produced a single Critical/High/Medium/Low verdict (4.5). Cause is visible in the model
itself and in the reader's own log line
(`app/modules/ifc_reader/piping_producer.py:_log_material_coverage:2052`): the file associates no
material with any element. This is recorded as a failure of the end-to-end result, not of the
engines' logic — the engines correctly refused to score unassessable elements.

**F14 — Provenance fields are incomplete on data-quality findings.**
`ruleset_version` is absent from all five sampled step-4 findings and from the MM-001 scored
finding in step 5; `temperature_source` appears on MM-001 only, including on MC-001 findings that
explicitly report `operating_temp_c: null`. Emitted by
`app/modules/phase_6/phase_6c_corrosion_ui.py`.

**F15 — Cross-model clash provenance is a label, not a filename.**
886 federated clashes report `clashing_source_model: "primary model"` instead of
`west_riverside_hospital_str_ifc4.ifc`, so a coordinator cannot tell which model the clashing
element came from. `app/modules/phase_6/phase_6d_seismic.py` (`source_of` mapping, issue metadata
at lines 195-225).

---

## 6. KNOWN LIMITATIONS (observed, not counted as failures)

- **MC-001 produces no verdicts without hydraulic data.** 8,539 of 8,539 elements on the West
  Riverside model and 4 of 4 on the MEP scenario returned `hydraulics_unavailable`
  (`flow_velocity_ms`, `dead_leg_length_m`, `operating_temp_c` all `null`). No IFC in this corpus
  carries the properties MC-001 needs. The engine's refusal to score is deliberate and documented
  in its own reason string.
- **Seismic score is a band-derived placeholder.** `app/modules/phase_6/phase_6d_seismic.py:206-215`
  maps Critical→0.9, High→0.7, Medium→0.4, Low→0.1 with the comment "a band-consistent placeholder
  is honest, a fabricated ratio is not". Every one of the 2,937 clashes carries one of exactly
  three score values.
- **`/api/analyze/*` has no auth dependency.** `app/api/analyze.py` contains zero occurrences of
  `get_current_user`; the OpenAPI document shows `security: (none)` for
  `POST /api/analyze/corrosion`, `POST /api/analyze/seismic` and `GET /api/analyze/export`, while
  `POST /api/projects` requires `HTTPBearer`. Anyone who can reach the port can run an analysis and
  download any project's findings.
- **Fallback rulesets were not in play.** Step 2 confirmed Supabase; the reduced
  `_FALLBACK_RULESETS` tables were never consulted in this session.
- **Analysis cache TTL is 30 minutes with 32 entries** (`app/services/analysis_cache.py:52,57`), so
  a results page revisited after half an hour costs a full recompute — 412 s measured for the
  step-4 project.
- **XM-001 is close to silent.** 1 issue on 8,539 elements (West Riverside) and 0 issues on the
  4-element MEP scenario.
- **The federated seismic figure in this report is not comparable to the recorded 19,552**, because
  only two of the three intended models could be attached (F4).

---

## 7. VERDICT

**Yes for Seismic, qualified yes for Piping.** The seismic path runs end to end on real IFC and is
reproducible against the recorded baseline: 2,403 clashes on `west_riverside_hospital_plumb_ifc2x3`
and 2,051 on `west_riverside_hospital_plumb_ifc4`, both matching the recorded values exactly, and
2,937 on a two-model federation with 886 genuine cross-model clashes; its CSV carries
`overlap_volume_mm3` and `clearance_mm` on 2,937 of 2,937 rows and its BCF archive validates with
0 XSD violations across 2,937 topics and 5,874 conforming 22-character IfcGuids. The piping path
also runs end to end — 8,539 elements parsed from a 23.8 MB IFC4 file, five engines executed in
282 s, 29,181 records returned, and CSV (11.4 MB), JSON (34.6 MB) and BCF (54.8 MB, 0 XSD
violations, 58,366 valid IfcGuids) all produced and downloadable from the signed-in UI — but on
that real model it delivers **zero risk verdicts**: 0 Critical, 0 High, 0 Medium, 0 Low across all
five engines, with all 29,181 outputs being data-quality notes, because the model associates no
material with any element. The engines demonstrably do score when the data is present (9 scored
verdicts across GC-001, CC-001 and MM-001 on the 4-element MEP scenario, carrying `ruleset_version`
and `galvanic_couple` provenance), so the compliance logic is live rather than stubbed; what the
build cannot yet show is a corrosion verdict population large enough to test — the Defect A
uniform-verdict regression could not be evaluated at all on the real model (0 scored elements) and
was measured on populations of 4, 4 and 1 elements elsewhere. Add the export contract deviations
(29,183 BCF topics and CSV rows against 0 scored verdicts, JSON `findings` reading 0), the
never-cached analyse endpoint (`cached=false` on an identical re-run, 141 s), a run-to-run count
that moves by two issues on identical input, and the configuration defects that make a default
checkout return HTTP 500 on every authenticated endpoint and unable to sign in through the UI, and
the honest summary is: valid Seismic outputs today, valid Piping *machinery* today, and a Piping
audit that will only produce defensible verdicts once it is pointed at models that carry materials.

---

## Addendum — 6 September 2026

Status of every failure in §5 after the day's work. Commit hashes are on
`origin/main`.

### Fixed

| # | What it was | Commit |
| --- | --- | --- |
| F6 | `POST /analyze/corrosion` and `/analyze/seismic` passed `use_cache=False` unconditionally, so an identical re-run always recomputed and always reported `cached=false` | `3ef0d5a` |
| F7 | The export forwarded the caller's `include_low` into the run, forking the cache key and recomputing the analysis it was meant to export | `3ef0d5a` |
| F8 | BCF and CSV carried Low verdicts and data-quality notes against the rulesets' "Low → asset register only, no BCF issue" | `3ef0d5a` (API defaults per format), `c673c0f` (UI export call) |
| F11 | Chip toggling could not change the table in usable time: the cache expired after 30 minutes and every miss re-ran five engines | `729b7ae` (capacity 64, TTL 86400 s, both env-configurable) |
| F14 | MM-001 scored findings carried no `ruleset_version` | `1ec7a76` |
| F15 | 886 federated clashes reported `clashing_source_model: "primary model"` instead of a file name | `8559979` |

Range `729b7ae..c673c0f` (five commits, in order: `729b7ae`, `3ef0d5a`,
`1ec7a76`, `8559979`, `c673c0f`).

Measured after the fixes, backend on port 8000:

- Second identical `POST /analyze/corrosion` on project 1540: `cached=true`,
  1.59 s against the first run's 39.2 s, both totalling 29,181 issues.
- Second `POST /analyze/seismic` on 1542: `cached=true`, 0.54 s against 187.7 s,
  both 2,937 clashes.
- CSV export of 1540: 0.477 s (was 165.5 s), 29,181 rows, equal to the results
  total.
- Three analyses plus four exports produced **2** engine runs in the log — one
  per project. No export recomputed.
- BCF defaults: 0 topics on 1540 (Medium+High+Critical = 0) and 5 topics on 1541
  (Medium 5 + High 0 + Critical 0 — four CC-001, one MM-001).
- MM-001 finding on 1541 carries `ruleset_version: BIMGUARD-MM-001 v1.0.0`.
- All 886 cross-model clashes on 1542 name both files; zero `"primary model"`
  labels remain across 2,937 issues.

### F10 — fixed elsewhere, verified here

Commit `8211d09` sets `selectedSlug` from `activeCategory` before the mount
fetch. Verified live on **6 September 2026, 09:22 local**, without pressing Run
Audit:

| Page | Rows | Header | Time to rows |
| --- | --- | --- | --- |
| `/#/seismic?project_id=1542` | 50 | `Audit Findings 2,937 of 2,937` | 1.1 s |
| `/#/piping?project_id=1541` | 14 | `Audit Findings 14 of 14` | 1.0 s |

Neither page showed "No Analysis Run Loaded". Screenshots:
`docs/validation/screenshots/f10-seismic-loads.png`,
`docs/validation/screenshots/f10-piping-loads.png`.

### Configuration, not code — owner: Shane

| # | What is needed |
| --- | --- |
| F1 | `SUPABASE_JWKS_URL` in the root `.env`. Without it every signed-in endpoint returns 500 from the first request |
| F2 | `frontend/.env` does not exist in this checkout. `frontend/.env.example` ships the dev email and password but placeholders for `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` |
| F3 | Downstream of F2: the dev sign-in button renders and returns `401 Invalid API key`, because the only key in the checkout is a placeholder. Re-tested 6 Sept — unchanged |

`CLAUDE.md` was corrected on 6 Sept: it had claimed the example "already ships
working" values.

### Closed as not-defects

- **F9** — the JSON export's `findings` and `data_quality` are two keys of one
  payload, not a lost half. `findings + data_quality` equals the CSV row count
  (29,183 in the audit, re-measured at 7 on the synthetic fixture). The reading
  that `findings: []` meant an empty audit was mine; the split is deliberate,
  and the export tests now pin the sum.
- **F13** — zero scored verdicts on West Riverside is the engines refusing to
  score elements the model gives no material for. 29,181 data-quality notes,
  each naming its check and reason, is the correct output for that input, not a
  failure of the build. It stays a demo-day talking point, not a defect.

### Still open

| # | Status |
| --- | --- |
| F4 | Supabase storage returns `413 Payload too large` for the 69.7 MB mechanical model; the upload endpoint answers 500 having attached the models that fit. Unchanged |
| F5 | 29,181 / 29,183 / 29,181 issues across three identical runs of project 1540, varying in MM-001's count; re-observed 6 Sept (runs 1–2 at 29,181, run 3 at 29,183). Band totals unaffected |
| F12 | Not reproduced. Three forced recomputes (107.9 s, 135.9 s, 139.6 s) over 6.8 minutes on one process on 6 Sept, with `GET /api/auth/me` and `POST /api/projects` checked after the second and third: 200/201 every time, zero 5xx and zero tracebacks in the log. The token had 3,168 s of life left at the final check, so expiry is ruled out here and in the original occurrence (~8 minutes into a 3,600 s lifetime). No file:line established |

### Superseded in §6

The line "Analysis cache TTL is 30 minutes with 32 entries" describes the
pre-fix build. It is now 86,400 seconds and 64 entries, both overridable via
`BIMGUARD_CACHE_TTL_SECONDS` and `BIMGUARD_CACHE_ENTRIES`.
