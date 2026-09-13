# SB-001 provenance correction — 2026-09-13

Scope: the SB-001 (Blue Halo) seismic clearance ruleset,
`data/rulesets/sb001_seismic_clearance.json` (previously
`config_en_1998_1_din_4149.json`), schema 1.0.0 → 1.1.0. No engine logic,
scoring, banding or geometry code changed.

## 1. What was wrong

The ruleset presented itself as a combined profile of two European seismic
standards and attributed each of its thresholds to one or both of them. That
attribution was false in four ways.

1. **Both cited editions do not exist.** The configuration cited an EN 1998-1
   edition dated 2020 and a DIN 4149 edition dated 2022-03, with clause references
   to each. Neither edition has been published.
2. **The EN 1998-1 clause was from the wrong part of the standard.** The cited
   clause sat in Chapter 5 of EN 1998-1, which covers concrete buildings.
   Non-structural elements are addressed in §4.3.5.
3. **The numbers were not in either standard.** Every dimensional value — clearance
   from structure, transverse and longitudinal restraint spacing, pipe diameter
   threshold and brace angle range — was presented with a per-standard value
   (for example, 150 mm under EN 1998-1 and 200 mm under DIN 4149) and a "governing"
   merge rule. Neither EN 1998-1 nor the German National Annex dimensions MEP brace
   spacing, brace angles or clearance at all, so there were no per-standard values
   to merge.
4. **The hospital importance factor was a different quantity.** The configuration
   set Ip = 1.6 for hospitals. No component importance factor of 1.6 exists.

### Where the error came from

The values trace to `docs/validation/data/hermes_standards_research_summary.json`,
the output of an AI-assisted standards research pass ("Hermes"). That file lists,
for each standard, a year, a restraint spacing, a minimum clearance, a pipe
threshold, an angle range, an importance factor and a clause citation. None of
those entries carries a quotation or a page reference. The generator
(`app/modules/blue_halo/hermes_config_expanded.py`) parsed the free text, merged the
EN 1998-1 and DIN 4149 entries by a "more onerous governs" rule, and wrote the
result as the shipped configuration. The research entry for EN 1998-1 gave 1.5 for
critical facilities and the entry for DIN 4149 gave 1.6 for hospitals; the per-key
maximum rule selected 1.6. The configuration's own `data_gaps` list recorded that
several fields were missing or computed, but it did not question the fields that
were present, and nothing in the pipeline checked the research summary against the
standards it named.

The configuration therefore looked well documented — merge rules, data gaps, a
citation list — while the underlying values had no verified source. Recording
reasoning is not the same as recording evidence.

## 2. Evidence that the editions do not exist

The published edition history, as established on 2026-09-13:

- **EN 1998-1** (Eurocode 8, Part 1): EN 1998-1:2004, with corrigenda in 2009, 2011
  and 2013 and amendment A1:2013. The second-generation Eurocode 8 is being
  published in separate parts, including BS EN 1998-1-1:2024 and
  BS EN 1998-1-2:2026. There is no 2020 edition of EN 1998-1.
- **DIN 4149**: DIN 4149:2005-04 was withdrawn and replaced in Germany by
  DIN EN 1998-1:2010-12 with National Annex DIN EN 1998-1/NA:2011-01, updated
  as DIN EN 1998-1/NA:2018-10. There is no 2022 edition of DIN 4149.

These edition histories were not checked against the CEN or DIN catalogues from
inside this repository, which holds neither standard. A reader lifting this account
should confirm the edition list against the current catalogue at the time of use.

## 3. What FEMA E-74 does and does not evidence

Because neither Eurocode 8 nor the German National Annex gives MEP dimensional
rules, the one document on disk that does discuss them was read:
FEMA E-74, *Reducing the Risks of Nonstructural Earthquake Damage – A Practical
Guide*, 4th edition, December 2012 (885 pages, extractable text layer). E-74 is a
guide, not a code. For the actual requirements it defers to ASCE/SEI 7-10
Chapter 13 (§13.6 for distribution systems), NFPA 13 (2010) for sprinkler piping,
ASME B31 for pressure piping, and SMACNA's *Seismic Restraint Manual* (3rd ed.,
2009) among others.

