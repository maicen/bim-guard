# BIM-Guard Validation Report

**Measured:** 2026-09-05
**Run baseline:** `3075f5b` — analysis path verified byte-identical at `756b938` (`git diff --name-only 3075f5b..756b938` touches no file under `app/` or `data/rulesets/`)
**Corpus:** `test-models/models/` — 34 IFC files, 807 MB, 21 × IFC2X3 + 13 × IFC4

Every figure in this report comes from a run of a script in `scripts/`, against real IFC
models, at the commit named above. Nothing is quoted from a prior document. Where an
earlier document states a different number, the difference is recorded in
§8 rather than silently corrected.

---

## 1. What was measured, and what that does and does not show

Three harnesses, each answering a different question:

| Harness | Question | Output |
| --- | --- | --- |
| `scripts/validation_engine_matrix.py` | What do the five engines produce on real models? | `docs/validation/data/engine-matrix.json` |
| `scripts/validation_mm001_controls.py` | Does MM-001 fire only where it should? | `docs/validation/data/mm001-controls.json` |
| `scripts/validate_bcf_corpus.py` | Do the exported BCF archives satisfy BCF 2.1? | `docs/validation/data/bcf-corpus.json` |

The corpus run measures *behaviour*, not correctness: it shows what the engines emit on
93,457 real piping elements, and it cannot show whether a given verdict is metallurgically
right. The controlled cases (§6) are what test correctness, because they hold every input
fixed but one. Read the two together — a corpus number alone says how much the tool says,
not whether it is worth listening to.

### Method note: one combined pass, not six solo passes

`scripts/batch_corrosion_runs.py` runs each engine a second time on its own to time it in
isolation, costing six analysis passes per model. The matrix harness instead parses once,
runs the five engines together once, and attributes each Issue back to its engine via
`Issue.mechanism`. The per-engine counts here are therefore *as-deployed* — what the
engines produce when they run together, which is how the product runs them.

Attribution was verified rather than assumed. GC-001 and CC-001 return identical counts on
every model, which looks like a bucketing bug. It is not: the two carry distinct mechanism
labels (`GC-001 galvanic`, `CC-001 crevice`) and distinct band splits — GC-001's 537
findings are *all* Low, CC-001's 537 are *all* Medium. Both are element-wise engines gated
on the same `material_unresolved` precondition, so they assess the same set and each emits
one verdict per assessable element.

Runs were executed single-threaded. An earlier attempt was discarded in full after two
copies of each script were found writing to shared output paths concurrently (see §8).

---

## 2. Corrections to the project's own documentation

This audit was run against HEAD, not against the continuation document, because that
document's structural claims are stale. Verified against source at the run baseline:

| Continuation doc claims | Actually at HEAD |
| --- | --- |
| `app/engines/bimguard_gc_corrosion_engine.py` | Absent. GC-001 is `app/engines/bimguard_galvanic_engine.py` |
| `app/engines/bimguard_mm_corrosion_engine.py` | Absent. MM-001 is a **comparator**: `app/modules/comparator/material_media.py` |
| `app/engines/bimguard_xm_corrosion_engine.py` | Absent. XM-001 is a **comparator**: `app/modules/comparator/cross_material.py` |
| `app.modules.module6_compliance` import path | Matches zero tracked files |
| "XM-001 returns 0 findings" | **False.** XM-001 returns 16,562 findings (§5) |

CC-001 and MC-001 are `bimguard_crevice_engine.py` and `bimguard_mic_engine.py`. Three of
the five compliance checks are engines under `app/engines/`; two are comparators under
`app/modules/comparator/`.

---

## 3. Corpus

34 IFC files, of which **21 carry piping** and 13 do not. The 13 are architectural,
structural and sculpture models; they are not failures. The corrosion engines correctly
have nothing to say about a model with no pipework, and the harness records them as
`skipped: no piping elements` rather than as zero-finding passes.

**Total piping elements: 93,457.** No model failed to parse or analyse.

---

## 4. Gate coverage — read the source split, not the headline

The headline coverage numbers are reproduced exactly. They are also the least informative
figures in this report, and are presented here with the splits that make them readable.

| Gate | Coverage | Read from the model | Inferred / defaulted | Unresolved |
| --- | --- | --- | --- | --- |
| Material | **33.88 %** | 1,780 (**1.9 %**) | 29,885 (32.0 %) | 61,792 |
| Environment | **100.0 %** | 0 from IFC; 783 from spatial names (0.8 %) | 92,674 defaulted (**99.2 %**) | 0 |
| Temperature | **32.07 %** | **0** | 29,968 (100 % of coverage) | 63,489 |

