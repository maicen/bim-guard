# Seismic federated runs, coverage tracers and a measured model manifest — September 2026

Scope: SB-001 (Blue Halo) seismic clearance run federated and single-model per
building; the four material/environment/temperature coverage tracers; and a
measured replacement for the fabricated figures in `data/models-manifest.json`.

This report covers **seismic and coverage only**. It does not touch the
corrosion half of the September batch, whose numbers are under review.

Everything below was measured on 2026-09-05 against the 15 IFC models present in
`data/test_models/`. No number here is copied from upstream metadata.

- Machine record: [`data/seismic-federated-2026-09.json`](data/seismic-federated-2026-09.json)
- Archives: `docs/bcf_exports/seismic-2026-09/<building>/<run>/` (gitignored, not committed)

---

## 1. Seismic — SB-001 Blue Halo, federated vs control

Four buildings have more than one discipline model on disk. Three were named for
this trial; **digitalhub is a fourth that meets the same test** and is reported
separately in §1.5.

Every run used `angle_iron` bracing, seismic zone on, and the shipped
jurisdiction config `data/rulesets/config_en_1998_1_din_4149.json`
(EN 1998-1:2020 + DIN 4149:2022, 200 mm base clearance, 63 mm pipe threshold).

### 1.1 Federated runs

| Building | Primary (MEP) | Federated with | Elements | In-class | **Braced (in scope)** | Below threshold | Unmeasurable | Clashes | Crit | High | Med | Low | Cross-model | geometry_unavailable | Dedup'd | Wall clock |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| clinic | `Clinic_Plumbing.ifc` | HVAC, Structural | 11,376 | 4,441 | **2,219** | 2,222 | 0 | 4,533 | 53 | 847 | 3,633 | 0 | 796 | 0 | 0 | 378.4 s |
| west-riverside | `west_riverside_hospital_mech_ifc4.ifc` | plumb 2x3, plumb ifc4, str | 28,855 | 13,040 | **6,027** | 7,013 | 0 | 14,934 | 5,825 | 3,240 | 5,869 | 0 | 7,678 | 0 | 7,650 | 892.7 s |
| duplex | `Duplex_MEP_20110907.ifc` | A, Plumbing | 1,530 | 658 | **12** | 646 | 0 | 85 | 0 | 13 | 72 | 0 | 17 | 0 | 159 | 55.6 s |
| **Total** | | | | | **8,258** | | 0 | **19,552** | **5,878** | **4,100** | **9,574** | **0** | **8,491** | **0** | | 1,326.7 s |

No federated run returned 0, so the "show the in-scope braced count before
reporting a 0" condition does not arise. It is shown anyway: in-scope braced
elements are 2,219 / 6,027 / 12, all > 0.

### 1.2 Control runs (each model alone, no `--auto-extra`)

| Building | Model | Elements | In-class | Braced | Below threshold | Unmeasurable | Clashes | Crit | High | Med | geometry_unavailable | Wall clock |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| clinic | `Clinic_HVAC.ifc` | 3,704 | 1,548 | 1,543 | 5 | 0 | 1,806 | 19 | 617 | 1,170 | 0 | 47.2 s |
| clinic | `Clinic_Plumbing.ifc` | 6,587 | 2,893 | 676 | 2,217 | 0 | 1,931 | 29 | 38 | 1,864 | 0 | 282.5 s |
| clinic | **`Clinic_Structural.ifc`** | 1,085 | **0** | **0** | 0 | 0 | **0** | 0 | 0 | 0 | 0 | 12.5 s |
| west-riverside | `..._mech_ifc4.ifc` | 16,837 | 8,732 | 5,238 | 3,494 | 0 | 4,853 | 183 | 1,601 | 3,069 | 0 | 225.7 s |
| west-riverside | `..._plumb_ifc2x3.ifc` | 9,121 | 4,308 | 789 | 3,519 | 0 | 2,403 | 66 | 233 | 2,104 | 0 | 179.9 s |
| west-riverside | `..._plumb_ifc4.ifc` | 7,650 | 4,308 | 789 | 3,519 | 0 | 2,051 | 66 | 233 | 1,752 | 0 | 350.1 s |
| west-riverside | **`..._str_ifc4.ifc`** | 2,897 | **0** | **0** | 0 | 0 | **0** | 0 | 0 | 0 | 0 | 10.7 s |
| duplex | **`Duplex_A_20110907.ifc`** | 265 | **0** | **0** | 0 | 0 | **0** | 0 | 0 | 0 | 0 | 1.4 s |
| duplex | `Duplex_MEP_20110907.ifc` | 926 | 427 | 12 | 415 | 0 | 68 | 0 | 4 | 64 | 0 | 20.8 s |
| duplex | `Duplex_Plumbing_20121113.ifc` | 498 | 231 | **0** | 231 | 0 | **0** | 0 | 0 | 0 | 0 | 33.9 s |

