# Post-FMP backlog

Written 2026-09-09, against `origin/main` at `019f0f5`. Every `file:line` below
was checked against that commit as it stands in this worktree; where a cited
line had moved since it was first recorded, the current line is given and the
move is noted. Anything not present on `origin/main` is labelled with the branch
or commit it comes from.

None of these is a demo blocker. The frozen demo runs from tag `fmp-demo`
(`a55b70a`) and is unaffected by all of them.

---

## 1. Per-element engines accept non-service classes

**What.** The IFC reader treats architectural and structural classes as service
elements, so the corrosion engines score them as if they were pipework.
`app/modules/ifc_reader/ifc_parser.py:165-166` maps `IfcMember` → `JT-005` and
`IfcPlate` → `JT-014` (a joint type each), and
`app/modules/ifc_reader/piping_producer.py:136` accepts bare
`IfcDistributionElement` into the piping view.

**Evidence.** Branch `docs/engine-showcase-2026-09-08` at `761d3a7`.
`west_riverside_hospital_arc_ifc4.ifc` — an *architectural* model of 7,122
`IfcMember` and 2,211 `IfcPlate`, containing no pipes at all — produced **27,999
findings** on the five-engine run, including 6,630 GC-001 verdicts scoring
aluminium curtain-wall mullions against themselves (0 V self-couple) and 6,630
CC-001 Mediums on an unclassified joint type. Separately, MM-001's only
real-model verdicts in the whole corpus are **10 fire-extinguisher cabinets** on
`Clinic_Architectural.ifc`, scored against a `GalvanisedSteel` that was not read
from the model at all but inferred from the system name — `material_source:
system_inference:fire_sprinkler`.

**Why it is not in the demo.** The demo uses 1917 (synthetic, all real pipe
classes) and 1540 (genuine plumbing). Neither exercises the architectural path,
so no window frame appears in any demo number.

**Done would measure.** Re-running the showcase sweep on
`west_riverside_hospital_arc_ifc4.ifc` yields **0 corrosion findings**, and the
`IFC_SERVICE_LABELS` / piping-producer accept-lists name only distribution
classes that can carry a fluid. MM-001 verdicts derived from
`system_inference:*` are either suppressed or banded as inference rather than
reading.

## 2. Run provenance missing from `AnalysisResultContract`

**What.** The envelope the SPA receives cannot say how the run was
parameterised. `AnalysisResultContract`
(`app/modules/contracts.py:1014` — was `:963` before `019f0f5`) has no field for
the engine set, `include_low`, a run timestamp, the model file name or its
SHA-256, or a per-engine ruleset id. `_format_result`
(`app/api/analyze.py:175`) populates 9 of its 17 fields, leaving
`duration_seconds`, `elements_evaluated`, `unique_elements_evaluated`,
`rules_with_elements`, `pass_rate`, `bcf_artifact_id`, `summary` and `page`
unset on every real run.

**Evidence.** `docs/validation/engine-showcase-2026-09-08/00_entry_points.md` on
branch `docs/engine-showcase-2026-09-08` at `761d3a7`, §4 and its closing two
gaps. That showcase had to carry the provenance in `summary` — a real field the
API never fills — to produce a self-describing artefact.

**Why it is not in the demo.** The demo reads one project at a time with a human
who knows which chips are lit, so nothing on screen depends on the envelope
recording it.

**Done would measure.** An exported `result.json` from a real run names the
engine set, `include_low`, the model SHA-256 and each engine's `ruleset_version`
without the reader consulting the request that produced it.

## 3. F3 — `resolve_material` mis-resolves 8 of 20 galvanic-series keys

**What.** Two different normalisers decide the same value. The preflight gate
normalises with `ifc_parser._spaced()`
(`app/modules/ifc_reader/ifc_parser.py:248`), so `SS_316_passive` becomes
`ss 316 passive`, matches the alias `ss 316` and passes. The engine then calls
`resolve_material` (`app/modules/ifc_reader/piping_producer.py:1158`) on the raw
string, which does not separator-normalise, matches nothing, and returns
`carbon_steel`. The gate decides *whether* to score; the engine decides *what*
to score it as; they disagree.