What these say plainly:

- **Material coverage is 33.88 %, but only 1.9 % of the corpus is a measurement.** The
  remaining 32.0 % is a design convention applied by system type. Both halves feed the same
  scoring, which is why the producer keeps them apart and stamps every element with its
  source and confidence.
- **Environment coverage is 100 % because almost all of it is a default.** 99.2 % of
  elements were assigned `T1_indoor_damp` because no atmospheric metadata exists in MEP
  models. This is a deliberate choice: mapping fluid service onto atmospheric class (e.g.
  potable → marine) would score indoor hospital plumbing at severity 1.00 and generate
  false positives at scale. `T1_indoor_damp` (severity 0.20) is the honest floor.
- **Temperature coverage is 32.07 % and is 100 % inference.** Not one element in 93,457
  carries an operating-temperature property in its IFC. Every temperature the engines
  scored on was deduced from system type.

Per-model coverage varies enormously — from 0 % material on six models to 91.91 % on the
sprinkler model — because it depends entirely on how the model was authored:

| Model | Piping | Material % | from IFC | inferred | Env % | Temp % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Clinic_Architectural.ifc | 102 | 9.80 | 0 | 10 | 100.0 | 9.80 |
| Clinic_Electrical.ifc | 2,089 | 0.00 | 0 | 0 | 100.0 | 0.00 |
| Clinic_HVAC.ifc | 3,704 | 13.39 | 496 | 0 | 100.0 | 0.00 |
| Clinic_Plumbing.ifc | 6,587 | 38.91 | 528 | 2,035 | 100.0 | 25.70 |
| west_riverside_hospital_elec_ifc4.ifc | 1,673 | 0.00 | 0 | 0 | 100.0 | 0.00 |
| west_riverside_hospital_fire_ifc4.ifc | 861 | 41.11 | 0 | 354 | 100.0 | 41.11 |
| west_riverside_hospital_mech_ifc4.ifc | 17,424 | 10.86 | 0 | 1,893 | 100.0 | 10.86 |
| west_riverside_hospital_plumb_ifc4.ifc | 8,539 | 58.27 | 0 | 4,976 | 100.0 | 58.27 |
| west_riverside_hospital_sprinkle_ifc4.ifc | 13,490 | 91.91 | 2 | 12,397 | 100.0 | 91.91 |
| DigitalHub_FM-HZG_v2.ifc | 1,795 | 0.00 | 0 | 0 | 100.0 | 0.00 |
| DigitalHub_FM-LFT_v2.ifc | 1,310 | 1.07 | 0 | 14 | 100.0 | 1.07 |
| DigitalHub_FM-SAN_v2.ifc | 1,010 | 0.00 | 0 | 0 | 100.0 | 0.00 |
| Duplex_Electrical_20121207.ifc | 99 | 3.03 | 0 | 3 | 100.0 | 3.03 |
| Duplex_MEP_20110907.ifc | 926 | 23.97 | 0 | 222 | 100.0 | 15.98 |
| Duplex_Plumbing_20121113.ifc | 498 | 43.98 | 46 | 173 | 100.0 | 31.53 |
| IFC_Schependomlaan.ifc | 73 | 17.81 | 13 | 0 | 100.0 | 0.00 |
| Molio_with_URIs.ifc | 48 | 0.00 | 0 | 0 | 100.0 | 0.00 |
| wbdg_office_arc.ifc | 31 | 0.00 | 0 | 0 | 100.0 | 0.00 |
| wbdg_office_mep.ifc | 5,697 | 26.12 | 695 | 793 | 100.0 | 22.92 |
| west_riverside_hospital_mech_ifc2x3.ifc | 18,488 | 10.25 | 0 | 1,895 | 100.0 | 10.25 |
| west_riverside_hospital_plumb_ifc2x3.ifc | 9,013 | 56.81 | 0 | 5,120 | 100.0 | 56.81 |

---

## 5. Engine matrix

All five engines, run together, `include_low=True`, over the 21 models carrying piping.
Cells are **findings / data-quality refusals**. A refusal is the engine declining to score
an element and saying which input was missing — it is not a detection, and is never
reported as a pass.

