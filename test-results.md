# BIMGUARD E2E Validation Results

Date: 2026-08-30
Commit: 0d36df3 (harness) — analyses ran against the code at e354f2f
Dataset: maicen/bimguard-test-models — 34 IFC models, 807.4 MB of IFC (950 MB checked out)
Harness: `scripts/e2e_server.py` + `scripts/e2e_suite.py`, manifest `e2e-models.json`
Machine record: `test-results.json`

## What this run adds over the previous one

The previous pass could not run the architectural analysis at all and did not
know what the corrosion engines would do against a populated database, because
the rule packs live in `supabase/migrations/20260806180500_seed_static_data_assets.sql`
rather than in the repository tree. This run loads those rows through the
shipped `StaticDataService` and runs **two passes over the same models**:

| Pass | Server | What it represents |
| --- | --- | --- |
| 1 | `e2e_server.py` | The shipped default on a machine with no database: engines on their built-in fallback catalogs, architecture unavailable |
| 2 | `e2e_server.py --seed-code-rulesets` | The same code with the migration's rule packs resident: engines on database catalogs, architecture running |

The two passes disagree, and the disagreement is the most important result here.

## Summary

**Pass 1 — 88 checks: 76 PASS, 7 FAIL, 5 WARN, 0 SKIP.** About 90 analyses over
real HTTP against a live uvicorn server.

| Category | Models | Result |
| --- | --- | --- |
| 1. Piping — engine gating | 15 | **PASS** — the gate held on every model |
| 2. Piping — cache separation | 4 | **PASS** — 40x–60x speedup on a hit |
| 3. Exports (BCF/CSV/JSON) | 5 | **PASS** — counts match findings exactly |
| 4. Seismic | 3 structural + 2 geometry | **RUNS, EVALUATES NOTHING** — finding 4 |
| 5. Architecture | 5 | **FAIL without a database** — finding 1 |
| 6. Schema robustness | 2 twin pairs | **PASS on parsing, FAIL as written** — finding 5 |
| 7. Geometry robustness | 2 | Parsed without crashing, no findings |
| 8. Performance | 4 tiers | **PASS** — baseline below |

## 1. Piping — engine gating (15 models, all PASS)

Every model got the three-way gate check; four also got single-engine and
empty-selection variants. Not one leaked an unselected engine.

| Model | Schema | MB | All five engines | Cold |
| --- | --- | --- | --- | --- |
| Clinic_Plumbing | IFC2X3 | 53.2 | GC/CC/MC 6587 each, MM 6587, **XM 906** | 39.6 s |
| Clinic_HVAC | IFC2X3 | 25.7 | GC/CC/MC 3704 each, MM 3704, **XM 16775** | 17.5 s |
| wr_plumb_ifc4 | IFC4 | 22.7 | GC/CC/MC 8539 each, MM 8539, XM 0 | 31.0 s |
| wr_mech_ifc4 | IFC4 | 69.7 | GC/CC/MC 17424 each, MM 17424, XM 0 | 86.1 s |
| wr_sprinkler_ifc4 | IFC4 | 32.4 | GC/CC/MC 13490 each, MM 13490, **XM 5** | 61.2 s |
| wr_plumb_ifc2x3 | IFC2X3 | 23.8 | GC/CC/MC 9013 each, MM 9013, XM 0 | 33.1 s |
| wr_mech_ifc2x3 | IFC2X3 | 75.1 | GC/CC/MC 18488 each, MM 18488, XM 0 | 92.4 s |
| Duplex_MEP | IFC2X3 | 17.0 | GC/CC/MC 926 each, MM 926, XM 0 | 3.9 s |
| Duplex_Plumbing | IFC2X3 | 30.1 | GC/CC/MC 498 each, MM 498, **XM 74** | 4.4 s |
| DigitalHub_HZG | IFC4 | 19.9 | GC/CC/MC 1795 each, MM 1795, XM 0 | 6.4 s |
| DigitalHub_SAN | IFC4 | 24.0 | GC/CC/MC 1010 each, MM 1010, XM 0 | 3.8 s |
| DigitalHub_LFT | IFC4 | 12.2 | GC/CC/MC 1310 each, MM 1310, XM 0 | 4.8 s |
| wbdg_office_mep | IFC2X3 | 40.0 | GC/CC/MC 5697 each, MM 5697, **XM 830** | 38.3 s |
| IFC_Schependomlaan | IFC2X3 | 47.0 | GC/CC/MC 82 each, MM 73, XM 0 | 5.6 s |
| craslabbim | IFC2X3 | 64.4 | no elements extracted | 7.3 s |