**Both expectations hold.** Every structural/architectural-only control returned
exactly 0 clashes from 0 in-class elements (`Clinic_Structural`,
`west_riverside_hospital_str_ifc4`, `Duplex_A`). And every federated run found
MEP-vs-structure clashes that no control could see (§1.3).

`Duplex_Plumbing_20121113.ifc` also returns 0, for a different and important
reason: it has 231 in-class elements but **all 231 fall below the 63 mm bracing
threshold**, so it generates no halo. It still participates in the federated run
as a clash *target* (5 clashes), never as a source.

### 1.3 Cross-model pairs (source_model → clashing_source_model)

| Building | Source model | Clashing model | Clashes |
|---|---|---|---|
| clinic | `Clinic_Plumbing.ifc` | `Clinic_Plumbing.ifc` | 1,931 |
| clinic | `Clinic_HVAC.ifc` | `Clinic_HVAC.ifc` | 1,806 |
| clinic | `Clinic_HVAC.ifc` | **`Clinic_Structural.ifc`** | **521** |
| clinic | `Clinic_Plumbing.ifc` | **`Clinic_Structural.ifc`** | **121** |
| clinic | `Clinic_HVAC.ifc` | `Clinic_Plumbing.ifc` | 80 |
| clinic | `Clinic_Plumbing.ifc` | `Clinic_HVAC.ifc` | 74 |
| west-riverside | `..._mech_ifc4.ifc` | **`..._str_ifc4.ifc`** | **6,761** |
| west-riverside | `..._mech_ifc4.ifc` | `..._mech_ifc4.ifc` | 4,853 |
| west-riverside | `..._plumb_ifc2x3.ifc` | `..._plumb_ifc2x3.ifc` | 2,403 |
| west-riverside | `..._plumb_ifc2x3.ifc` | **`..._str_ifc4.ifc`** | **886** |
| west-riverside | `..._mech_ifc4.ifc` | `..._plumb_ifc2x3.ifc` | 27 |
| west-riverside | `..._plumb_ifc2x3.ifc` | `..._mech_ifc4.ifc` | 4 |
| duplex | `Duplex_MEP_20110907.ifc` | `Duplex_MEP_20110907.ifc` | 68 |
| duplex | `Duplex_MEP_20110907.ifc` | **`Duplex_A_20110907.ifc`** | **12** |
| duplex | `Duplex_MEP_20110907.ifc` | `Duplex_Plumbing_20121113.ifc` | 5 |

The engine labels the primary model `"primary model"` rather than by filename
(`phase_6d_seismic.py:64`, `PRIMARY_MODEL_LABEL`). The driver maps that label
back to the real filename before reporting, so every row above names a file.

### 1.4 Federation is exactly additive

Federated clashes decompose with no residue into the same-model clashes the
controls already found, plus the cross-model clashes only federation can see:

| Building | Σ controls (surviving models) | + cross-model | = federated | Actual |
|---|---|---|---|---|
| clinic | 1,931 + 1,806 + 0 = 3,737 | 796 | 4,533 | **4,533** ✓ |
| duplex | 68 + 0 + 0 = 68 | 17 | 85 | **85** ✓ |
| west-riverside | 4,853 + 2,403 = 7,256 | 7,678 | 14,934 | **14,934** ✓ |

West-riverside sums only two controls because `plumb_ifc4` contributes nothing —
see Anomaly A2. No same-model clash is lost or invented by federating.

### 1.5 digitalhub — the fourth qualifying building (beyond the named three)

| Run | Elements | In-class | Braced | Below | Unmeasurable | Clashes | Crit | High | Med | Cross | **geometry_unavailable** | Wall clock |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| federated (`FM-SAN` primary) | 4,139 | 2,013 | 595 | 2 | 1,416 | 549 | 41 | 320 | 188 | 2 | **1,416** | 16.8 s |
| control `FM-HZG_v2` | 1,795 | 914 | 0 | 2 | 912 | 0 | 0 | 0 | 0 | 0 | **912** | 3.8 s |
| control `FM-LFT_v2` | 1,310 | 595 | 595 | 0 | 0 | 547 | 41 | 320 | 186 | 0 | 0 | 3.2 s |
| control `FM-SAN_v2` | 1,034 | 504 | 0 | 0 | 504 | 0 | 0 | 0 | 0 | 0 | **504** | 12.5 s |

This is the **only** building in the corpus that exercises the
`geometry_unavailable` path, and it does so heavily: 1,416 of 2,013 in-class
elements (70%) have a bounding box with no thickness, so no diameter can be
estimated to test against the 63 mm threshold. They are reported as data-quality
findings rather than silently dropped, which is the documented behaviour
(`phase_6d_seismic.py:_bracing_scope`, `"unmeasurable"`). Its BCF archives carry
those 1,416 as topics — hence 1,965 topics against 549 clashes on the federated
run.

### 1.6 BCF archives

**13 archives checked for the three named buildings, 32,664 topics, 0
violations. 17 archives / 36,592 topics / 0 violations including digitalhub.**

Every `markup.bcf` and `viewpoint.bcfv` was validated against the vendored
buildingSMART BCF 2.1 schemas (`tests/schemas/bcf21/markup.xsd`,
`visinfo.xsd`), and `bcf.version` / `project.bcfp` presence was checked, using
`validate_archive` from `scripts/regenerate_demo_bcf.py`. That script's
`--validate-only` flag cannot target an arbitrary folder — it validates only the
three engine demo archives — so its validator was imported and called directly,
as anticipated.

Four archives contain 0 topics (`Clinic_Structural`, `..._str_ifc4`,
`Duplex_A`, `Duplex_Plumbing`). They are still well-formed BCF and still
validate; a 0-topic archive is the correct output for a run that raised nothing.

---

## 2. Coverage tracers

All four commands ran exactly as specified, with no deviation: `--models-dir`,
`--no-inference`, and `--json` all exist on the material and temperature
tracers, and `--models-dir` / `--json` on the environment tracer. (The
environment tracer's third flag is `--no-default`, not `--no-inference`; it was
not needed and was not used.)