| Model | Piping | GC-001 | CC-001 | MC-001 | MM-001 | XM-001 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Clinic_Architectural.ifc | 102 | 522/286 | 522/286 | 0/808 | 10/92 | 0/0 |
| Clinic_Electrical.ifc | 2,089 | 0/2089 | 0/2089 | 0/2089 | 0/2089 | 0/0 |
| Clinic_HVAC.ifc | 3,704 | 0/3704 | 0/3704 | 0/3704 | 0/3704 | **16268**/507 |
| Clinic_Plumbing.ifc | 6,587 | 0/6587 | 0/6587 | 0/6587 | 0/4894 | 0/3066 |
| west_riverside_hospital_elec_ifc4.ifc | 1,673 | 0/1673 | 0/1673 | 0/1673 | 0/1673 | 0/0 |
| west_riverside_hospital_fire_ifc4.ifc | 861 | 0/861 | 0/861 | 0/861 | 354/507 | 0/0 |
| west_riverside_hospital_mech_ifc4.ifc | 17,424 | 0/17424 | 0/17424 | 0/17424 | 0/15531 | 0/3 |
| west_riverside_hospital_plumb_ifc4.ifc | 8,539 | 0/8539 | 0/8539 | 0/8539 | 0/3563 | 0/1 |
| west_riverside_hospital_sprinkle_ifc4.ifc | 13,490 | 2/13488 | 2/13488 | 0/13490 | **12397**/1091 | 4/4 |
| DigitalHub_FM-HZG_v2.ifc | 1,795 | 0/1795 | 0/1795 | 0/1795 | 0/1795 | 0/0 |
| DigitalHub_FM-LFT_v2.ifc | 1,310 | 0/1310 | 0/1310 | 0/1310 | 14/1296 | 0/28 |
| DigitalHub_FM-SAN_v2.ifc | 1,010 | 0/1010 | 0/1010 | 0/1010 | 0/1010 | 0/0 |
| Duplex_Electrical_20121207.ifc | 99 | 0/99 | 0/99 | 0/99 | 1/96 | 0/0 |
| Duplex_MEP_20110907.ifc | 926 | 0/926 | 0/926 | 0/926 | 1/778 | 0/160 |
| Duplex_Plumbing_20121113.ifc | 498 | 0/498 | 0/498 | 0/498 | 0/341 | 0/235 |
| IFC_Schependomlaan.ifc | 73 | 13/69 | 13/69 | 0/82 | 0/73 | 0/0 |
| Molio_with_URIs.ifc | 48 | 0/48 | 0/48 | 0/48 | 0/48 | 0/0 |
| wbdg_office_arc.ifc | 31 | 0/39 | 0/39 | 0/39 | 0/31 | 0/0 |
| wbdg_office_mep.ifc | 5,697 | 0/5697 | 0/5697 | 0/5697 | 292/4391 | 290/860 |
| west_riverside_hospital_mech_ifc2x3.ifc | 18,488 | 0/18488 | 0/18488 | 0/18488 | 0/16593 | 0/4 |
| west_riverside_hospital_plumb_ifc2x3.ifc | 9,013 | 0/9013 | 0/9013 | 0/9013 | 0/3893 | 0/50 |

### Corpus totals

| Engine | Findings | Excluding Low | Data-quality refusals | Dominant refusal reason |
| --- | ---: | ---: | ---: | --- |
| GC-001 galvanic | 537 | **0** | 93,643 | `material_unresolved` |
| CC-001 crevice | 537 | 537 | 93,643 | `material_unresolved` |
| MC-001 microbiological | **0** | 0 | 94,180 | `hydraulics_unavailable` |
| MM-001 material-media | **13,069** | 13,069 | 63,489 | `material_normalisation` (61,792), `unmapped_pairing` (1,697) |
| XM-001 cross-material | **16,562** | 16,562 | 4,918 | `material_not_in_series` |

Total Issues emitted: **380,578** (findings + refusals; reconciles exactly with the
per-engine rows and with the BCF topic count in §7).

Three results deserve to be stated plainly rather than averaged away:

**GC-001 emits 537 findings, all of them Low band.** At the product default
(`include_low=False`) GC-001 produces **zero** findings on this corpus. The engine runs, is
exercised by its unit tests and validates its demo BCF — but on these 21 real models it
finds nothing a user would see.

**MC-001 emits zero findings on every model.** All 94,180 elements are refused with
`hydraulics_unavailable`: MC-001 needs flow velocity and dead-leg data, and no model in the
corpus carries it. The refusal is the correct behaviour — a microbiological verdict without
hydraulic data would be fabricated — but MC-001's real-model contribution is currently nil.