All five engines are user-selectable and every selection was honoured:
element-only never produced MM/XM, network-only never produced GC/CC/MC, a
single-engine selection produced only that engine, and an empty selection
produced nothing.

## 2. Cache separation (4 models, all PASS)

Miss, a different selection, then the original selection again: identical
findings, and the hit is dramatically faster.

| Model | Cold | Other selection | Cached hit |
| --- | --- | --- | --- |
| Clinic_Plumbing 53 MB | 36.7 s | 22.6 s | **0.59 s** |
| wr_plumb_ifc4 23 MB | 30.5 s | 14.0 s | **1.87 s** |
| DigitalHub_SAN 24 MB | 4.7 s | 0.05 s | 0.11 s |
| Duplex_MEP 17 MB | 4.0 s | 0.04 s | 0.10 s |

## 3. Exports (all PASS)

| Analysis | CSV | BCF |
| --- | --- | --- |
| wr_plumb_ifc4 corrosion | 34 156 rows = 34 156 findings | 102 470 entries, 34 156 topics + viewpoints |
| Clinic_Plumbing corrosion | 27 254 rows = 27 254 findings | 81 764 entries, 27 254 topics + viewpoints |
| Duplex_MEP corrosion | 3 704 rows = 3 704 findings | 11 114 entries, 3 704 topics + viewpoints |
| Clinic_Structural seismic | 0 rows = 0 findings | valid archive, 0 topics |
| AC20-FZK-Haus architecture (pass 2) | 77 rows = 77 findings | 233 entries, 77 topics + viewpoints |
| wbdg_office_arc architecture (pass 2) | 1 304 rows = 1 304 findings | 3 914 entries, 1 304 topics + viewpoints |

JSON parsed in every case. Row and topic counts match finding counts exactly —
at 34 156 findings that is a meaningful check of the export path.

## 4. Performance baseline

| File | Size | Cold | Cached | Speedup |
| --- | --- | --- | --- | --- |
| west_riverside_fire_ifc4 | 0.86 MB | 2.97 s | 0.08 s | 38x |
| west_riverside_plumb_ifc4 | 22.66 MB | 31.00 s | 0.76 s | 41x |
| Clinic_Plumbing | 53.25 MB | 33.33 s | 0.60 s | 55x |
| west_riverside_mech_ifc4 | 69.66 MB | 104.82 s | 1.55 s | 67x |

Cold time tracks element count and geometry work, not file size — the 53 MB
model is faster than the 23 MB one. The largest model finishes in 105 s,
inside the 120 s the plan expected. Cached runs are consistently under 2 s.

## 5. Pass 2 — the same models against a seeded database

**41 checks: 41 PASS, 0 FAIL, 3 WARN.** Same code, same models; the only change
is that `static_data_assets` holds the rule packs the seed migration installs.

### Architecture now runs on all five models

51 rules load (the 47 packaged ones plus the 4 hardcoded). Two columns of
findings are given because the same model does not always return the same
number — see finding 8.

| Model | MB | Findings (first run) | High | Medium | Rules fired | Findings (pass 2) | Time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AC20-FZK-Haus | 2.5 | 77 | 30 | 47 | 5 of 51 | 77 | 8.3 s |
| wbdg_office_arc | 3.9 | 1 306 | 1 104 | 202 | 11 of 51 | 1 304 | 19.2 s |
| DigitalHub_FM-ARC | 8.6 | 516 | 387 | 129 | 7 of 51 | 516 | 36.4 s |
| Clinic_Architectural | 12.4 | 2 917 | 2 373 | 544 | 10 of 51 | 2 847 | 46.4 s |
| wr_arc_ifc4 | 77.2 | 3 585 | 3 143 | 442 | 8 of 51 | 3 585 | 133.8 s |

Findings carry real values (`200.0 mm < required 860.0 mm`), real citations and
real positions, and every export matched: 77 findings → 77 CSV rows and 77 BCF
topics; 3 585 findings → 3 585 topics with viewpoints.

### Piping loses an engine

Every piping model returned the same counts as pass 1 for CC-001, MC-001,
MM-001 and XM-001 — and **no `GC-001` key at all, on any of the 15 models**.
See finding 2.

### Seismic is unchanged

0 findings on all three structural models, exactly as in pass 1. The five
seeded `BIMGUARD-SB-001` rules are thresholds; the blocker is geometry
(finding 4), which no amount of seeding addresses.