Against the eleven SB-001 constants, E-74 gives:

| Constant | Current value | FEMA E-74 | Verdict |
| --- | --- | --- | --- |
| Transverse brace spacing | 1.0 m | 40 ft ductile / 20 ft nonductile pipe maximum (App. A §3.9.D.6–7, sample specification) | Sourced (piping), value differs |
| Longitudinal brace spacing | 1.5 m | 80 ft ductile / 40 ft nonductile pipe maximum (App. A §3.9.D.6) | Sourced (piping), value differs |
| Duct area threshold | null | 6 sq ft (§6.4.6.1; App. A §3.9.E.1) | Sourced |
| Importance factor, hospital / standard | 1.6 / 1.0 | 1.5 / 1.0 (§5.3.1, citing ASCE 7-10 §13.1.3) | Sourced, 1.6 is wrong |
| Clearance from structure | 200 mm | Only a ⅔-hanger-length rule for *unbraced* piping (App. A §3.9.D.9) | Partial |
| Pipe diameter threshold | 63 mm | ASCE 7-10 exemption "anywhere from 1- to 3-inch" by design category and occupancy (§6.4.3.1) | Partial |
| Hospital clearance addition | 0 mm | Stricter requirements for hospitals, no distance (§5.3.1) | Partial |
| Adjacent-system clearance | 0 mm | Interaction and tolerance verification, no distance (§2.2.4; App. A §1.8.D) | Partial |
| Brace angle minimum | 40° | None for pipe or duct | Not covered |
| Brace angle maximum | 65° | None for pipe or duct | Not covered |
| Seismic-zone clearance addition | 0 mm | Drift and joint rules only, no clearance addition | Not covered |

**FEMA E-74 evidences 4 of the 11 constants with a number, discusses 4 without a
number, and does not cover 3.** Of the four it evidences, three contradict
the values SB-001 used (1.0 m, 1.5 m, Ip 1.6) and one fills a null. E-74 is US
customary throughout; metric conversions in the configuration are BIMGUARD's.

## 4. The two value changes

**Hospital importance factor: 1.6 → 1.5.** FEMA E-74 §5.3.1 (printed pp. 5-8 to
5-9) and ASCE/SEI 7-10 §13.1.3 set Ip = 1.5 for designated seismic systems,
including critical components in Risk Category IV buildings, and 1.0 otherwise.
The 1.6 in the earlier source is most plausibly the coefficient in the upper bound
on component design force, 1.6·S_DS·Ip·Wp (E-74 p. 5-10) — a different quantity.

**Duct area threshold: null → 0.557 m².** FEMA E-74 §6.4.6.1 (printed p. 6-346)
exempts HVAC ducts under 6 sq ft cross-section (or under 17 lb/ft) where impact is
avoided or protected against, and its model specification (App. A §3.9.E.1)
requires bracing above 6 sq ft or for hazardous contents. 6 sq ft = 0.557 m²; the
conversion is ours.

**Effect on findings.** Neither field is read by any SB-001 code path at this
commit. `load_clearance_config` loads both into `ClearanceConfig`, but
`run_seismic_analysis` uses neither: clearance additions come from
`clearance_rules`, and ducts stay in scope unconditionally. No current finding
changes, and no test expectation moved because of either value. The changes matter
for any future code that consumes them and for anyone reading the configuration as
a statement of fact.

Two outputs do change, both textual: every seismic finding now cites
"FEMA E-74 (4th ed., December 2012)" and "ASCE/SEI 7-10 §13.6" instead of the
two standard names, and the jurisdiction label reads "BIMGUARD SB-001 screening
calibration (authored thresholds, not code values)". The ruleset stamp on every
finding moves from `BIMGUARD-SB-001 v1.0.0` to `v1.1.0`.

## 5. The re-label

Every other threshold keeps its value. What changed is what the configuration
claims about it. Each threshold now has a `provenance` block with a `status`:

- **sourced** — the value is stated in a document held, cited by section and page.
- **derived** — the value is arithmetic on other thresholds.
- **authored** — the value is BIMGUARD's own calibration; any related source is
  recorded as a reference, not as the origin.

| Threshold | Value | Status |
| --- | --- | --- |
| importance_factors.hospital | 1.5 | sourced |
| importance_factors.standard | 1.0 | sourced |
| thresholds.duct_area_sqm | 0.557 | sourced |
| brace_types.*.spacing_transverse_m | 1.0 | authored |
| brace_types.*.spacing_longitudinal_m | 1.5 | authored |
| clearance_rules.base_from_structure_mm (and brace_types.*.clearance_mm) | 200 | authored |
| thresholds.pipe_diameter_mm | 63 | authored |
| angle_constraints.min_degrees | 40 | authored |
| angle_constraints.max_degrees | 65 | authored |
| angle_constraints.ideal_degrees | 52.5 | derived |
| angle_constraints.tolerance_degrees | 12.5 | derived |
| clearance_rules.seismic_zone_addition_mm | 0 | authored |
| clearance_rules.hospital_addition_mm | 0 | authored |
| clearance_rules.adjacent_system_mm | 0 | authored |

The configuration's `provenance_summary` records **3 sourced, 2 derived, 9
authored** (14 blocks: the importance factor is one constant in the E-74 table
above but two blocks here). The brace angle datum is now stated explicitly as
degrees from horizontal.

Why keep the authored values rather than replace them with E-74's? Because they do
different jobs. E-74's spacing maxima come from a sample specification written to be
customised, for ductile piping, and they describe the most lenient installation a
contractor may build. SB-001 is a coordination-stage screen that asks whether a
model leaves room for bracing; a tighter value produces more candidate findings for
a human to review. Replacing 1.0 m with 12.19 m would be a change to the risk model,
which was out of scope. Labelling it honestly was not.

The governing codes are now named accurately in `metadata.governing_codes`:
EN 1998-1:2004+A1:2013 (§4.3.5) and DIN EN 1998-1/NA:2018-10, each recorded as
giving no MEP dimensional rules, with DIN 4149:2005-04 recorded as withdrawn.

## 6. Limitation statement (for the thesis)

BIMGUARD SB-001 is a screening tool. Its clearance, spacing, pipe-size and
brace-angle thresholds are authored calibration, not values stated by
EN 1998-1, its German National Annex, ASCE/SEI 7-10 or FEMA E-74. Three
parameters are sourced to FEMA E-74: the component importance factors and the duct
cross-section exemption threshold. SB-001 findings indicate where a model may not
leave room for seismic bracing; they are not a substitute for bracing design to
ASCE/SEI 7-10 §13.6 or EN 1998-1, which must be carried out by the responsible
engineer.

An earlier version of the ruleset attributed its thresholds to EN 1998-1 and
DIN 4149 editions that do not exist. The values originated in an unverified
AI-assisted research summary and were carried into the shipped configuration
without being checked against the standards named. The error was found by reading
the standards' edition histories and the one dimensional source held (FEMA E-74),
and corrected before any value was changed on the strength of it.

## 7. What this does not fix

- **Per-finding citations cannot yet carry per-threshold status.** The engine
  builds each finding's citation from `metadata.standards_cited` and the
  jurisdiction label. A finding does not say whether the clearance behind it is
  sourced or authored; the configuration does.
- **Historical records are unchanged.** Dated validation reports and audit exports
  under `docs/validation/`, the raw research summary under
  `docs/validation/data/`, and the generated NotebookLM corpora
  (`docs/bimguard_*_rules.md`) still quote the old citations as they were produced.
  They are records of what the system said at the time.
- **The Hermes research summary is unverified beyond this ruleset.** Its NFPA 13
  and ASCE 7-22 entries carry the same shape of uncited values. They are not loaded
  by SB-001, but they should not be used as a source.
- **The frozen demo figure is unaffected.** Project 1542's 2,937 seismic findings
  depend on clearance, spacing and diameter thresholds that did not change, and on
  two fields no code path reads. The count is not expected to move; it was not
  re-run.
