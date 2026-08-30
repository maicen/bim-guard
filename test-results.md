# BIMGUARD E2E Test Results

Date: 2026-08-30
Commit: d56e824 (+ this run)
Dataset: maicen/bimguard-test-models — 38 rows, 34 IFC files, 1.3 GB checked out
Harness: `scripts/e2e_server.py` + `scripts/e2e_suite.py`, manifest `e2e-models.json`
Machine record: `test-results.json`

## Summary

**88 checks: 76 PASS, 7 FAIL, 5 WARN, 0 SKIP.** ~90 analyses over real HTTP
against a live uvicorn server, roughly 50 minutes of compute.

| Category | Models | Result |
| --- | --- | --- |
| 1. Piping — engine gating | 15 | **PASS** — gate held on every model |
| 2. Piping — cache separation | 4 | **PASS** — 15x–60x speedup on hit |
| 3. Exports (BCF/CSV/JSON) | 5 | **PASS** — counts match findings exactly |
| 4. Seismic | 3 structural + 3 MEP | **RUNS, EVALUATES NOTHING** — see finding 1 |
| 5. Architecture | 5 | **BLOCKED** — rule pack needs a database |
| 6. Schema robustness | 2 twin pairs | **PASS on parsing** — see finding 2 |
| 7. Geometry robustness | 2 | Parsed without crashing, no findings |
| 8. Performance | 4 tiers | **PASS** — baseline below |

The three headline findings are in their own section; they matter more than the
counts.

## 1. Piping — engine gating (15 models, all PASS)

Every model got the three-way gate check; four also got single-engine and
empty-selection variants. Not one leaked an unselected engine.

| Model | Schema | MB | All five engines |
| --- | --- | --- | --- |
| Clinic_Plumbing | IFC2X3 | 53.2 | GC/CC/MC 6587 each, MM 6587, **XM 906** |
| Clinic_HVAC | IFC2X3 | 25.7 | GC/CC/MC 3704 each, MM 3704, **XM 16775** |
| wr_plumb_ifc4 | IFC4 | 22.7 | GC/CC/MC 8539 each, MM 8539, XM 0 |
| wr_mech_ifc4 | IFC4 | 69.7 | GC/CC/MC 17424 each, MM 17424, XM 0 |
| wr_sprinkler_ifc4 | IFC4 | 32.4 | GC/CC/MC 13490 each, MM 13490, **XM 5** |
| wr_plumb_ifc2x3 | IFC2X3 | 23.8 | GC/CC/MC 9013 each, MM 9013, XM 0 |
| wr_mech_ifc2x3 | IFC2X3 | 75.1 | GC/CC/MC 18488 each, MM 18488, XM 0 |
| Duplex_MEP | IFC2X3 | 17.0 | GC/CC/MC 926 each, MM 926, XM 0 |
| Duplex_Plumbing | IFC2X3 | 30.1 | GC/CC/MC 498 each, MM 498, **XM 74** |
| DigitalHub_HZG | IFC4 | 19.9 | GC/CC/MC 1795 each, MM 1795, XM 0 |
| DigitalHub_SAN | IFC4 | 24.0 | GC/CC/MC 1010 each, MM 1010, XM 0 |
| DigitalHub_LFT | IFC4 | 12.2 | GC/CC/MC 1310 each, MM 1310, XM 0 |
| wbdg_office_mep | IFC2X3 | 40.0 | GC/CC/MC 5697 each, MM 5697, **XM 830** |
| IFC_Schependomlaan | IFC2X3 | 47.0 | GC/CC/MC 82 each, MM 73, XM 0 |
| craslabbim | IFC2X3 | 64.4 | no elements extracted (see notes) |

XM-001 fires on five models — 906, 16775, 830, 74 and 5 couples — so the
cross-material comparator does produce verdicts on real data. It stays silent
where materials do not resolve (finding 3).

## 2. Cache separation (4 models, all PASS)

Miss, a different selection, then the original selection again: identical
findings, and the hit is dramatically faster.