## 6. Beyond the manifest

Two models were extracted from the dataset's zip bundles as extra robustness
probes:

| Model | Schema | Size | Result |
| --- | --- | --- | --- |
| SGD_BODO_Eng-HVAC-Plumbing | **IFC2X2_FINAL** (2005, DDS exporter) | 69.4 MB | **HTTP 400, clean refusal**: "The file could not be read as IFC: Unsupported schema: IFC2X2_FINAL" |
| Autodesk-Research_210-King | IFC2X3 | **148.0 MB** | **200 in 43.6 s** — 7 908 elements, 6 496 piping; CC 7 908, MC 7 908, MM 6 496, XM 461 |

The IFC2X2 refusal is correct behaviour, not a crash — the schema predates the
two the parser supports and it says so. The 148 MB model is twice the size of
anything in the manifest and analysed faster than the 69.7 MB one, confirming
that cost tracks element count rather than bytes.

(One cosmetic artefact: `ifcopenshell.file.__del__` raises an ignored `KeyError`
during garbage collection after a rejected parse. Library teardown noise, no
effect on the response.)

---

# Findings that need a decision

## Finding 1 — nothing in the running application seeds the Part 9 rule packs

`BUILDING-CODE-PART9` (31 rules) and `BUILDING-CODE-PART9-EXT` (16 rules) exist,
are well-formed, and evaluate correctly. **No code path in the running
application ever puts them into the rules table.**

- Startup calls `app.main._seed_library`, which runs `seed_engine_rulesets` and
  `seed_architectural_code_rules`. The second seeds **four hardcoded rules**
  (`CODE 9.9.10.1`, `9.9.4.1`, `9.7.2.3`, `9.10.9.14.PW`), not the packs.
- `seed_default_code_rulesets` is the function that loads the 47 packaged rules.
  Grepping the tree, **it has no caller** outside its own module; `/api/rules/seed`
  calls `seed_engine_rulesets` instead.

The consequences compound:

| Database state | Rules the Architecture theme loads | Findings |
| --- | --- | --- |
| No database at all (pass 1) | — | **HTTP 400**, `Missing static asset ruleset:BUILDING-CODE-PART9` on all 5 models |
| Migrated exactly as the app seeds it | **4** | **0** — every rule reports `values_missing` for every matched element |
| Migrated + packs seeded explicitly | **51** | findings on all 5 models (table below) |

So the "47 architectural rules" claim does not hold at runtime under either of
the first two states, and the middle row is the one a correctly migrated
production database actually produces: architecture runs and finds nothing.