**Evidence.** `docs/validation/final-godmode-audit-2026-09-07.md:228` — "F3 —
`resolve_material` mis-resolves 8 of the 20 galvanic-series keys, six of them to
`carbon_steel`". Worked examples at `:253` (`SS_316_passive → carbon_steel`,
`Galvanized_steel → carbon_steel`) and root cause at `:259`. `platinum →
carbon_steel` inverts the most noble entry in the table.

**Why it is not in the demo.** Latent on the demo corpus — 0 affected of 420
elements on 1917. It needs underscore-form material keys, which the demo models
do not carry.

**Done would measure.** All 20 series keys resolve to themselves, and the gate
and the engine call one normaliser.

## 4. `get_material_name()` coverage — every real MEP model reads 0 %

**What.** `app/modules/ifc_reader/ifc_parser.py:191` resolves a material for no
element of any real MEP model in the corpus, so GC-001 and CC-001 decline every
one of them.

**Evidence.** The showcase inventory on branch `docs/engine-showcase-2026-09-08`
at `761d3a7` (`01_inventory.md`): `west_riverside_hospital_plumb_ifc4` **0 of
8,539**, `west_riverside_hospital_mech_ifc4` **0 of 17,424**,
`west_riverside_hospital_sprinkle_ifc4` **0 of 13,490** — all 0.0 %. The
`feat/model-intake-ids` checker measured the same 0/8,539 on project 1540.
*Not located on `origin/main` — the checker is cited from
`feat/model-intake-ids`.*

**Why it is not in the demo.** The demo states this outright: 1540 is presented
as the model with no materials, and 29,181 data-quality notes is the intended
message.

**Done would measure.** A named percentage above zero on at least one real MEP
model — i.e. `IfcMaterial`/`IfcMaterialLayerSet` and property-set fallbacks are
read where the models actually put them.

## 5. Nominal diameter property names disagree

**What.** The generator writes one property name and the parser reads another.
`scripts/generate_demo_mep_model.py:464` writes `"InnerDiameter"` (with
`OuterDiameter`) into `Pset_PipeSegmentOccurrence`;
`app/modules/ifc_reader/piping_producer.py:1914` reads
`"NominalDiameter", "NominalDiameterMM", "DN", "Size"`. Nothing joins them, so
the generated diameter never reaches `nominal_diameter_mm`.

**Evidence.** The two lines above, both current on `019f0f5`. `OuterDiameter`
*is* read, at `piping_producer.py:1916` (`outside_diameter_mm`), so the mismatch
is specific to the nominal/inner pair.

**Why it is not in the demo.** MC-001 falls back to
`ASSUMED_NOMINAL_DIAMETER_M` and records that it did, so the demo shows a
declared assumption rather than a wrong number.

**Done would measure.** A generated model's elements report a
`nominal_diameter_mm` read from the file, and
`assumed_nominal_diameter_m` stops appearing in their metadata.

## 6. `/api/dashboard/stats` polling — Osama's scope, measurement only

**What.** The SPA polls the dashboard statistics endpoint for the life of the
tab, including while the user is inside a project. `checkHealth` is defined at
`frontend/src/App.svelte:127`, called on mount at `:268`, and re-armed by
`setInterval(checkHealth, 45000)` at `:279` — widened from ~40 s to 45 s by
`ba714e0`. A cheap `/api/health` exists at `app/api/__init__.py:68` and the
header chips do not use it.

**Evidence.** `docs/validation/final-verification-2026-09-09.md` (recorded by
`da28972`): 142 requests over an 80-minute session, 111 of them fired while the
browser was on a non-Dashboard route, median 6.8 s, slowest 13.1 s. Re-measured
2026-09-08 and recorded in `docs/demo/RUNBOOK.md` known limitations: 5–8 s to
fill.

**Why it is not in the demo.** It costs nothing visible once inside a project;
the runbook tells the presenter to open 1917 immediately rather than wait for
the tiles.