| Model | Cold | Other selection | Cached hit |
| --- | --- | --- | --- |
| Clinic_Plumbing 53 MB | 42.7 s | 30.1 s | **1.77 s** |
| wr_plumb_ifc4 23 MB | 35.1 s | 19.2 s | **1.92 s** |
| DigitalHub_SAN 24 MB | 5.4 s | 0.09 s | 0.15 s |
| Duplex_MEP 17 MB | 5.1 s | 0.07 s | 0.12 s |

## 3. Exports (all PASS)

| Model | CSV | BCF |
| --- | --- | --- |
| wr_plumb_ifc4 | 34 156 rows = 34 156 findings | 102 470 entries, 34 156 topics + viewpoints |
| Clinic_Plumbing | 27 254 rows = 27 254 findings | 81 764 entries, 27 254 topics + viewpoints |
| Duplex_MEP | 3 704 rows = 3 704 findings | 11 114 entries, 3 704 topics + viewpoints |
| Clinic_Structural (seismic) | 0 rows = 0 findings | valid archive, 0 topics |

JSON parsed for every case. Row and topic counts match finding counts exactly —
at 34 156 findings, that is a meaningful check of the export path.

## 4. Performance baseline

| File | Size | Cold | Cached | Speedup |
| --- | --- | --- | --- | --- |
| west_riverside_fire_ifc4 | 0.86 MB | 2.0 s | 0.09 s | 23x |
| west_riverside_plumb_ifc4 | 22.7 MB | 37.6 s | 2.5 s | 15x |
| Clinic_Plumbing | 53.2 MB | 44.0 s | 0.73 s | 60x |
| west_riverside_mech_ifc4 | 69.7 MB | 164.7 s | 3.8 s | 43x |

Cold time is not linear in file size — it tracks element count and geometry
work. **The 69.7 MB model takes 165 s, not the <90 s the plan expected.** Cached
runs are consistently under 4 s.

---

# Findings that need a decision

## Finding 1 — seismic cannot evaluate any element of any real model

SB-001 runs, and reports honestly, but produces **no verdicts at all** on real
files:

- On the three structural models (Clinic_Structural, wr_str_ifc4,
  wbdg_office_str): **0 findings**. These carry beams, columns and footings but
  no distribution services, so there is nothing for a clearance check to iterate.
- On MEP models, which do have services: **100% data-quality**. Duplex_MEP 427,
  wbdg_office_mep 1959, Clinic_Plumbing 10 — every one `SB-001.DATA`, band low,
  `check=geometry_unavailable`, reason **"no readable geometry"**.

Root cause, traced to `halo_volume_generator._local_vertices`: it reads only
`IfcTriangulatedFaceSet`, `IfcPolygonalFaceSet`, `IfcPolyline` and
`IfcExtrudedAreaSolid`. Real exports do not represent geometry that way —
Duplex_MEP holds 942 `IfcMappedItem` and 14 `IfcFacetedBrep`; Clinic_Plumbing
holds 3703 `IfcMappedItem` and 708 `IfcFacetedBrep`. A mapped item hides its
extrusion inside `MappingSource.MappedRepresentation`, so the top-level scan
never reaches it and `element_bbox_mm` returns None for every element.

The engine's four findings on the tiny synthetic fixture came from a file whose
elements carry explicit coordinates. Nothing was wrong with that test; it simply
never exercised a real export.

**Fix sketch** (not applied — this changes engine behaviour and wants domain
review): resolve `IfcMappedItem` by recursing into its mapping source and
composing `MappingTarget`, and collect vertices from `IfcFacetedBrep` faces.
Both are contained additions to `_local_vertices`.

## Finding 2 — the schema twins are not the same model

Reported FAIL by the suite, and the assertion was right to fire, but the cause
is the dataset, not the parser:

| Pair | IFC4 | IFC2x3 | Difference |
| --- | --- | --- | --- |
| Plumbing | 8 539 | 9 013 | 474 `IfcFlowTerminal` present only in IFC2x3 |
| Mechanical | 17 424 | 18 488 | 1 064 `IfcFlowTerminal` present only in IFC2x3 |

