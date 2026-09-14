# GC-001, CC-001 and MC-001 provenance declaration — 2026-09-13

Scope: the galvanic (BIMGUARD-GC-001), crevice (BIMGUARD-CC-001) and
microbiologically influenced (BIMGUARD-MC-001) corrosion rulesets. No threshold,
weight, band cut-off, score or scoring logic changed. No applied migration was
edited. No value was checked against a source document in this session.

## 1. What was wrong

MM-001 and XM-001 have said since their approval that their numbers are authored
calibration and that each citation names the standard governing a mechanism, not
the page a digit was read from. GC-001, CC-001 and MC-001 carried the same kind of
numbers and cited standards in the same way, but said nothing of the sort. Their
code, their seeded payloads, the client documentation and the product UI presented
the citations as the source of the thresholds:

- the Piping Checks explainer told users they could "trace a result back to the
  page in the standard that justifies it";
- Q01 said the composite came "from published weightings" and that each finding
  "attaches the standard and clause the threshold came from";
- Q02 labelled the citation "The threshold's source, auditable";
- the glossary reference lines listed standards with no qualification;
- the GC-001 seeded payload records `"source": "NASA-STD-6012 Table 1"` against
  the voltage thresholds.

None of the cited documents is held by the project (§3), and none of the values
has been checked against one. The rulesets were generated with AI assistance from
NotebookLM prompts in April 2026; the rule-generation prompt is recorded at
`docs/RESOURCES.md:95-105` and asks for "approximate" voltage gaps from two
secondary sources. What the rulesets actually contain is a calibration authored
for BIMGUARD, organised under the standards that govern each mechanism. That is a
legitimate thing to ship. Presenting it as quoted standard values was not.

## 2. Where these rulesets live

Unlike MM-001 and XM-001, none of the three has a JSON file under
`data/rulesets/`. Their content exists in two places.

| Location | What it holds |
| --- | --- |
| `supabase/migrations/20260806180500_seed_static_data_assets.sql` | Seeded static-asset payloads: GC-001 at :583, CC-001 at :736, MC-001 at :918. Applied; not editable. |
| `app/services/corrosion_rule_catalog.py:125` (`_FALLBACK_RULESETS`) | Fallback tables served when the stored payload is missing or unreadable. |

`app/services/ruleset_seeder.py:84-86` maps the three `ruleset_id`s to payload
file names, and writes one `rules` row per class with
`source_text="Source: <citation>"`.

## 3. Citations and whether each document is held

"Held" means a copy of the cited document exists on disk. The search covered PDF,
DOCX and EPUB files by name across the drive, and tracked files in this repository.
It did not cover untracked caches inside the other worktrees, which were out of
bounds for this session. Nothing matched.

### GC-001 — `standards_referenced` (8)

| Citation | Held |
| --- | --- |
| NASA-STD-6012 | No |
| WorldStainless / Euro Inox (2025) | No |
| AUCSC Basic Corrosion Course (2024) | No |
| IMOA Design Manual, 4th Ed. | No |
| Prosoco Technical Note 104 | No |
| American Galvanizers Association (2023) | No. `docs/scraped_standards/corrosion_mil_std_889_galvanic.md` holds a scraped AGA web page on galvanised steel in contact with other metals. It is not the coating-life data cited. |
| ISO 19650 | No (information management, no corrosion values) |
| buildingSMART BCF 2.1 | Not a document of values (exchange format) |

MIL-STD-889B is held in part, as `data/reference/mil_std_889b_table_ii.json`, and
the engine reads it (`app/engines/bimguard_corrosion_engine.py:130,155`). The
GC-001 payload does not cite it, so it gives no provenance to any GC-001 payload
value.

### CC-001 — `standards_referenced` (9) plus field-level sources