**Done would measure.** The header chips poll `/api/health`, and
`/api/dashboard/stats` is requested only while the Dashboard is mounted —
0 requests from a project route over a 30-minute session.

## 7. F2 — parser non-determinism on 1540

**What.** Two identical parses of the same file can assign material to a
different number of elements, moving MM-001's data-quality count. The material
resolution runs after system classification in
`app/modules/ifc_reader/piping_producer.py:1820-1875`, where the system is the
fallback source when the file carries no material of its own
(`:1829-1830` states exactly that).

**Evidence.** Audit F2, `docs/validation/final-audit-2026-09-06.md`: **29,181 /
29,183 / 29,181** across three sequential runs of project 1540, varying only in
MM-001's count. Band totals unaffected. Reproduced as 29,181 on the showcase
sweep at `761d3a7`.

**Why it is not in the demo.** The demo quotes 29,181 and the variation is two
issues in twenty-nine thousand, entirely inside data-quality notes.

**Done would measure.** Ten consecutive parses of 1540 return an identical
element-by-element material assignment.

## 8. F8 — absent flow velocity is scored as stagnant

**What.** MC-001 coerces a missing velocity to zero and then classifies zero as
the worst flow class. `app/engines/bimguard_mic_engine.py:297` reads
`element.flow_velocity_ms if element.flow_velocity_ms is not None else 0.0`, and
`classify_flow_velocity` treats `velocity_ms <= 0.0` as stagnant (`:51`).

**Evidence.** Audit F8, `docs/validation/final-audit-2026-09-06.md`:
structurally reachable, **0 occurrences on this corpus** — an element needs a
temperature but no velocity to hit it, and no model in the corpus has that
combination.

**Why it is not in the demo.** Zero occurrences on every demo model. The
hydraulics gate refuses elements where all three inputs are absent, which is the
common case.

**Done would measure.** An element with a temperature and no velocity produces a
data-quality note or an explicitly unknown flow class, never a stagnant band.

## 9. BCF steps 11–12 not implemented

**What.** The BCF export omits the camera frame derived from an element's
bounding box, and the status-change comments.

**Evidence.** `docs/demo/RUNBOOK.md:450` — "BCF export does not implement steps
11–12 — camera frame from bounding box and status-change comments are not
generated."

**Why it is not in the demo.** The archives validate and open: six BCF archives
produced across the showcase sweep at `761d3a7` returned **0 XSD violations**
against `tests/schemas/bcf21/markup.xsd`, including 2,937 seismic topics and
29,181 on 1540.

**Done would measure.** A topic opened in BIMCollab Zoom lands the camera on the
element without the reviewer navigating, and a status change made in the
receiving tool round-trips as a comment.

## 10. SB-001 `ruleset_version` stamp is regeneration-fragile

**What.** The seismic ruleset version is derived from the clearance config at
`app/modules/phase_6/phase_6d_seismic.py:146` (`_ruleset_version(config)`,
applied at `:558`). The config is produced by
`app/modules/blue_halo/hermes_config_expanded.py`; regenerating it without
carrying the version through would silently drop `BIMGUARD-SB-001 v1.0.0` from
every seismic finding.

**Evidence.** The showcase sweep at `761d3a7` recorded **0 findings missing
`ruleset_version` across all 31 runs**, seismic included — so the stamp is
present today. The risk is the regeneration path, not the current output.

**Why it is not in the demo.** The config has not been regenerated; the stamp is
on every one of the 2,937 seismic findings.

**Done would measure.** Regenerating `hermes_config_expanded.py` from source and
re-running seismic still stamps every finding, proven by a test that fails if
the version is empty.

## 11. Unapplied Supabase migrations

**What.** Four migration files exist in the build that have not been applied to
the Supabase project:

- `20260907202655_add_org_code_to_organizations.sql`
- `20260908141146_add_ifc_model_summary_metadata.sql`
- `20260908143524_cascade_model_enhancement_lineage_on_project_delete.sql`
- `20260908144003_add_ifc_file_id_to_model_enhancement_lineage.sql`
- `20260908144010_add_ifc_file_id_to_report_artifacts.sql`