Every count reconciles exactly. Plumbing IFC4: 4308 `IfcPipeSegment` + 4231
`IfcPipeFitting` = 8539; IFC2x3: the same 8539 as `IfcFlowSegment`/
`IfcFlowFitting`, **plus** 474 flow terminals the IFC4 export omits. Mechanical
IFC4: 4816 duct segments + 4740 duct fittings + 3916 pipe segments + 3490 pipe
fittings + 462 valves = 17 424; IFC2x3: the same 16 962 as flow segments and
fittings + 462 flow controllers + 1064 flow terminals = 18 488.

**So schema handling is verified equivalent.** The parser mapped IFC2x3
`IfcFlowSegment`/`IfcFlowFitting`/`IfcFlowController` and IFC4
`IfcPipeSegment`/`IfcDuctSegment`/`IfcValve` onto the same element set, to the
entity. The findings differ only because the IFC4 exports dropped their
terminals. The "identical findings" expectation cannot hold for these files.

## Finding 3 — MM-001 has no materials to work with

MM-001 returns one finding per element on every model, and on the models checked
they are all `data_quality`: *"material not identified"*. The dataset marks
`west_riverside_hospital_plumb_ifc4` as "Full" material data; the file actually
holds **7 `IfcMaterial` entities** for 8 539 pipes, attached through 245
`IfcMaterialList` containers, named `Porcelain,White`, `Porcelain, White`,
`Metal Polished`, `Default`, `Stainless Steel`, `Finishes - Interior -
Porcelain`, `Metal - Stainless Steel, Satin Plain`.

`normalise_material()` maps those to `Unknown`, and MM-001 reports "not
assessed" rather than a false all-clear — the four-step data-quality rule doing
its job. One nuance worth a decision: `_material_name` takes `materials[0]` from
a material list, so where a list pairs a finish with the pipe metal the finish
wins. Which member represents the pipe body is a domain call.

## Finding 4 — architecture still cannot run (unchanged)

All five architectural models return
`400 The architectural analysis could not be run: Missing static asset
ruleset:BUILDING-CODE-PART9`. The Part 9 ruleset is served from
`static_data_assets`, not the repository, so this needs Supabase credentials.
The **78 rules claim remains unverified**. The clean 400 (rather than the 500
stack trace this suite found last run) is the fix from commit caadeee.

## Notes

- **craslabbim** (64 MB industrial) yielded no elements at all: it holds no
  service entities the parser collects. Recorded PASS because the gate held
  trivially; it is really "nothing to analyse".
- **The fire-protection smoke model has no pipes.**
  `west_riverside_hospital_fire_ifc4.ifc` holds 861
  `IfcDistributionControlElement` (fire-alarm devices) and zero pipe entities,
  yet GC/CC/MC scored all 861 as medium/medium/high corrosion risk.
  `IfcDistributionElement` is deliberately in the parser's service map (an
  aluminium-on-steel cable tray is a real galvanic case) and control elements
  are an IFC subtype of it. Whether fire-alarm devices should draw corrosion
  verdicts is a domain question.
- GC/CC/MC ran on their built-in catalogs; their database rule overrides were
  not exercised, for the same missing-database reason as finding 4.
- The BCF assertion was corrected mid-run: one topic per finding, so zero
  findings must give zero topics. The two seismic export checks were re-run
  under the corrected rule and pass.

## Submission readiness

| Claim | Status |
| --- | --- |
| Piping gating across 15 models | **Verified** |
| Cache separation | **Verified** |
| Exports BCF/CSV/JSON | **Verified**, up to 34 156 findings |
| Schema robustness IFC2x3/IFC4 | **Verified** — equivalent parsing, twins differ in content |
| Performance baseline | **Established**; 69.7 MB takes 165 s, over the 90 s target |
| Geometry robustness | Both AISC files parsed without crashing; neither produced findings |
| Seismic analysis | **Not production-ready** — evaluates nothing on real exports (finding 1) |
| Architecture analysis | **Unverified** — needs a database |

**Ready for submission: NEEDS WORK.** Piping is genuinely validated at scale.
Seismic runs but cannot read real geometry, and architecture has still never
been executed.