| Model | Piping elems | **File-only material %** | Inferred material % | Env: ifc / spatial / default | Temperature % |
|---|---|---|---|---|---|
| `Clinic_HVAC.ifc` | 3,704 | 13.4% | 13.4% | 0 / 1 / 3,703 | 0.0% |
| `Clinic_Plumbing.ifc` | 6,587 | 8.0% | 38.9% | 0 / 0 / 6,587 | 25.7% |
| `DigitalHub_FM-HZG_v2.ifc` | 1,795 | 0.0% | 0.0% | 0 / 0 / 1,795 | 0.0% |
| `DigitalHub_FM-LFT_v2.ifc` | 1,310 | 0.0% | 1.1% | 0 / 0 / 1,310 | 1.1% |
| `DigitalHub_FM-SAN_v2.ifc` | 1,010 | 0.0% | 0.0% | 0 / 0 / 1,010 | 0.0% |
| `Duplex_MEP_20110907.ifc` | 926 | 0.0% | 24.0% | 0 / 1 / 925 | 16.0% |
| `Duplex_Plumbing_20121113.ifc` | 498 | 9.2% | 44.0% | 0 / 3 / 495 | 31.5% |
| `nfpa13_test.ifc` | 6 | 100.0% | 100.0% | 0 / 0 / 6 | 66.7% |
| `wbdg_office_mep.ifc` | 5,697 | 12.2% | 26.1% | 0 / 347 / 5,350 | 22.9% |
| `west_riverside_hospital_mech_ifc4.ifc` | 17,424 | 0.0% | 10.9% | 0 / 198 / 17,226 | 10.9% |
| `west_riverside_hospital_plumb_ifc2x3.ifc` | 9,013 | 0.0% | 56.9% | 0 / 0 / 9,013 | 56.8% |
| `west_riverside_hospital_plumb_ifc4.ifc` | 8,539 | 0.0% | 58.3% | 0 / 0 / 8,539 | 58.3% |
| **TOTAL** | **56,509** | **3.1%** | **30.1%** | **0 / 550 / 55,959** | **27.1%** |

**Environment source split: 0 from IFC, 550 from spatial names (1.0%), 55,959
from the T1 indoor default (99.0%).** The tracer reports 100% environment
coverage, and that figure is carried almost entirely by a blanket default, not
by anything read from a model. No model in the corpus carries a single
environment property the reader recognises.

**Temperature is 0.0% from IFC across all 56,509 elements.** Every one of the
15,308 resolved temperatures (27.1%) is inferred from the piping system; not one
is read from a file.

Material is the same shape: 3.1% read from file, rising to 30.1% only once
system-based inference is switched on — a 27-point gap that is assumption, not
measurement.

---

## 3. Measured model manifest

`data/models-manifest-measured.json` — written by
`scripts/measure_model_manifest.py`, covering all 15 models on disk.
`data/models-manifest.json` was **not** edited.

| Model | Schema | MB | sha256 (first 12) | PipeSeg | DuctSeg | CblCarrier | FlowSeg | DistElem | IfcMaterial | File-only mat % |
|---|---|---|---|---|---|---|---|---|---|---|
| `Clinic_HVAC.ifc` | IFC2X3 | 25.7 | `39c88a79f48f` | 0 | 0 | 0 | 1,548 | 0 | **0** | 13.4% |
| `Clinic_Plumbing.ifc` | IFC2X3 | 53.2 | `e662a8d02736` | 0 | 0 | 0 | 2,893 | 0 | 1 | 8.0% |
| `Clinic_Structural.ifc` | IFC2X3 | 18.2 | `325287b375f1` | 0 | 0 | 0 | 0 | 0 | 9 | n/a |
| `DigitalHub_FM-HZG_v2.ifc` | IFC4 | 19.9 | `a5603e8f6aa4` | 914 | 0 | 0 | 0 | 0 | 1 | 0.0% |
| `DigitalHub_FM-LFT_v2.ifc` | IFC4 | 12.1 | `c0a180787595` | 0 | 595 | 0 | 0 | 0 | 2 | 0.0% |
| `DigitalHub_FM-SAN_v2.ifc` | IFC4 | 24.0 | `0b1d6b0abd8d` | 504 | 0 | 0 | 0 | 0 | 1 | 0.0% |
| `Duplex_A_20110907.ifc` | IFC2X3 | 2.3 | `b347a2c8aa8f` | 0 | 0 | 0 | 0 | 0 | 18 | n/a |
| `Duplex_MEP_20110907.ifc` | IFC2X3 | 17.0 | `13976a8e223f` | 0 | 0 | 0 | 427 | 0 | **0** | 0.0% |
| `Duplex_Plumbing_20121113.ifc` | IFC2X3 | 30.1 | `abfaf5c0979b` | 0 | 0 | 0 | 231 | 0 | 3 | 9.2% |
| `nfpa13_test.ifc` | IFC4X3 | 0.0 | `43a4f8ae9d37` | 6 | 0 | 0 | 0 | 0 | 3 | 100.0% |
| `wbdg_office_mep.ifc` | IFC2X3 | 40.0 | `835263f1a9f8` | 0 | 0 | 0 | 1,959 | 0 | **0** | 12.2% |
| `west_riverside_hospital_mech_ifc4.ifc` | IFC4 | 69.7 | `04a29bc312fe` | 3,916 | 4,816 | 0 | 0 | 0 | 1 | 0.0% |
| `west_riverside_hospital_plumb_ifc2x3.ifc` | IFC2X3 | 23.8 | `5f3e24ed7082` | 0 | 0 | 0 | 4,308 | 0 | 7 | 0.0% |
| `west_riverside_hospital_plumb_ifc4.ifc` | IFC4 | 22.7 | `bb53f0eb8f72` | 4,308 | 0 | 0 | 0 | 0 | 7 | 0.0% |
| `west_riverside_hospital_str_ifc4.ifc` | IFC4 | 6.2 | `7eed88eb21da` | 0 | 0 | 0 | 0 | 0 | 7 | n/a |