| Citation | Held |
| --- | --- |
| EN ISO 15329:2007 | No |
| ASTM G48, Method B | No |
| CIRIA C692 | No |
| CIBSE Guide G | No |
| IMOA Design Manual, 4th Ed. | No |
| EN 1993-1-4 | No |
| BS 8539 | No |
| buildingSMART BCF 2.1 | Not a document of values |
| ISO 19650 | Not a document of values |
| Sandvik Corrosion Handbook (field source, migration :780) | No |
| Fontana & Greene (1967) (field source) | No |

### MC-001 — `standards_referenced` (11)

| Citation | Held |
| --- | --- |
| CIBSE TM13:2013 | No |
| HSE HSG274 Part 1 | No |
| HSE HSG274 Part 2 | No |
| HSE HSG274 Part 3 | No |
| BS 8552:2012 | No |
| ASTM G-187 | No — suspect, §5 |
| EN ISO 9308-1 | No |
| WHO Guidelines for Drinking-Water Quality, 4th Ed. (2011) | No |
| NACCE TPC 11 | No — suspect, §5 |
| NACE SP0198 | No |
| CIBSE Guide G | No |

## 4. Threshold counts and status

Status vocabulary follows SB-001 (`docs/planning/sb001_provenance_2026-09-13.md`
§5):

- **sourced** — stated in a held document, cited by section and page;
- **derived** — arithmetic on other values in the same ruleset;
- **authored** — BIMGUARD's own calibration.

The counts below were measured from the seeded payloads at origin/main 8cd6b22.
They count every numeric leaf in the payload, plus both ends of every numeric risk
band range. They exclude the pset schema, `ifc_data_sources`, the mitigation
catalogue and `ruleset_version`.

| Ruleset | Values | Sourced | Derived | Authored |
| --- | --- | --- | --- | --- |
| GC-001 | 79 | 0 | 10 | 69 |
| CC-001 | 60 | 0 | 5 | 55 |
| MC-001 | 69 structured, plus 27 embedded in threshold text | 0 | 0 | 96 (69 + 27) |

What the derived values are:

- **GC-001, 10 derived:** `common_mep_pairings[*].gap_v`, each equal to the
  absolute difference of the two materials' potentials in the ruleset's own
  galvanic series. All 10 reproduced exactly.
- **CC-001, 5 derived:** `high_risk_configurations[*].expected_score`, each
  reproduced by the ruleset's own weighted formula. All 5 reproduced.

The derivation is internal arithmetic. It makes those ten and five values
consistent with the rest of the ruleset; it does not give them any external
source.

**MC-001's 27 text-embedded numbers.** These are numbers written inside strings
rather than as JSON numbers: 7 in the dead-leg ratio bands (for example `"10–20"`),
12 in `high_risk_configurations`, and 8 in the temperature classes (for example
`"25–45°C"`). The engine parses the strings, so they are thresholds. They are
counted separately so the structured count is comparable across the three rulesets.

**Zero sourced, in all three.** A value can only be sourced against a document that
is held (§3), and none is. This does not mean the values are wrong. Some sit in
ranges commonly quoted in secondary literature, such as a 20–45 °C Legionella
growth range and a CCT ordering of 304 < 316 < 2205. But no value has been checked
against a source here, so agreement cannot be claimed.

## 5. The two suspect citations

Both appear in MC-001 and are recorded exactly as written. Neither was changed:
they are citation text, and removing them was out of scope.

### ASTM G-187

The MC-001 seeded payload names it itself as "ASTM G-187 — Standard Practice for
Measurement of Soil Resistivity" (migration :929). It then cites it for things
soil resistivity does not govern:

- flow-class reference: migration :961 (`"ASTM G-187 / NACCE TPC 11"`);
- material MIC susceptibility scores: migration :1013 (carbon steel), :1016
  (ss304), :1017 (ss316), :1018 (duplex 2205), :1022 (titanium, "exceptional MIC
  resistance").

The ruleset contradicts itself: by its own declaration the document measures soil
resistivity, and it is not a source for the MIC susceptibility of stainless or
titanium pipe in building water.

Live code that still carries the citation:

- `app/engines/bimguard_mic_engine.py:9` — module docstring; now annotated as
  suspect;
- `app/engines/bimguard_mic_engine.py:538` — BCF issue body, "ASTM G-187 — MIC
  Assessment Standard Practice";
- `app/modules/phase_6/phase_6c_corrosion_ui.py:399` — finding citation, standard
  "ASTM G-187", clause "MIC assessment standard practice";
- `app/services/ruleset_seeder.py:681` — `source_text` fallback reference.

The strings at `:538` and `:399` are emitted into findings and BCF output. They
were **not** changed, because changing them changes output and this session was
limited to declarations. They are the first thing to fix in the follow-up (§9).

### "NACCE TPC 11"

Recorded at migration :932 as "NACCE TPC 11 — MIC in Industrial Water Systems", and
cited at :961, :969, :977, :1013, :1014 and :1015. The corrosion body is NACE
International, now AMPP; "NACCE" is not its name. Whether a document with that
number and title exists under NACE has not been verified. As written, the citation
cannot be looked up.

It also appears at `app/engines/bimguard_mic_engine.py:15` (now annotated) and as
the default reference in `app/services/ruleset_seeder.py:681`.

## 6. What MM-001 and XM-001 already declare

MM-001, `data/rulesets/mm_001_material_media.json:34-47` (PROVENANCE_WARNING):

> The RANKINGS in this matrix reflect established corrosion-engineering consensus:
> which material/media pairings are benign and which are known failure modes.
>
> The NUMBERS - compatibility_score to two decimals and predicted_lifespan_years -
> are a calibration authored for this ruleset. They are NOT quoted from the cited
> standards. The citation on each cell identifies the standard that GOVERNS THAT
> MECHANISM, not a document from which the digit was read.
>
> A corrosion engineer must verify every cell against the cited source, and against
> project water chemistry, before this pack drives any compliance verdict.

And at `:20`: "The digits remain a calibration authored for this ruleset, not values
quoted from the cited standards. Citations name the standard governing each
mechanism."

XM-001, `data/rulesets/xm_001_cross_material.json:19`:

> As with MM-001: the separation, mitigation and normalisation values remain a
> calibration authored for this ruleset, not values quoted from the cited
> standards. Approval covers the convention and the structure, not the digits.

**XM-001 inherits GC-001's voltages.** XM-001 does not carry its own galvanic series
or voltage thresholds. It reads GC-001's at runtime, through the GC-001 engine
(`app/modules/phase_6/phase_6c_corrosion_ui.py:666-715`). XM-001's declaration
therefore covered its own separation and mitigation values, but the potentials and
voltage limits behind every XM-001 galvanic couple were GC-001 numbers, and GC-001
declared nothing. The GC-001 declaration added here closes that gap: it states that
the same provenance applies to the potentials and voltages XM-001 scores.

## 7. Fallback versus seeded divergence

Cross-referenced from the fallback audit rather than restated. The audit found:

- **21 value mismatches** between `_FALLBACK_RULESETS` and the seeded payloads:
  GC-001 0, CC-001 5, MC-001 16;
- **119 keys present in only one source**.

This session reproduced the 21 mismatches by the same breakdown. With lists matched
by identity (class key or label), there are 0 / 4 / 13 numeric mismatches. Adding
the CC-001 JT-001 geometry class (Tight vs Open) and three MC-001 text thresholds
gives 0 / 5 / 16:

- DL3_LONG: `>10` vs `10–20`;
- T2_DANGER: `20–45` vs `25–45°C`;
- T4_SAFE_HOT: `>45` vs `>55°C`.

The key comparison was not reproduced. This method counted 22 keys present only in
the fallback (GC-001 9, CC-001 2, MC-001 11). The different figure reflects a
different key-matching method; the audit's 119 stands as the audit's figure.

The module docstring at `app/services/corrosion_rule_catalog.py:17-20` said the
fallback tables were "strict subsets" of the stored payloads. That was false on
both counts: the values differ, and the fallback carries keys the payloads lack.
The docstring now states the divergence and points here. The divergence itself was
not resolved, because resolving it moves numbers. Every fallback value is
authored, exactly as the seeded values are.

## 8. What changed in this branch

Declarations, added to docstrings and comments only:

- `app/engines/bimguard_corrosion_engine.py` — PROVENANCE block in the module
  docstring, including the XM-001 inheritance.
- `app/engines/bimguard_crevice_engine.py` — PROVENANCE block. The "Based on EN ISO
  15329:2007" comment on the severity classes now says the classes are named after
  the framework and the figures are authored.
- `app/engines/bimguard_mic_engine.py` — PROVENANCE block. The two suspect
  citations are annotated in the standards list. `classify_dead_leg` no longer says
  its bands are "per HSE HSG274".
- `app/services/corrosion_rule_catalog.py` — "strict subsets" replaced by the
  divergence statement; PROVENANCE section added.
- `app/services/ruleset_seeder.py` — comment stating that `Source: <citation>` rows
  name the governing standard, not the source of the digit.

These are docstrings and comments only; the changed modules are identical to
origin/main by AST with docstrings stripped.

Live user-facing claims corrected, with citations kept:

- `frontend/src/lib/components/PipingChecksExplainer.svelte`
- `frontend/src/lib/glossary.ts` (GC/CC/MC reference lines)
- `docs/demo/piping-checks-plain-english.md`
- `docs/client-qa/Q01_What_Is_Piping_Corrosion_Analysis.md`
- `docs/client-qa/Q02_Interpreting_GC001_Galvanic_Findings.md`
- `docs/client-qa/Q12_Which_Building_Codes_Does_BIMGUARD_Reference.md`
- `docs/client-qa/Q14_Customising_The_Architecture_Ruleset.md`
- `README.md` (the compliance-module list also mislabelled GC-001 as seismic and
  CC-001 as atmospheric)

Deck source text, annotated so the next build does not reprint the claim:

- `scripts/build/build_deck_a.py:140` and `:164`
- `scripts/build/build_deck_c.py:172`

### Seeded wording recorded here, not edited

The applied migration keeps this wording. It is the stored payload, and migrations
are not edited once applied. A future migration that re-seeds these payloads should
replace it.

| Ruleset | Migration line | Current wording | Proposed replacement |
| --- | --- | --- | --- |
| GC-001 | :587 | description: "BIMGUARD AI compliance ruleset for galvanic corrosion risk assessment…" | Append: "Thresholds are a calibration authored for this ruleset; citations name the governing standard, not the source of the digit." |
| GC-001 | :613 | `"source": "WorldStainless / Euro Inox (2025) and AUCSC Basic Corrosion Course (2024)"` | `"governing_reference": …` (same text) plus `"provenance": "authored"` |
| GC-001 | :639 | `"source": "NASA-STD-6012 Table 1"` | `"governing_reference": "NASA-STD-6012"`, `"provenance": "authored"`. Do not name a table until it has been read. |
| GC-001 | :649 | `"source": "Prosoco Technical Note 104 / AUCSC Basic Corrosion Course (2024)"` | As above |
| GC-001 | :660 | `"source": "IMOA Design Manual 4th Ed."` | As above |
| CC-001 | :740 | ruleset description | Same appended sentence as GC-001 :587 |
| CC-001 | :769-770 | weighting rationale and CCT interpolation description | Keep; add that the weights and the 20 / 30 °C interpolation points are authored |
| CC-001 | :779-780 | `"source": "ASTM G48 Method B / CIRIA C692 / Sandvik Corrosion Handbook"` | `"governing_reference": …`, `"provenance": "authored"` |
| CC-001 | :794 | "Source: CIBSE Guide G / CIRIA C692." | "Governing guidance: CIBSE Guide G / CIRIA C692; class scores authored." |
| CC-001 | :820-821 | "Seven severity classes per EN ISO 15329:2007 wetting classification framework." / `"source": "EN ISO 15329:2007"` | "Seven severity classes named after the EN ISO 15329:2007 wetting-class framework; severity figures authored." |
| MC-001 | :929, :932 | the two suspect standard entries | Resolve per §5 before re-seeding; do not carry forward as written |
| MC-001 | :946 | weighting rationale | Keep; add that the weights are authored |
| MC-001 | :955-1022 | per-cell `"reference"` | Rename to `"governing_reference"`; replace the ASTM G-187 and NACCE entries once §5 is resolved |
| MC-001 | :1025-1033 | system-modifier `rationale` | Keep; add that multipliers are authored |

## 9. What this does not fix

- **Output strings still cite ASTM G-187 as an MIC standard practice**
  (`bimguard_mic_engine.py:538`, `phase_6c_corrosion_ui.py:399`). Every MC-001
  finding and BCF issue carries it. *Fixed 2026-09-14, §12.*
- **Findings cannot say a value is authored.** Citations are built per engine from
  standard names. A finding does not carry per-threshold status; the declaration
  lives in the code and this document.
- **No per-value status in the payloads.** GC-001, CC-001 and MC-001 have no `cite`,
  `conf` or `provenance` field. Adding one means re-seeding through a new migration.
- **The fallback divergence** (§7) is documented, not resolved.
- **Historical and generated records are unchanged.**
  - Dated validation records under `docs/validation/`, including the
    `engine-showcase-2026-09-08` samples, which quote ASTM G-187 as produced.
  - `docs/submissions/`.
  - The NotebookLM corpora: `docs/bimguard_corrosion_rules.md` quotes the old
    "strict subsets" docstring at :45603 and the old engine docstrings.
    `docs/bimguard_seismic_rules.md` includes shared files.
- **Out of scope, found in passing:** `app/services/ruleset_seeder.py` still
  describes seismic brace spacing as "per EN 1998-1 / DIN 4149", which SB-001's
  correction established is not a source. The README seismic line cites ASCE 7-22,
  while SB-001 cites ASCE/SEI 7-10. *Both examined 2026-09-14, §12: the seeder
  observation was a misreading; the README is corrected.*

### Needs rebuilding afterwards

- **Deck A and Deck C:** from `scripts/build/build_deck_a.py` and
  `build_deck_c.py`.
- **NotebookLM corpora:** `docs/bimguard_corrosion_rules.md` and
  `docs/bimguard_seismic_rules.md`, via `scripts/compile_for_notebooklm.py`.
- **Frontend production bundle:** the explainer and glossary text changed.

None was rebuilt in this session.

## 10. Moving a value from authored to sourced

For each value:

1. Obtain the document.
2. Find the table or clause that states the value, for the same condition: alloy,
   environment class, temperature, geometry.
3. Record section and page.
4. Either confirm the value, or change it through a reviewed change with its own
   test expectations.

Values the document does not state stay authored, however close they are.

Roughly what that costs:

- **Documents.** About 20 of the citations in §3 are paid standards or guides:
  ASTM G48, EN ISO 15329, EN 1993-1-4, BS 8539, BS 8552, EN ISO 9308-1, CIBSE TM13,
  CIBSE Guide G, CIRIA C692, NACE SP0198 and the like. Individual prices typically
  run from tens to a few hundred euros each, so the set is on the order of
  €2,000–€4,000.
  - NASA-STD-6012, the HSE HSG274 parts and the WHO guidelines are free.
  - The IMOA Design Manual and the Euro Inox / WorldStainless publications are
    free to download.
  - The AUCSC course is paid training rather than a document.
  - Prices were not checked in this session.
- **Effort.** 244 values (79 + 60 + 96), less the 15 derived. Most cannot be sourced
  at all: weights, band cut-offs and composite scores are design choices no standard
  states. A realistic target is the physical inputs:
  - the galvanic series potentials and voltage limits (GC-001, and through it
    XM-001);
  - the CCT table (CC-001);
  - the temperature and dead-leg regime (MC-001).

  That is on the order of 60–80 values. With the documents in hand, reading and
  recording them is a few days of a corrosion engineer's time.
- **Consequence.** Any value that changes on sourcing moves findings. Each would
  need the same treatment SB-001's two value changes received: record the change,
  measure the effect, and update test expectations.

## 11. Limitation statement (for the thesis)

The corrosion engines GC-001 (galvanic), CC-001 (crevice) and MC-001
(microbiologically influenced) score risk from thresholds, weights and band
boundaries that are a calibration authored for BIMGUARD. They are not values quoted
from the standards the rulesets cite. Each citation names the standard or body of
practice that governs the mechanism being scored, not a document from which a
number was read. None of the cited documents was held by the project, and no value
was verified against one. The rulesets were generated with AI assistance and then
organised under the governing standards. Of the numeric values in the three seeded
rulesets, 15 are derived arithmetically from other values in the same ruleset, and
the remainder are authored; none is sourced. The same holds for the material-media
(MM-001) and cross-material (XM-001) rulesets, which declared it from the outset;
XM-001's galvanic potentials and voltage limits are GC-001's. Two MC-001 citations
are defective as recorded: ASTM G-187 is a soil-resistivity practice by the
ruleset's own description yet is cited for MIC material susceptibility, and "NACCE
TPC 11" does not name an identifiable document. The fallback tables used when a
stored ruleset is unavailable diverge from the seeded rulesets in 21 values.
Corrosion findings therefore rank relative risk under a stated calibration. They do
not certify that a design meets any cited standard, and a corrosion engineer must
verify the governing values against the source documents before a finding is
relied on.

## 12. Follow-up, 2026-09-14: emitted MIC citations, the seismic remnant, the README

Branch `fix/corrosion-provenance`, from 4f8adc7. No threshold, weight, band
cut-off or scoring formula changed. No migration was edited, and no SQL was
written or run.

### 12.1 MC-001 citations no longer attribute a threshold to a named standard

**Option chosen: name the mechanism and the body of practice, and mark the
threshold authored.** Keeping the citation behind an "unverified" qualifier was
rejected. A reader of a finding sees a standard designation first and a qualifier
second. Leaving "ASTM G-187" in the standard field would still read as a source
for a number, and the ruleset's own description rules the document out. AMPP
(formerly NACE) is named as a body of practice only, and no document number is
given. The ruleset already names NACE for MIC (`"NACE / ASTM G-187"`,
`NACE SP0198`), and "NACCE" is a misspelling of that body. So nothing is named
that the ruleset does not already point to. No document title was substituted
for "TPC 11", because none can be confirmed.

| Location | Old | New |
| --- | --- | --- |
| `app/engines/bimguard_mic_engine.py:542-543` (BCF issue description) | `ASTM G-187 — MIC Assessment Standard Practice` | `AMPP (formerly NACE) industry practice — MIC mechanism only` / `MC-001 thresholds are authored calibration, not values quoted from any standard above` |
| `app/modules/phase_6/phase_6c_corrosion_ui.py:405-406` (finding citation) | standard `ASTM G-187`, clause `MIC assessment standard practice` | standard `AMPP (formerly NACE) industry practice`, clause `MIC mechanism only; MC-001 flow-class threshold is authored calibration, not a standard value` |
| `app/services/ruleset_seeder.py:681` (`source_text` default) | `NACCE TPC 11` | `AMPP (formerly NACE) industry practice, MIC mechanism only; score is MC-001 authored calibration` |

The citation `reason` (`flow class <key>`) is unchanged. The module docstring now
says neither suspect citation is emitted.
`tests/test_mc001_citation_provenance.py` holds this: all six cases fail against
4f8adc7's code and pass after the change.

The seeder default only applies to a material with no `reference`. All ten seeded
materials carry one, so seeding the current payload does not use the default.

**Effect on project 1917** (frozen export `bimguard-corrosion-project-1917.json`,
exported 2026-09-09T09:25:45Z). All **294** MC-001 findings (critical 10, high 64,
medium 220) carry the changed citation, one each. The export contains no "NACCE"
string. No MC-001 narrative quotes G-187: the flow, temperature and dead-leg
references the narrative prints are other citations.

**Score invariance, offline.** Method:

1. Parse the MC-001 `content_json` literal out of migration `20260806180500` at
   :918.
2. Serve it through a patched `StaticDataService.get_asset_json`.
3. Build the rule rows with `_seed_mc001` against a fake service. The fake uses
   the real `RuleService._build_rule_row` and captures 57 rows.
4. Serve those rows through a patched `RuleService.list_by_ruleset`.
5. Reload the engine catalog.
6. For each finding, rebuild the `MICElement` from the export. Flow velocity,
   operating temperature and dead-leg length come from the narrative. The
   material comes from the narrative's resolved catalog label, mapped back to its
   key. System and IFC type come from metadata, and diameter is metadata's
   `assumed_nominal_diameter_m`.
7. Score with `assess_mic_risk` and build the citations with `_mic_citations`.

No database, network or running server was used. Run at 4f8adc7 and again after
the change:

| | 4f8adc7 | after |
| --- | --- | --- |
| findings reconstructed | 294 / 294 | 294 / 294 |
| max abs score deviation | 0.0 | 0.0 |
| band / mitigation / class-key mismatches | 0 / 0 / 0 | 0 / 0 / 0 |
| citation `reason` equal to export | 294 | 294 |
| first citation standard | `ASTM G-187` × 294 | `AMPP (formerly NACE) industry practice` × 294 |

Finding ids are taken from the export and are unaffected. A first pass that
ignored the material label deviated on 23 findings, by up to 0.037. Those were
copper elements scored as unknown, a flaw in the reconstruction script rather
than a code difference. It was corrected before any code was changed.

**Dated evidence left as recorded.** These still show the old string, as produced
at the time:

- the 1917 frozen export;
- the `docs/validation/engine-showcase-2026-09-08/` samples and README;
- `docs/validation/final-godmode-audit-2026-09-07.md`.

### 12.2 Seeded wording recorded, not edited

Migration `20260806180500_seed_static_data_assets.sql` is applied and unchanged.
A future migration that re-seeds the MC-001 payload should use:

| Line | Current | Proposed |
| --- | --- | --- |
| :929 | `"ASTM G-187 — Standard Practice for Measurement of Soil Resistivity"` in `standards_referenced` | Remove from the MC-001 list. By its own description it has no bearing on MIC. |
| :932 | `"NACCE TPC 11 — MIC in Industrial Water Systems"` | `"AMPP (formerly NACE) — MIC industry practice (no document verified)"` |
| :961 | SRB `"reference": "ASTM G-187 / NACCE TPC 11"` | `"governing_reference": "AMPP (formerly NACE) industry practice"`, `"provenance": "authored"` |
| :969 | IOB `"reference": "NACCE TPC 11"` | as :961 |
| :977 | APB `"reference": "CIBSE Guide G / NACCE TPC 11"` | `"governing_reference": "CIBSE Guide G / AMPP (formerly NACE) industry practice"`, `"provenance": "authored"` |
| :1013 | carbon_steel `"ASTM G-187 / NACCE TPC 11"` | `"governing_reference": "AMPP (formerly NACE) industry practice"`, `"provenance": "authored"` |
| :1014 | cast_iron `"NACCE TPC 11"` | as :1013 |
| :1015 | galv_steel `"NACCE TPC 11"` | as :1013 |
| :1016 | ss304 `"ASTM G-187"` | as :1013 |
| :1017 | ss316 `"ASTM G-187"` | as :1013 |
| :1018 | duplex2205 `"NACE / ASTM G-187"` | as :1013 |
| :1022 | titanium `"ASTM G-187 — exceptional MIC resistance"` | as :1013. Drop "exceptional MIC resistance" as a sourced claim. |

**Stored `rules` rows carrying the same text.** `_seed_mc001` writes
`source_text = "Source: <reference>"`. So a database seeded from this payload holds
seven MC-001 rows whose `source_text` repeats a suspect citation:

- `MC-001.MAT.CARBON_STEEL`
- `.CAST_IRON`
- `.GALV_STEEL`
- `.SS304`
- `.SS316`
- `.DUPLEX2205`
- `.TITANIUM`

They appear in the rules catalog, not in findings. A code change cannot reach
them, because the insert pass skips existing references. Correcting them needs a
new migration. It should update `source_text` for exactly those seven references
in `ruleset_id = 'BIMGUARD-MC-001'`, and only where `source_text` still equals
the seeded value, to `Source: AMPP (formerly NACE) industry practice, MIC
mechanism only; score is MC-001 authored calibration`. It should also re-seed
the `ruleset:BIMGUARD-MC-001` static asset with the payload wording above. That
migration was not written.

### 12.3 The seismic "remnant" in `ruleset_seeder.py` is neither a second site nor an incomplete fix

§9 recorded that `ruleset_seeder.py` "still describes seismic brace spacing as
per EN 1998-1 / DIN 4149". That was a misreading of a search hit.

- The only occurrences in the file at 4f8adc7 are :768 and :775, plus the comment
  at :760. They sit inside `_SB001_SUPERSEDED`, as the **old** half of each
  `(old, new)` pair. `_correct_superseded_seismic_rows` (:792) looks for exactly
  that string and replaces it with the calibration wording. The string is the
  correction's match key, not seeded text.
- `seed_seismic_rules` (:841 onward) seeds no description containing EN 1998-1 or
  DIN 4149.
- The correction is in this branch: `fdafd86`, "stop seeding EN 1998-1 / DIN 4149
  attributions and correct stored rows", is an ancestor of 4f8adc7.
- `git log -S "DIN 4149" -- app/services/ruleset_seeder.py` shows one commit that
  introduced the wording, `eaf2afd`. Its two description strings are identical to
  the match keys, so no other variant was ever seeded from this file. Migration
  `20260913131052` matches the same two strings, plus the folder-description
  variant from `20260830001000`.

Changing those strings would stop both the in-place correction and
`tests/test_sb001_seeded_provenance.py` from matching pre-correction rows. They
were left unchanged. **No additional SQL is needed.** Any production row seeded
from this file carries exactly the string that `_correct_superseded_seismic_rows`
and migration `20260913131052` already target. Whether that migration has been
applied was not checked (no SQL run).

Found in passing, not changed:

- `.github/ISSUE_TEMPLATE/compliance_defect.yml:22` labels Blue Halo "EN 1998 /
  DIN 4149".

### 12.4 README seismic edition

`README.md:30` cited "FEMA E-74, ASCE 7-22". It now cites FEMA E-74 and ASCE/SEI
7-10 §13.6 as cited by it, and says the thresholds are screening calibration
except where marked sourced. That matches `sb001_seismic_clearance.json`.

Other files with the ASCE 7-22 mismatch, reported and not changed:

| File | What it says | Why left |
| --- | --- | --- |
| `app/constants.py:522-528` | standards registry entry "ASCE 7-22", applicable to Halo | Executable; outside this change's permitted differences |
| `scripts/NOTEBOOK_STANDARDS.py:108-114` | same registry entry | Same data, NotebookLM tooling |
| `docs/ISO19650/BIMGuard-ISO19650-Requirements.md:83` | Tier 4 row cites ASCE 7-22 and labels GC-001 as seismic bracing | Separate doc correction |
| `docs/HERMES_CONTEXT.md:67` | ASCE 7-22 in the Hermes brief | Headered Hermes artifact |
| `app/modules/blue_halo/generate_expanded_config.py`, `hermes_config_expanded.py` | the retired Hermes ASCE 7-22 + NFPA 13 pair | Accurate historical description |

### 12.5 Needs rebuilding

- **NotebookLM corpora:** `docs/bimguard_corrosion_rules.md` quotes the old BCF
  string, the old `_mic_citations` and the old seeder default. Rebuild via
  `scripts/compile_for_notebooklm.py`.
- **Decks:** no deck source changed in this follow-up. Deck A and Deck C are
  still pending from §9.
- **Frontend bundle:** no frontend file changed.
- **Running demo:** the live backend serves the old citation until it restarts on
  this code. The warm cache holds findings with the old string.