**Fix**: call `seed_default_code_rulesets` from `_seed_library` (or add the packs
to `seed_engine_rulesets`' tuple). One line; the packs already work.

## Finding 2 — GC-001 goes silent when its catalog comes from the database

This is the most consequential result of the run. The same model, the same
code, the same elements — only the catalog source differs:

| Engine | Built-in fallback catalog | Database catalog |
| --- | --- | --- |
| GC-001 | 926 findings, **all Medium** | 926 assessments, **all Low** |
| CC-001 | 926 findings, all Medium | 926 findings, all Medium |
| MC-001 | 926 findings, all **High** | 926 findings, all **Critical** |

(Duplex_MEP, 926 elements, `include_low=True` so nothing is hidden.)

`app/services/analysis_runner.py` hardcodes `include_low=False` — the API never
exposes it — so Low findings are dropped before the caller sees them. With a
seeded database **GC-001 therefore reports nothing at all**, on every one of the
15 piping models: pass 2's counts carry no `GC-001` key anywhere.

The database catalog is the richer one, and it is meant to win: 20 galvanic
series entries against 8, 7 environment classes against 4, 10 mitigations
against 1, and a `scoring_model` with 4 weights where the fallback has none.
Which is to say the fallback's Medium verdicts are the ones produced by an
impoverished catalog, and the DB's Low is the considered answer — but a
galvanic engine that is structurally incapable of surfacing a finding is not
something to ship without a decision.

**Two things to decide**: whether GC-001's DB weights genuinely place these
couples at Low, and whether Low findings should reach the API at all when a
whole mechanism can vanish behind that filter.

## Finding 3 — no element in the dataset has a material any engine can resolve

MM-001 emitted **88 554 findings across the 15 piping models, and every single
one is `data_quality`** ("material not identified"). GC-001 assessed 88 563
elements over the same models — so essentially every piping element in the
dataset carries a material `normalise_material()` cannot map. Coverage is 0%,
not the 1.9% the plan assumed.

The four-step data-quality rule is doing exactly what it promises — MM-001
reports "not assessed" rather than a false all-clear. **But GC-001, CC-001 and
MC-001 do not**: for those same elements with those same unresolvable
materials, they returned confident banded verdicts on every model —
GC Medium, CC Medium, MC High, one per element. CC-001 has a data-quality path
and used it 167 times on wr_mech_ifc4, 197 on wr_mech_ifc2x3 and 9 on
Schependomlaan; material absence was not among the reasons it fired.

This matters for how the result is described. It is **not** accurate to say the
corrosion engines "handle missing material gracefully by emitting data-quality
findings" — only MM-001 and XM-001 do. GC/CC/MC score a corrosion risk band for
material they could not identify.

XM-001 does produce real cross-material verdicts where a network exists:
Clinic_HVAC gave 16 268 Medium couples alongside 507 data-quality ones.

## Finding 4 — seismic could not evaluate any element of any real model — FIXED

**Resolved in commit `7aa8cf0`.** What the run measured, and what changed,
is recorded below; the fix is described at the end of this finding.

- Three structural models (Clinic_Structural, wr_str_ifc4, wbdg_office_str):
  **0 findings**. They carry beams, columns and footings but no distribution
  services, so a clearance check has nothing to iterate.
- Both AISC geometry models: 0 findings, no crash.
- On an MEP model, which does have services: Duplex_MEP returned **427
  findings, every one `SB-001.DATA`**, `mechanism=data_quality`,
  `check=geometry_unavailable`, "SB-001 did not produce a result for this
  element". Not one clearance verdict.

Root cause, still present at `halo_volume_generator._local_vertices`: it reads
only `IfcTriangulatedFaceSet`, `IfcPolygonalFaceSet`, `IfcPolyline` and
`IfcExtrudedAreaSolid`. Real exports do not represent geometry that way —
counted directly, Duplex_MEP holds **942 `IfcMappedItem`, 14 `IfcFacetedBrep`,
62 `IfcExtrudedAreaSolid` and no `IfcTriangulatedFaceSet` at all**. A mapped
item hides its extrusion inside `MappingSource.MappedRepresentation`, so the
top-level scan never reaches it and `element_bbox_mm` returns None.

Seismic does at least report its own stats correctly — `data_quality: 427` —
which is the contrast that makes finding 6 a bug rather than a design choice.

Seeding the database does not touch this: the 5 seeded `BIMGUARD-SB-001` rules
are thresholds, and the blocker is geometry.

**Fix applied** (`7aa8cf0`): `_local_vertices` now walks representation items
recursively. `IfcMappedItem` resolves through its mapping source with the
vertices transformed by `get_mappeditem_transformation`; boundary
representations (`IfcFacetedBrep` and the rest of `IfcManifoldSolidBrep`,
`IfcFaceBasedSurfaceModel`, `IfcShellBasedSurfaceModel`) are read through their
faces; `IfcBooleanResult` takes its first operand, whose extent contains the
result. Swept solids are still reduced to their extrusion axis.

**After the fix**, all 926 `IfcDistributionElement` in Duplex_MEP resolve a
bounding box (median extent 35 mm), and seismic reports clearance instead of
data quality:

| Model | Before | After |
| --- | --- | --- |
| Duplex_MEP | 427 data-quality | **4 773 verdicts** — 39 critical, 151 high, 4 583 medium |
| wbdg_office_mep | 1 959 data-quality | **17 406 verdicts** — 131 critical, 1 018 high |
| Clinic_Plumbing | 10 data-quality | **12 245 verdicts** — 97 critical, 474 high |

Findings carry overlap volumes, percentages, EN 1998-1 / DIN 4149 citations and
mitigations. The structural models still return nothing, which is a dataset
property — they carry no distribution services — not a geometry one.

**Still open**: the counts are large because a 200 mm halo around densely
packed MEP catches most neighbours. Whether that threshold is right for these
models is a domain question this change does not settle; it only makes the
engine able to ask it. The identical geometry limitation also remains in
`module2_ifc_read/piping_producer._local_vertices`, which feeds the corrosion
network geometry — left alone deliberately, since changing it would move the
corrosion numbers reported above.

## Finding 5 — the schema twins are not the same model

Reported FAIL by the suite, and the assertion was right to fire, but the cause
is the dataset, not the parser:

| Pair | IFC4 | IFC2x3 | Difference |
| --- | --- | --- | --- |
| Plumbing | 8 539 | 9 013 | 474 `IfcFlowTerminal` present only in IFC2x3 |
| Mechanical | 17 424 | 18 488 | 1 064 `IfcFlowTerminal` present only in IFC2x3 |

Every count reconciles exactly, counted from the files directly: plumbing IFC4
holds 4 308 `IfcPipeSegment` + 4 231 `IfcPipeFitting` = 8 539; the IFC2x3 twin
holds exactly 4 308 `IfcFlowSegment` + 4 231 `IfcFlowFitting`, **plus** 474
`IfcFlowTerminal` the IFC4 export omits.

**Schema handling is verified equivalent** — the parser maps the IFC2x3 and
IFC4 entity families onto the same element set, to the entity. The findings
differ only because the IFC4 exports dropped their terminals, so the "identical
findings" expectation cannot hold for these particular files. Either the
assertion should compare the shared entity families, or the dataset needs true
twins.

## Finding 6 — architecture reports every risk band as zero

With the packs seeded, AC20-FZK-Haus returns 77 findings whose bands are 30
High and 47 Medium, and `issue_stats` reports
`{total: 77, critical: 0, high: 0, medium: 0, low: 0, data_quality: 0}`.

`app/modules/orchestrator.py` fills `issue_stats` only on the MEP branch; for
Architecture it stays `{}`, and `app/api/analyze.py::_format_result` then
defaults every band to 0 while deriving `total` from the finding count. Any UI
reading the stats block sees an all-zero severity breakdown over a non-zero
total. Small fix, wrong number on screen.

## Finding 7 — the unit suite needs a database it does not document needing

`uv run pytest tests/` on a machine with no Supabase: **29 failed, 762 passed,
5 skipped, 5 xfailed**. The failures trace to the same missing static assets —
`app.modules.orchestrator`, `code_seed_rules`, `code_extended_rules` and
`enhanced_orchestrator` all raise `ValueError: Missing static asset
ruleset:BUILDING-CODE-PART9` at import, and `test_imports` fails by name
because they are in neither the known-failure nor the regression registry.
Whatever the fix for finding 1 is, it should let these modules import.

## Finding 8 — architecture did not return the same answer twice — FIXED

The same model, the same server, four consecutive runs with `use_cache=false`:

| Run | Findings | `CODE 9.5.1.2` (IfcSpace ceiling height) |
| --- | --- | --- |
| 1 | 1 304 | 0 |
| 2 | **1 307** | **3** |
| 3 | 1 304 | 0 |
| 4 | 1 304 | 0 |

Between server boots the spread is wider: Clinic_Architectural returned 2 917
findings on one boot and 2 847 on another, the 70-finding difference being
`CODE 3.8.3.2` (accessible corridor width, `IfcSpace`) firing in one and not the
other. Both models parse the same element count (3 298) and load the same 51
rules in both cases, so the input is identical.

Every rule observed flipping targets `IfcSpace` on a numeric property
(`Height`, `Width`).

**Root cause, found and fixed in `3659bcf`** — the full investigation is in
`findings.txt`. `IFCGeometryExtractor._get_shape` cached tessellated shapes
under `id(element)`, the CPython address of an ifcopenshell wrapper.
ifcopenshell creates a fresh wrapper on every entity access and frees it when
the caller drops it, so those addresses are recycled: fetching
wbdg_office_arc's 99 spaces twice, 32 addresses were reused and **31 of them
came back pointing at a different space**. A cache hit therefore returned
another element's geometry, or a cached `None`. Only geometry-derived
properties were affected, which is why the flipping rules were all `IfcSpace`
measurements.

The cache is now keyed on the STEP entity id. After the fix, wbdg_office_arc
returns 1 304 findings on six consecutive runs with an identical rule-by-rule
breakdown, and Clinic_Architectural returns 2 847 both within a boot and across
a restart.

**The deterministic answer is the lower count, and it is the right one.** Every
space in wbdg_office_arc is at least 2 500 mm tall (median 2 500, max 9 757), so
none can violate the 1 950 mm bathroom-ceiling rule. The three `CODE 9.5.1.2`
findings that came and went were **false violations** produced by measuring a
space with another element's shape. The bug was inventing findings, not hiding
them — which makes it a correctness bug, not only a reproducibility one.

## Notes

- **craslabbim** (64 MB industrial) yielded no elements: it holds no service
  entities the parser collects. Recorded PASS because the gate held trivially.
- **The fire-protection model has no pipes.** `west_riverside_hospital_fire_ifc4`
  holds 861 `IfcDistributionControlElement` (fire-alarm devices) and zero pipe
  entities, yet GC/CC/MC banded all 861. `IfcDistributionElement` is
  deliberately in the parser's service map (an aluminium-on-steel cable tray is
  a real galvanic case) and control elements are an IFC subtype of it. Whether
  fire-alarm devices should draw corrosion verdicts is a domain question.