Class counts are **exact type** (`entity.is_a() == class`), not
subtype-inclusive, because that is what the seismic engine keys on. A
subtype-inclusive count would report the same element three times, since
`IfcPipeSegment` and `IfcDuctSegment` are subtypes of `IfcFlowSegment`, which is
itself a subtype of `IfcDistributionElement`.

Two consequences fall straight out of this table:

- **Schema determines the class.** Every IFC2X3 model expresses piping as the
  generic `IfcFlowSegment`; every IFC4 model uses the specific `IfcPipeSegment`
  / `IfcDuctSegment`. Exact-type `IfcDistributionElement` is 0 in all 15 models.
- **The counts independently confirm the seismic scope.** `in_class` in §1.2
  equals the sum of the four braced classes here for every model —
  `Clinic_HVAC` 1,548; `Clinic_Plumbing` 2,893; `Duplex_MEP` 427;
  `Duplex_Plumbing` 231; `..._mech_ifc4` 3,916 + 4,816 = 8,732. Two independent
  readers agree.

`material_pct_file_only` and `IfcMaterial` count measure different things and
legitimately disagree — see Anomaly A3.

---

## Anomalies

**A1 — `--building-type` is inert under the shipped config.**
`clearance_rules.hospital_addition_mm` and `seismic_zone_addition_mm` are both
`0` in `data/rulesets/config_en_1998_1_din_4149.json:80-83`, and
`halo_volume_generator.py:245-247` adds exactly those. So
`--building-type hospital` and `--no-seismic-zone` change no clearance envelope
and no result. The config's own `data_gaps` says both figures were "left at 0mm
rather than guessed", so this is honest, but every run in this report used the
same 200 mm envelope regardless of the flag passed.