**XM-001 fires, and fires hardest of the five.** See below.

### XM-001 — the open question, resolved

XM-001 was recorded in project documentation as returning 0 findings and as "implementation
deferred". Measured: **16,562 findings, all Medium band**, concentrated in three models.

| Model | XM-001 findings | Material from IFC | Material inferred |
| --- | ---: | ---: | ---: |
| Clinic_HVAC.ifc | 16,268 | 496 | 0 |
| wbdg_office_mep.ifc | 290 | 695 | 793 |
| west_riverside_hospital_sprinkle_ifc4.ifc | 4 | 2 | 12,397 |

The mechanism predicted in the architecture notes is confirmed, but the conclusion drawn
from it was wrong. XM-001 needs *dissimilar* materials meeting at a junction, and
system-type inference assigns one material per system — so inferred materials cannot
produce a couple. The measured firing rate tracks the **from-IFC** column, not the inferred
one, almost perfectly: Clinic_HVAC carries 496 genuinely-authored materials and 0 inferred,
and yields 16,268 findings; the sprinkler model carries 2 authored materials against 12,397
inferred, and yields 4.

So XM-001 is implemented, functional, and gated by material provenance rather than by any
code gap. Its low yield on inference-dominated models is a property of the input data. Its
16,268 findings on a single genuinely-authored model show what it does when the data is
there.

One caution against reading 16,562 as 16,562 distinct defects: XM-001 scores *pairs*, so on
a densely-connected model the count grows with junction count, not with element count.
Clinic_HVAC's 16,268 findings arise from 3,704 elements. The number is a pair count and
should be reported as such.

---

## 6. MM-001 controlled cases — 12/12

`uv run python scripts/validation_mm001_controls.py` — exit 0. Each case holds three of the
four MM-001 inputs fixed and moves one, so every verdict has a single cause. Expectations
are asserted; the script exits non-zero if the engine disagrees.

| Case | Material / medium | °C | Expected | Actual | Band | Score |
| --- | --- | ---: | --- | --- | --- | ---: |
| POS-1 | GalvanisedSteel / stagnant_water | 20 | finding | finding | medium | 0.400 |
| POS-2 | GalvanisedSteel / hot_water | 60 | finding | finding | medium | 0.550 |
| POS-3 | GalvanisedSteel / pool_water | 27 | finding | finding | high | 0.747 |
| NEG-1 | Copper_C12200 / cold_water (potable) | 12 | silent | silent | — | — |
| NEG-2 | Copper_C12200 / hot_water | 60 | silent | silent | — | — |
| NEG-3 | Copper_C12200 / chilled_water | 6 | silent | silent | — | — |
| NEG-4 | PVC / cold_water | 12 | silent | silent | — | — |
| REF-1 | material not identified | 12 | refusal | refusal | — | — |
| REF-2 | environment unclassified | 20 | refusal | refusal | — | — |
| REF-3 | operating temperature missing | — | refusal | refusal | — | — |
| REF-4 | Titanium / oxygen (unmapped cell) | 20 | refusal | refusal | — | — |
| REF-5 | PVC / foul_water (unmapped medium) | 20 | refusal | refusal | — | — |

"Silent" means the engine produced nothing at all — not a Low-band finding, not a refusal.

**NEG-2 is the load-bearing case.** 60 °C is mandated by HSE HSG274 for Legionella control
and is required by MC-001 in this same codebase. Copper at 60 °C stays silent only because
the rule pack's `kinetics_guard` caps the temperature term at 0.35 for cells below 0.35.
Without the guard, the environment and temperature terms alone score 0.39 — Medium — and
the tool would flag what its own microbiological engine mandates. The guard is what keeps
MM-001 from contradicting MC-001.

**Corpus corroboration.** The controls say galvanised-in-stagnant should fire and
copper-in-potable should not. The corpus agrees without being asked to: of 13,069 MM-001
findings across 21 real models, **13,068 are `GalvanisedSteel / stagnant_water`** and 1 is
`CarbonSteel / hot_water`. Not one finding is copper in any medium. The textbook
zinc-depletion failure mode is essentially the entire MM-001 yield, which is what a correct
material-media check on this corpus should look like.

---

## 7. BCF 2.1 schema validation

Validated part-by-part against the buildingSMART BCF 2.1 `markup.xsd` and `visinfo.xsd`
vendored at `tests/schemas/bcf21/`.