**Evidence.** `ls supabase/migrations/` on `019f0f5`. The org-code one is
recorded as unapplied in `docs/demo/RUNBOOK.md` known limitations; the 8 Sept
batch arrived with Osama's model-service work (`d32c768`…`47681d9`).
*Which of the 8 Sept batch are applied was not verified — this session is
forbidden from touching Supabase, so the list is "present in the build,
application state unconfirmed" rather than "confirmed unapplied".*

**Why it is not in the demo.** None is needed by the frozen demo: the walkthrough
creates no organisation, uploads no model and generates no report artefact.
The demo runs from `a55b70a`, which predates the whole 8 Sept batch.

**Done would measure.** `list_migrations` on the remote and
`ls supabase/migrations/` return the same set, with no local file unrecorded.

## 12. Live-DB tests write to the production Supabase project

**What.** `tests/test_api_rules.py` creates and deletes rows in the live
Supabase project rather than against an isolated database. A failed run can
leave rows behind, and a concurrent run can see another's.

**Evidence.** `tests/test_api_rules.py:10` builds `TestClient(app)` against the
real application, then `POST`s a rule at `:38`, `PUT`s it at `:55` and `DELETE`s
it at `:62`, with a folder `DELETE` at `:71`. Those requests reach
`PersistenceService.get_db()` (`app/services/persistence.py:195`), which returns
a live Supabase client whenever `SUPABASE_URL` and a key are set and an
in-memory client only when they are not — so any developer with a working `.env`
runs these against production. `get_isolated_sqlite_db()` exists for exactly
this case (`app/services/persistence.py:245`) and this module does not use it.

**Why it is not in the demo.** Tests are not run during the demo. It is a
data-safety issue for the team, not a demo risk.

**Done would measure.** The module runs green with `SUPABASE_URL` unset, and a
deliberate mid-run abort leaves no row behind in the live project.

## 13. PD-001 Proximity / Drip-Path

**What.** A new mechanism: pipework whose leak or condensate path falls on
equipment below it. Blocked on its mechanism table.

**Evidence.** *Not located on `origin/main` — cited from branch
`feat/pd-001-sources`, which carries the mechanism table with **one sourced
row**. Five source PDFs are still pending; two of them were moved out of the
repository during this session's housekeeping to
`D:\Zigurat Masters\reference-pdfs\` (ASME B31.3-2020 Process Piping Workbook,
and Process Piping Fundamentals Module 1).*

**Why it is not in the demo.** The engine does not exist on `main`; there is
nothing to show.

**Done would measure.** The mechanism table has a sourced row per rule with a
citable clause, and PD-001 returns a banded verdict on the synthetic control.

## 14. EC-001 erosion-corrosion by velocity

**What.** A further mechanism: metal loss where flow velocity exceeds the
material's erosion threshold. Candidate to follow PD-001, since both need the
same hydraulic inputs.

**Evidence.** *Not located on `origin/main` — no branch, no rule table, no
engine module exists yet.* Its dependency is measured, though: the showcase
inventory at `761d3a7` shows **0 % hydraulics coverage on every real model**, so
EC-001 would return data-quality notes on the entire corpus exactly as MC-001
does today.

**Why it is not in the demo.** It does not exist, and the corpus could not feed
it if it did.

**Done would measure.** A model carrying real flow velocities produces EC-001
verdicts whose thresholds cite a standard, and the erosion band moves with
velocity rather than with material alone.

---

## Citation audit

| Status | Count | Notes |
| --- | ---: | --- |
| Verified as cited | 10 | line numbers confirmed in this worktree at `019f0f5` |
| Re-pointed | 2 | `AnalysisResultContract` moved `contracts.py:963` → `:1014`; item 12's persistence lines corrected to `:195` / `:245` |
| Not located on `origin/main` | 3 | item 4's intake checker (`feat/model-intake-ids`), item 13 (`feat/pd-001-sources`), item 14 (does not exist yet) |