**A2 — `west_riverside_hospital_plumb_ifc2x3` and `_plumb_ifc4` are the same
building exported twice, and one is silently absorbed.**
Both carry 4,308 in-class elements with identical `GlobalId`s. In the federated
run, `federated_duplicates=7,650` — exactly the full element count of
`plumb_ifc4` — so **every one of its elements was deduplicated away** and it
contributed nothing: it appears in no cross-model pair in §1.3. The dedup is
correct and documented (`phase_6d_seismic.py:417-422`, "One element, one
envelope"), but the federated west-riverside run effectively covered three
models, not the four named on its command line.

Worse, the two exports do **not** agree when run alone: `plumb_ifc2x3` reports
9,121 elements and 2,403 clashes, `plumb_ifc4` reports 7,650 elements and 2,051
clashes — a 17% difference in findings for the same 4,308 braced elements of the
same building. The bracing scope is identical (4,308 in-class, 789 braced, 3,519
below threshold), so the difference is entirely in which *non-braced* elements
resolve to readable geometry and become clash candidates. Which schema you
export governs how many seismic findings you get.

**A3 — a model can hold zero `IfcMaterial` and still report non-zero file-only
material coverage.**
`Clinic_HVAC.ifc` has **0** `IfcMaterial` entities, **0** `IfcMaterialLayerSet`,
and **0** `IfcRelAssociatesMaterial` — verified directly — yet the file-only
tracer reports 13.4% (496 elements). This is not a defect: `resolve_material`
accepts a `Material`/`MaterialName` property-set value as a second file-borne
source and tags it `MATERIAL_SOURCE_IFC`
(`app/modules/ifc_reader/piping_producer.py:1201-1208`), and its docstring names
this exact model. Both numbers are readings of the file and neither is inferred,
but the pair looks self-contradictory unless the distinction is stated — so the
measured manifest and `data/test_models/README.md` both state it.

**A4 — the three coverage JSONs previously described a different, larger
corpus.** The committed versions were generated over `test-models\models`: 21
models and **93,457** piping elements. Re-running them at the paths specified
for this task points them at `data/test_models`: 15 models on disk, 12 with
piping, **56,509** elements. The percentages therefore moved for reasons that
have nothing to do with the reader:

| Tracer | Previous (21 models, 93,457 elems) | Now (data/test_models, 56,509 elems) |
|---|---|---|
| material (inference on) | 33.88% | 30.09% |
| temperature | 32.06% | 27.09% |
| environment | 100.0% (783 spatial / 92,674 default) | 100.0% (550 spatial / 55,959 default) |

**Percentages across this commit are not comparable.** The 6 upstream models
absent from `data/test_models` (`Clinic_Electrical`, `IFC_Schependomlaan`,
`Molio_with_URIs`, `..._elec_ifc4`, `..._fire_ifc4`, `..._sprinkle_ifc4`, etc.)
are gone from the record.

**A5 — the tracers silently omit models with no piping.**
`scripts/trace_material_coverage.py:57-58` returns `None` for a model with no
piping elements and `:114-115` skips it with no output line. Three of the 15
models on disk (`Clinic_Structural.ifc`, `Duplex_A_20110907.ifc`,
`west_riverside_hospital_str_ifc4.ifc`) never appear in any tracer table, and
nothing says so. They are correctly excluded — they are structural and
architectural models — but a reader counting rows sees 12 and has no way to know
15 were opened. The measured manifest lists all 15 with `n/a` for these.

**A6 — the config defines two `angle_*` variants and the engine silently takes
the first.** `rules_for(BraceType.ANGLE_IRON)` matches both `angle_fire` and
`angle_mechanical` (both start with `"angle"`,
`halo_volume_generator.py:96-100`), and `phase_6d_seismic.py:395` takes
`rules[0]` with no note. Harmless here — the two variants carry identical
spacing and clearance in this config — but a jurisdiction that distinguished
them would have one silently ignored.

**A7 — clash detection is brute-force, and it dominates runtime.**
`detect_halo_clash_against_geometry` tests every halo against every candidate
with no spatial index (its own docstring at `halo_volume_generator.py:907-911`
says the pre-filter is expected "upstream of this call"; nothing performs it),
and `phase_6d_seismic.py:494` rebuilds the full candidate list inside the
per-brace loop. The west-riverside federated run took 892.7 s for 6,027 braced
elements against 28,855 candidates. Total wall clock for the 17 runs here was
2,527.7 s. This is a scaling limit, not a wrong answer.

**A8 — same-model clashes dominate the control runs and are likely adjacency,
not defects.** `Clinic_HVAC` alone reports 1,806 clashes from 1,543 braced
ducts, and only the halo's own source element is excluded from its candidate
list (`halo_volume_generator.py:923`). Connected neighbouring segments of one
straight run therefore intrude on each other's 200 mm envelopes by construction.
This was not separately quantified and is flagged, not measured — the
cross-model counts in §1.3, which are the point of federating, are unaffected.

---

## Regenerating everything

```bash
# Task 1 — seismic, federated + controls (writes BCF under docs/bcf_exports/seismic-2026-09/
# and the machine record under docs/validation/data/). ~40 min total.
uv run python scripts/run_seismic_matrix.py                       # clinic, west-riverside, duplex
uv run python scripts/run_seismic_matrix.py --building digitalhub # the fourth qualifying building

# Task 2 — coverage tracers (exactly as specified; all four flags verified against argparse)
uv run python scripts/trace_material_coverage.py --models-dir data/test_models --json docs/validation/data/material-coverage.json
uv run python scripts/trace_material_coverage.py --models-dir data/test_models --no-inference --json docs/validation/data/material-coverage-file-only.json
uv run python scripts/trace_environment_coverage.py --models-dir data/test_models --json docs/validation/data/environment-coverage.json
uv run python scripts/trace_temperature_coverage.py --models-dir data/test_models --json docs/validation/data/temperature-coverage.json

# Task 3 — measured manifest (reads the file-only JSON produced above)
uv run python scripts/measure_model_manifest.py

# Re-validate every archive against the BCF 2.1 XSDs
uv run python -c "
import sys; sys.path.insert(0,'.')
from pathlib import Path
from scripts.regenerate_demo_bcf import _schemas, validate_archive
s = _schemas()
for p in sorted(Path('docs/bcf_exports/seismic-2026-09').rglob('*.bcfzip')):
    t, v = validate_archive(p, s)
    print('OK ' if not v else 'BAD', f'topics={t:6}', p.as_posix())
"
```

Missing models are fetched with
`uv run python scripts/fetch_test_model.py --set <clinic|west-riverside|duplex>`.

### Two deviations from the task as written, and why

1. **`scripts/run_seismic_matrix.py` is used instead of
   `run_full_pipeline.py --auto-extra`.** `--auto-extra` globs every other
   `.ifc` beside the model (`run_full_pipeline.py:_resolve_extras`), and all 15
   models sit in one flat directory, so it would federate four buildings into
   one run. The task's suggested fix — copying each building into
   `data/test_models/<building>/` — breaks Tasks 2 and 3 instead, because all
   three tracers use `rglob` (`trace_material_coverage.py:94`,
   `trace_environment_coverage.py:103`, `trace_temperature_coverage.py:117`)
   and would count every copied model twice. The driver passes extras
   explicitly, needs no copies, and reports the three metrics
   `run_full_pipeline.py` never prints. **Equivalence was verified**: staging
   duplex into `data/federated/duplex/` (gitignored) and running the literal
   command

   ```bash
   uv run python scripts/run_full_pipeline.py --model data/federated/duplex/Duplex_MEP_20110907.ifc --auto-extra --skip-galvanic --building-type standard
   ```

   returns **85 findings (0 critical, 13 high, 72 medium)** — identical to the
   driver's duplex federated row in §1.1.

2. **Two new scripts, not one.** `run_seismic_matrix.py` is the Task 1 driver.
   `measure_model_manifest.py` was added because Task 3 asks for a generated
   data file and Task 4 asks for the commands to regenerate it, which is not
   possible without a script. Neither file is owned by another session.

Archives were written directly into
`docs/bcf_exports/seismic-2026-09/<building>/<run>/` via `BCFExporter`'s
`export_dir` argument rather than written and then moved. `docs/bcf_exports/*`
is gitignored, so no archive is committed.