### Archives generated at the run baseline

| Source | Archives valid | Topics |
| --- | --- | ---: |
| Corpus run, one archive per analysed model (`validation_engine_matrix.py`) | **21 / 21** | 380,578 |
| Engine demo archives, regenerated (`regenerate_demo_bcf.py`, exit 0) | **3 / 3** | 20 |

Every archive this codebase produced during validation — 21 from real models carrying up to
72,061 topics each, plus the three engine demos — validates cleanly. This is the load-bearing
BCF result.

<!-- BCF_CORPUS_SECTION -->

### Determinism check

Regenerating the three engine demo archives two days after their committed versions produced
asset-register CSVs that differ **only** in the `AssessmentDate` timestamp. Every score,
band, mitigation list and citation is byte-identical. The engines are deterministic across
runs.

---

## 8. Limitations and discrepancies

Stated rather than omitted; a bounded claim is worth more than an unbounded one.

**MM-001 reaches 8 of 24 piping systems.** The compatibility matrix carries eight media —
`cold_water`, `hot_water`, `chilled_water`, `condenser_water`, `pool_water`, `steam`,
`condensate`, `stagnant_water`. The remaining `PipingSystem` values — foul drainage,
rainwater, medical gases (oxygen, nitrous, vacuum, compressed air), natural gas, pool
chemical dosing — map to media with no cell, so those elements can only ever produce an
`unmapped_pairing` refusal (1,697 in this corpus). Refusing is the honest behaviour, but it
bounds MM-001's reach and no amount of better IFC authoring would extend it. Only a larger
matrix would.

**MC-001 contributes nothing on real models.** Zero findings, 94,180 refusals, all
`hydraulics_unavailable`. Until flow-velocity and dead-leg data reach the producer, MC-001
is exercised only by its unit tests and its synthetic demo.

**GC-001 contributes nothing at the product default.** All 537 findings band Low, so a user
running with `include_low=False` sees none of them.

**Temperature is entirely inferred.** Zero elements of 93,457 carry an IFC operating
temperature. Every temperature-dependent verdict in this report rests on a system-type
design convention, not on a reading of the model.

**XM-001's yield is a pair count**, not a defect count, and is concentrated in one model
(16,268 of 16,562).

**Discrepancies against earlier documents:**

| Claim elsewhere | Measured here |
| --- | --- |
| "XM-001 returns 0 findings" / "implementation deferred" | 16,562 findings; implemented and functional |
| "138 BCF test archives valid against XSD" | Not reproducible. See §7 for the actual corpus count |
| "MM-001 13,069 findings" | **Confirmed exactly**: 13,069 |
| "material 33.9 % / environment 100 % / temperature 32.1 %" | **Confirmed**: 33.88 % / 100.0 % / 32.07 % |
| `material-coverage.json` reporting 30.09 % over 56,509 elements | Different corpus (`data/test_models`, not `test-models/models`). Not a regression |

**A measurement discarded.** An earlier run of this matrix was thrown away in full. Two
copies of each harness — one orphaned from a prior session, one current — ran concurrently
against the same log and JSON paths, interleaving their writes. The corrupted log attributed
the sprinkler model's 13,490 piping elements to Clinic_Plumbing, which actually has 6,587,
and inflated its issue count from 27,721 to 53,966. The contention also tripled parse times
(Clinic_HVAC: 53.84 s contended vs 10.94 s clean). Every figure in this report comes from
the single-threaded re-run. On Windows, `uv run` spawns a grandchild Python that does not
die with its parent shell, so a stopped background task can leave a live writer behind;
harness runs should use session-scoped output paths, and only one should run at a time.

---

## 9. Reproducing this report

```bash
# Engine matrix over the full corpus (~10 min single-threaded)
uv run python scripts/validation_engine_matrix.py \
    --models test-models/models \
    --json docs/validation/data/engine-matrix.json

# MM-001 controlled cases (seconds; exit 0 == all cases behaved as specified)
uv run python scripts/validation_mm001_controls.py \
    --json docs/validation/data/mm001-controls.json

# BCF corpus validation
uv run python scripts/validate_bcf_corpus.py \
    --json docs/validation/data/bcf-corpus.json

# Engine demo archives: regenerate and validate
uv run python scripts/regenerate_demo_bcf.py --sweep
```

Run them one at a time. Total wall-clock for the corpus run at the baseline commit was
298.0 s parsing and 319.4 s analysis across 21 models.