- **`element_count` in the analysis response is the finding count, not the
  element count.** It matched the total findings exactly on all 15 piping
  models (Duplex_MEP: 926 elements, `element_count` 3704 = four engines x 926).
  `app/api/analyze.py:142` falls back to `len(issues)` because the corrosion
  result carries no top-level `ifc_element_count`, though
  `phase_6b_parsing` computes one.
- **The dataset holds more than the 34 models the manifest names**: four zip
  bundles (`NBU_MedicalClinic`, `Academic_Autodesk`, `Autodesk_210-King`,
  `SGD_BODO`) contain 16 further IFC models, including a 207 MB MEP model and
  an `IFC2X2_FINAL` file from 2005. They are outside this run.

## Submission readiness

| Claim | Status |
| --- | --- |
| Piping gating across 15 models, all five engines user-selectable | **Verified** |
| Cache separation keyed on engine selection | **Verified** |
| Exports BCF/CSV/JSON | **Verified**, up to 34 156 findings |
| Schema robustness IFC2x3 / IFC4 | **Verified** — equivalent parsing; the twins differ in content (finding 5) |
| Schema refusal for IFC2X2 | **Verified** — clean 400, no crash |
| Performance baseline | **Established** — 105 s for 69.7 MB, 43.6 s for 148 MB, under 2 s cached |
| Piping corrosion, 5 engines | **Qualified** — GC-001 reports nothing against a seeded database (finding 2) |
| Material handling | **Qualified** — MM/XM report data quality honestly; GC/CC/MC band unidentified material as if known (finding 3) |
| Architecture, 47 rules | **Not as claimed** — the packs work, nothing seeds them; the app evaluates 4 (finding 1) |
| Architecture, reproducible output | **Fixed** — identical across 6 runs and a restart (finding 8) |
| Architecture risk bands | **No** — every band reports 0 (finding 6) |
| Seismic SB-001 | **Fixed** — reads mapped and boundary geometry; now returns clearance verdicts, thresholds need review (finding 4) |

**Ready for submission: CLOSER, NOT YET.** Findings 4 and 8 are fixed —
seismic reads real geometry and architecture is reproducible. The piping
pipeline was already validated at scale, and export, cache, gating and schema
behaviour is solid. What is left:

1. **Seed the Part 9 packs** (finding 1) — one line, and the 47-rule claim
   becomes true.
2. **Decide the GC-001 band question** (finding 2) — a galvanic engine that
   cannot surface a finding is worse than no engine, and the answer depends on
   whether the DB weights are right.
3. **Review the seismic clearance threshold** — SB-001 now evaluates, and a
   200 mm halo flags most neighbours in dense MEP. That number needs a domain
   decision before the counts mean anything.

Findings 3, 6 and 7 are honest-description and presentation issues that should
be fixed before the material-coverage story is written up: the dataset's
material coverage is **0%**, not 1.9%, and only two of the five engines say so.

## Reproducing this

```bash
git clone https://github.com/maicen/bimguard-test-models.git test-models
cd frontend && npm install && npm run build && cd ..

# Pass 1 — shipped default, no database
BIMGUARD_E2E_MODELS="$(python -c 'import json;print(json.dumps(json.load(open("e2e-models.json"))["models"]))')" \
  uv run python scripts/e2e_server.py --port 8010 &
uv run python scripts/e2e_suite.py --manifest e2e-models.json \
  --base-url http://127.0.0.1:8010 --out test-results.json

# Pass 2 — with the seed migration's rule packs resident
BIMGUARD_E2E_MODELS="$(python -c 'import json;print(json.dumps(json.load(open("e2e-models.json"))["models"]))')" \
  uv run python scripts/e2e_server.py --port 8011 --seed-code-rulesets &
uv run python scripts/e2e_suite.py --manifest e2e-models.json \
  --base-url http://127.0.0.1:8011 --only piping,architecture,seismic \
  --quick-piping --out test-results-seeded.json
```

Pass 1 takes roughly 50 minutes on 4 cores, pass 2 roughly 25. `test-results.json`
holds the machine record of both, plus the band profiles, the catalog
comparison and the reproducibility runs.
