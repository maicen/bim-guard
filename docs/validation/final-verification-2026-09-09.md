# Pre-freeze verification of merged `main`

Re-verification of the demo against merged `main`, run from VS Code on a
purpose-started backend (`:8001`) and frontend (`:5174`). Read-only against the
working tree: nothing was fixed, and every mismatch below is reported rather
than repaired.

## 0. Session facts, and two corrections to the brief

**The verification ran on Monday 7 September 2026, not Wednesday the 9th.**
The host clock reads `Mon Sep 7 21:45 WEST 2026`, and every commit the brief
attributes to "Monday" and "Tuesday" is dated 2026-09-07. The brief's premise
that two days had elapsed is wrong; the merge and both fixes landed earlier the
same day this verification ran. The filenames the brief specified
(`final-verification-2026-09-09.md`, `screenshots/verify-2026-09-09/`) are kept
verbatim as named deliverables, but they do not describe the run date.

**Nothing was listening on `:8000` or `:5173`.** The brief's instruction to
avoid "the running servers ... Sunday's code" was moot — `netstat` showed both
ports free before anything was started.

### HEAD

```
f3fecca8dd1db155b913b2804ee0c08eaec1557f
feat(projects): replace header project switcher with persistent short name + ISO 19650 code
2026-09-07 22:29:41 +0300
```

`git pull origin main` fast-forwarded `2313206 -> f3fecca`. **`f3fecca` is not a
commit the brief anticipated**: it landed roughly 75 minutes before this run and
carries a schema migration (`20260907190708_add_short_name_and_require_project_code.sql`)
plus the removal of `ProjectSwitcher.svelte`. The migration is already applied to
the live database — every project row returned a populated `short_name` and
`project_code`.

Required ancestry, all confirmed present:

| Brief's reference | Actual SHA at HEAD | Note |
| --- | --- | --- |
| Monday's merge | `fd7a635` merge: BCF 2.1 topic conformance and god-mode audit record | ancestor of HEAD |
| Tuesday fix 1 | `4ec85e4` fix(rulesets): parse en-dash band ranges and JSON-quoted thresholds... | was `377442b` |
| Tuesday fix 2 | `06663a4` fix(provenance): ruleset_version on XM-001 and SB-001 findings | was `44e4fdd` |

The two fix SHAs differ from the ones in the brief because local `main` was
rebased before this session; the commits are identical in content (same four
files, same +231 lines) and the pre-rebase SHAs are no longer reachable.

### Servers and the FALLBACK gate

Backend `uv run uvicorn app.main:app --host 127.0.0.1 --port 8001`, logging to
`docs/validation/verify-backend.log` (confirmed gitignored by `.gitignore:84 *.log`).
Frontend built first (`npx vite build`, clean, 3590 modules, 1m 4s) then served
by `npx vite` on `:5174`.

One deviation, deliberate and non-invasive: `frontend/vite.config.ts` hardcodes
its dev proxy to `127.0.0.1:8000` with no environment override, so a dev server
on `:5174` would have proxied `/api` to a dead port. Rather than edit a tracked
file during a read-only verification, the dev server was started with an
out-of-repo config (`--config <scratchpad>/vite.verify.config.mts`) identical to
the repo's except for `port: 5174` and the two proxy targets pointing at `:8001`.
The working tree was not touched. `/api`, `/static` and the SPA root all
returned 200 through that proxy.

**FALLBACK gate: PASS.** Across 67,627 log lines:

```
Using hardcoded fallback ruleset  -> not present
RulesetIncompleteError            -> not present
WARNING lines                     -> none
```

Startup shows `static_data_assets?...asset_key=eq.ruleset:BIMGUARD-GC-001 ... 200 OK`
and equivalents for CC-001 and MC-001 — the database, not the reduced table.

## 1. Counts (route level, against `:8001`)

All figures MATCH.

### 1917 — all engines, run twice

| Figure | Expected | Actual | Verdict |
| --- | ---: | ---: | --- |
| Total findings | 1,988 | 1,988 | **MATCH** |
| Pass 1 | — | 20.6 s, `cached=false` | — |
| Pass 2 | — | 2.6 s, `cached=true` | **MATCH** |

Per engine (Critical / High / Medium / Low / Data Quality):

| Engine | Expected | Actual | Total | Verdict |
| --- | --- | --- | ---: | --- |
| GC-001 | 0/0/56/322/42 | 0/0/56/322/42 | 420 | **MATCH** |
| CC-001 | 0/70/308/0/42 | 0/70/308/0/42 | 420 | **MATCH** |
| MC-001 | 10/64/220/0/126 | 10/64/220/0/126 | 420 | **MATCH** |
| MM-001 | 0/0/146/0/36 | 0/0/146/0/36 | 182 | **MATCH** |
| XM-001 | 0/34/476/0/36 | 0/34/476/0/36 | 546 | **MATCH** |
| **Total** | **1,988** | **1,988** | | **MATCH** |

Aggregate stats match the runbook's stat cards exactly: total 1,706, critical 10,
high 168, medium 1,206, low 322, data-quality 282. Note the Low/DQ split is only
visible via `mechanism == "data_quality"` (the authoritative discriminator, per
`app/api/analyze.py:219`); data-quality notes carry `band="low"` in the contract.

### 1540 — full, once

| Figure | Expected | Actual | Verdict |
| --- | ---: | ---: | --- |
| Total findings | 29,181 or 29,183 | 29,183 | **MATCH** |
| Verdicts | 0 | 0 (all 29,183 are data-quality) | **MATCH** |

127.0 s, `cached=false`.

### 1542 — seismic, once

| Figure | Expected | Actual | Verdict |
| --- | ---: | ---: | --- |
| Total | 2,937 | 2,937 | **MATCH** |
| Critical / High / Medium | 783 / 314 / 1,840 | 783 / 314 / 1,840 | **MATCH** |
| Intra-model | 2,051 | 2,051 | **MATCH** |
| Cross-model | 886 | 886 | **MATCH** |

189.2 s, `cached=false` — well under the runbook's measured 577 s. Intra/cross
split computed from `details.source_model` vs `details.clashing_source_model`;
0 findings were unclassifiable.

## 2. MC-001 band thresholds and their source

**MATCH — the database is authoritative.**

All five engines' band rows, read live from `public.rules`:

| Engine | medium | high | critical | Source |
| --- | ---: | ---: | ---: | --- |
| GC-001 | 0.35 | 0.65 | 0.85 | DB rows |
| CC-001 | 0.30 | 0.55 | 0.80 | DB rows |
| **MC-001** | **0.25** | **0.50** | **0.75** | **DB rows** |
| MM-001 | 0.35 | 0.65 | 0.85 | DB rows |
| XM-001 | 0.35 | 0.65 | 0.85 | DB rows |

MC-001 is exactly `{medium 0.25, high 0.5, critical 0.75}` as required.

### Source proof

The JSON-fallback path in `_risk_band_thresholds`
(`app/services/corrosion_rule_catalog.py:381-386`) emits one WARNING per band —
`"Ruleset %s band %s came from the stored JSON payload, not a rule row"`.
Loading all three catalogs with a capturing log handler attached produced:

```
GC-001: {"critical": 0.85, "high": 0.65, "medium": 0.35}   JSON-fallback band WARNINGs: 0
CC-001: {"critical": 0.8,  "high": 0.55, "medium": 0.3}    JSON-fallback band WARNINGs: 0
MC-001: {"critical": 0.75, "high": 0.5,  "medium": 0.25}   JSON-fallback band WARNINGs: 0
```

Zero warnings for MC-001 means every boundary came from a rule row — not the
JSON payload, and not an engine literal.

Corroborating evidence — the underlying rows are clean and deduplicated,
15 of them, all bare numbers:

```
id= 234  MC-001.BAND.MEDIUM     check_value='0.25'
id= 235  MC-001.BAND.HIGH       check_value='0.5'
id= 236  MC-001.BAND.CRITICAL   check_value='0.75'
```

This means the repair in `docs/validation/sql/20260908_mc001_band_rows.sql`
**has already been applied** to the live project: the duplicate ids 7117-7125 are
gone, the `'null'` values on MC-001 MEDIUM/HIGH are gone, and the previously
JSON-quoted values are stored bare. Both the pre-condition (24 dirty rows) and
the post-condition (15 clean rows) that block asserts are consistent with a
completed run. Every MC-001 finding narrative independently cites the boundary,
e.g. *"Composite 0.958 against the Critical boundary 0.75 (BIMGUARD-MC-001 v1.0.0)"*.

## 3. Exports from the warm cache on `:8001`

| Export | Expected | Actual | Verdict |
| --- | ---: | ---: | --- |
| 1917 CSV rows | 1,988 | 1,988 | **MATCH** |
| 1917 JSON findings | 1,988 | 1,988 (1,706 verdicts + 282 data-quality) | **MATCH** |
| 1917 JSON missing `ruleset_version` | 0 | **246** | **MISMATCH** |
| 1917 BCF topics | 1,384 | 1,384 | **MATCH** |
| 1917 BCF XSD violations | 0 | 0 | **MATCH** |
| 1542 BCF topics | 2,937 | 2,937 | **MATCH** |
| 1542 BCF XSD violations | 0 | 0 | **MATCH** |

BCF validated topic-by-topic against the in-repo BCF 2.1 schema
`tests/schemas/bcf21/markup.xsd` — all 1,384 and all 2,937 markup files valid.

### MISMATCH: 246 data-quality notes carry no `ruleset_version`

Every **verdict** carries provenance. The gap is entirely in the data-quality
bucket, and only XM-001's notes were fixed:

| Bucket | Engine | Records | Missing `ruleset_version` |
| --- | --- | ---: | ---: |
| findings | GC/CC/MC/MM/XM | 1,706 | 0 |
| data_quality | GC-001 | 42 | **42** |
| data_quality | CC-001 | 42 | **42** |
| data_quality | MC-001 | 126 | **126** |
| data_quality | MM-001 | 36 | **36** |
| data_quality | XM-001 | 36 | 0 |
| | | | **246** |

Cause. `_data_quality_issue` builds its metadata at
`app/modules/phase_6/phase_6c_corrosion_ui.py:857-880` with `check`,
`mechanism_code`, `reason`, `ifc_type`, `material_a`, the gate inputs and
`_provenance(element)` — and no `ruleset_version`. XM-001's notes escape this
because XM stamps the version over its whole issue list in bulk at
`phase_6c_corrosion_ui.py:790-792`, which was the scope of Tuesday's
`06663a4 fix(provenance): ruleset_version on XM-001 and SB-001 findings`. GC-001,
CC-001, MC-001 and MM-001 data-quality notes were never in that commit's scope.

Not repaired, per instruction.

### 1917 GC-001 topic — `0FA76751-B031-587A-B8C3-C7C92A825EEF/markup.bcf`

Folder contains `markup.bcf`, `viewpoint.bcfv`, `snapshot.png`, `finding.json`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Markup xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Header>
    <File>
      <Filename>test_hospital_mep_demo.ifc</Filename>
      <Date>2026-09-06T08:06:16+00:00</Date>
    </File>
  </Header>
  <Topic Guid="0FA76751-B031-587A-B8C3-C7C92A825EEF" TopicType="Issue" TopicStatus="Open">
    <ReferenceLink></ReferenceLink>
    <Title>PIP-GC-L03-0941 Galvanic corrosion risk on DCW-036 Cold Water External Roof DN15</Title>
    <Priority>Normal</Priority>
    <Index>940</Index>
    <Labels>GC-001 galvanic corrosion</Labels>
    <Labels>medium</Labels>
    <Labels>GC-001</Labels>
    <Labels>ruleset:BIMGUARD-GC-001 v1.0.0</Labels>
    <CreationDate>2026-09-07T19:59:48.358856Z</CreationDate>
    <CreationAuthor>BIMGUARD AI GC-001 v1.0.0</CreationAuthor>
    <ModifiedDate>2026-09-07T19:59:48.358856Z</ModifiedDate>
    <AssignedTo>Mechanical engineer</AssignedTo>
    <Description>Brass (70/30) coupled to Copper gives a 0.04 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Couple basis: bimetallic pair from model. Non-stainless material - PREN check not applicable. Composite 0.36 against the Medium boundary 0.35 (BIMGUARD-GC-001 v1.0.0).

ELEMENT
  Type: IfcPipeSegment
  GUID: 2VAB3QUpXKFeie3oOqfeu0
  System: Domestic Cold Water
  Floor: Level 03 Roof

INPUTS
  Material source: ifc_metadata
  Material confidence: high
  Environment source: inferred from spatial names
  Environment confidence: medium
  Galvanic couple basis: bimetallic_pair_from_model

ASSESSMENT
  Band: medium
  Score: 0.36
  Ruleset: BIMGUARD-GC-001 v1.0.0

STANDARDS
  NASA-STD-6012 - Voltage threshold by environment class: threshold 0.25V for Normal heated indoor; measured gap 0.04V
  BIMGUARD-GC-001 v1.0.0 - Composite scoring: area ratio 0.1 banded Unfavourable

MITIGATION
  MIT-GC-004; MIT-GC-010</Description>
    <BimSnippet SnippetType="JSON" isExternal="false">
      <Reference>finding.json</Reference>
      <ReferenceSchema></ReferenceSchema>
    </BimSnippet>
    <DocumentReference Guid="C0A1EA8E-EC9B-55A5-A1B2-BD28E55D88C4" isExternal="false">
      <Description>NASA-STD-6012 - Voltage threshold by environment class</Description>
    </DocumentReference>
    <DocumentReference Guid="EBDC64C9-4E69-56A3-8CC7-4A2599F4E5A4" isExternal="false">
      <Description>BIMGUARD-GC-001 v1.0.0 - Composite scoring</Description>
    </DocumentReference>
    <RelatedTopic Guid="A1807C02-62D9-5B50-8577-9F96209D2F05"/>
    <RelatedTopic Guid="D4706933-2210-5455-98D1-1CFA5CBB029E"/>
  </Topic>
  <Comment Guid="E5DB3598-0DFE-4BAA-9193-16056CC9A5AE">
    <Date>2026-09-07T19:59:48.358856Z</Date>
    <Author>BIMGUARD AI</Author>
    <Comment>Issue automatically generated by BIMGUARD AI corrosion compliance engine.
Source finding id: GC-0022
Mechanism: GC-001 galvanic corrosion | Risk score: 0.3600 | Band: medium
Component: IfcPipeSegment (2VAB3QUpXKFeie3oOqfeu0)
Service type: Domestic Cold Water | Floor/zone: Level 03 Roof
Mitigation: MIT-GC-004; MIT-GC-010</Comment>
  </Comment>
  <Viewpoints Guid="ACB9C065-B81B-4FAC-89DB-A8FF44048873">
    <Viewpoint>viewpoint.bcfv</Viewpoint>
    <Snapshot>snapshot.png</Snapshot>
    <Index>0</Index>
  </Viewpoints>
</Markup>
```

### 1542 cross-model topic — `0034202B-5E0E-5E8E-AA49-BD2B9BFECA96/markup.bcf`

Folder contains `markup.bcf`, `viewpoint.bcfv`, `snapshot.png`, `finding.json`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Markup xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Header>
    <File>
      <Filename>west_riverside_hospital_plumb_ifc4.ifc</Filename>
      <Date>2026-09-05T20:03:55+00:00</Date>
    </File>
    <File>
      <Filename>west_riverside_hospital_str_ifc4.ifc</Filename>
      <Date>2026-09-05T20:04:54+00:00</Date>
    </File>
  </Header>
  <Topic Guid="0034202B-5E0E-5E8E-AA49-BD2B9BFECA96" TopicType="Clash" TopicStatus="Open">
    <ReferenceLink></ReferenceLink>
    <Title>SEI-SB-NA-0369 Bracing clearance clash 2hmd54FKP8m9ndYFbNXrz8 vs 1KKUUPboD1dQdWx8AZE2Gh</Title>
    <Priority>Critical</Priority>
    <Index>368</Index>
    <Labels>SB-001 seismic bracing</Labels>
    <Labels>critical</Labels>
    <Labels>SB-001</Labels>
    <Labels>ruleset:BIMGUARD-SB-001 v1.0.0</Labels>
    <CreationDate>2026-09-07T19:59:51.720285Z</CreationDate>
    <CreationAuthor>BIMGUARD AI SB-001 v1.0.0</CreationAuthor>
    <ModifiedDate>2026-09-07T19:59:51.720285Z</ModifiedDate>
    <AssignedTo>Mechanical engineer</AssignedTo>
    <Description>IfcBeam (1KKUUPboD1dQdWx8AZE2Gh) intrudes into the seismic bracing clearance halo of IfcPipeSegment (2hmd54FKP8m9ndYFbNXrz8) by 74,367,955 mm^3 (99.6% of the halo volume).

ELEMENT
  GUID: 2hmd54FKP8m9ndYFbNXrz8

CLASH GEOMETRY
  Halo element: f7575445-276e-4e6f-a5e8-273f511330a6
  Clashing element: 1KKUUPboD1dQdWx8AZE2Gh
  Clashing element class: IfcBeam
  Overlap volume: 74,367,954.6 mm3
  Required clearance: 200 mm
  Brace type: angle_iron
  Rule variant: angle_fire
  Jurisdiction: EN 1998-1:2020 + DIN 4149:2022
  Source model: west_riverside_hospital_plumb_ifc4.ifc
  Clashing source model: west_riverside_hospital_str_ifc4.ifc

ASSESSMENT
  Band: critical
  Score: 0.9
  Ruleset: BIMGUARD-SB-001 v1.0.0

STANDARDS
  EN 1998-1 - EN 1998-1:2020 + DIN 4149:2022 bracing clearance: 200.0mm clearance applied to angle_iron bracing (variant angle_fire)
  DIN 4149 - EN 1998-1:2020 + DIN 4149:2022 bracing clearance: 200.0mm clearance applied to angle_iron bracing (variant angle_fire)

MITIGATION
  Relocate 1KKUUPbo or re-route the braced service to restore 200.0mm clearance.</Description>
    <BimSnippet SnippetType="JSON" isExternal="false">
      <Reference>finding.json</Reference>
      <ReferenceSchema></ReferenceSchema>
    </BimSnippet>
    <DocumentReference Guid="9996724B-C282-5F7A-AF93-C0A5AB2749AF" isExternal="false">
      <Description>EN 1998-1 - EN 1998-1:2020 + DIN 4149:2022 bracing clearance</Description>
    </DocumentReference>
    <DocumentReference Guid="85AF3C30-6525-5440-ADAF-271E5D8801CB" isExternal="false">
      <Description>DIN 4149 - EN 1998-1:2020 + DIN 4149:2022 bracing clearance</Description>
    </DocumentReference>
    <RelatedTopic Guid="99521039-8EBF-552E-8932-C89B8FB94594"/>
    <RelatedTopic Guid="D8D7422D-4382-5D11-B901-9A6D65539DA0"/>
    <RelatedTopic Guid="5CF64848-9E82-57F3-B514-22F1F68D02EF"/>
    <RelatedTopic Guid="50540019-B520-5877-B4DE-48FFBCEAAC78"/>
    <RelatedTopic Guid="EC2B26AF-1B0B-5040-B0A2-CE0DB110F099"/>
    <RelatedTopic Guid="EAE3D130-42B8-536B-9DB7-D773F3CBB5CB"/>
    <RelatedTopic Guid="23FE3464-50B6-5878-9D7B-30F651FC8DDC"/>
    <RelatedTopic Guid="C6F0FC7D-C0A2-5DCD-ACA2-3185111E891C"/>
    <RelatedTopic Guid="68C2D35E-5FCE-5931-88FC-F22ADA372DF4"/>
    <RelatedTopic Guid="49DC5187-87EB-5FE3-9AC9-CB284B449004"/>
    <RelatedTopic Guid="9F336C94-6EA0-5C16-8F03-74A4E31C4178"/>
    <RelatedTopic Guid="72AFAF84-1973-51A0-8D17-2F9F4D4E0419"/>
    <RelatedTopic Guid="661E2406-6777-55D5-B1F9-EDEE32C586B0"/>
    <RelatedTopic Guid="F1DEE68B-DB01-5809-BB19-568D51564074"/>
    <RelatedTopic Guid="33E36D93-BBF9-5409-B41F-EACF9BED6935"/>
    <RelatedTopic Guid="98D0122F-FDB1-5BE4-9196-8AE5F2D09CE9"/>
  </Topic>
  <Comment Guid="3840C3EC-3D23-4B74-B19F-53F8915AC845">
    <Date>2026-09-07T19:59:51.720285Z</Date>
    <Author>BIMGUARD AI</Author>
    <Comment>Issue automatically generated by BIMGUARD AI corrosion compliance engine.
Source finding id: SB-2805
Mechanism: SB-001 seismic bracing | Risk score: 0.9000 | Band: critical
Component: 2hmd54FKP8m9ndYFbNXrz8 (2hmd54FKP8m9ndYFbNXrz8)
Related components: 1KKUUPboD1dQdWx8AZE2Gh
Service type:  | Floor/zone: 
Mitigation: Relocate 1KKUUPbo or re-route the braced service to restore 200.0mm clearance.</Comment>
  </Comment>
  <Viewpoints Guid="ED4C4C9E-7165-47EB-B222-61603B47F590">
    <Viewpoint>viewpoint.bcfv</Viewpoint>
    <Snapshot>snapshot.png</Snapshot>
    <Index>0</Index>
  </Viewpoints>
</Markup>
```

### Topic conformance — both topics

| Check | 1917 GC-001 | 1542 cross-model |
| --- | --- | --- |
| TopicType | `Issue` PASS | `Clash` PASS |
| CreationAuthor names engine + ruleset revision | `BIMGUARD AI GC-001 v1.0.0` PASS | `BIMGUARD AI SB-001 v1.0.0` PASS |
| No `DueDate` | absent PASS | absent PASS |
| Real `Filename`(s) in Header | 1 real filename PASS | **2** real filenames PASS |
| `DocumentReference` present | 2 PASS | 2 PASS |
| `finding.json` in topic folder | present PASS | present PASS |
| Title `{DOMAIN}-{ENGINE}-{FLOOR}-{seq}` | `PIP-GC-L03-0941` PASS | `SEI-SB-NA-0369` PASS |

## 4. Sort verdict — **WORKS**

Tested on Piping 1917 at `:5174`. One correction to the brief: `b217b5e` and
`5b4f917` are both authored by **Shane Haines**, not Osama.

Each column was exercised from a freshly reloaded default page.

| State | `aria-sort` | Request `sort=` | First three rows |
| --- | --- | --- | --- |
| Default | `none` | `band_then_score` | CRITICAL MC-001.01 0.96 x3 (`20KeDvTY...`, `0g9DJwi2...`, `0etgMFfP...`) |
| SEVERITY x1 | `descending` | `band_then_score` | CRITICAL MC-001.01 0.96 x3 (same three) |
| SEVERITY x2 | `ascending` | **`band_asc`** | LOW GC-001.01 x3 (`0Ac56GiX...`, `3iC2aMqM...`, `2DxcoUYe...`) |
| SCORE x1 | `descending` | **`score_desc`** | CRITICAL MC-001.01 0.96 x3 (same three) |
| SCORE x2 | `ascending` | **`score_asc`** | LOW GC-001.01 x3 (`0Ac56GiX...`, `3iC2aMqM...`, `2DxcoUYe...`) |

Screenshots `03-sort-0-default.png`, `04-sort-severity-1.png`,
`05-sort-severity-2.png`, `06-sort-score-1.png`, `07-sort-score-2.png`.

Both columns query the API with a changed `sort` parameter, and both genuinely
flip direction — the head of the table goes from Critical/0.96 to Low.

On the brief's criterion "ascending must actually reverse the order": it
reverses direction but is **not** a strict reversal, and that is the documented
intent, not a defect. `b217b5e` states it explicitly — `_is_data_quality` leads
the sort key in both `band_asc` and `score_asc` so data-quality notes sort *last*
in both directions, because a plain reversal would open the ascending page with
the elements the engines refused to score. Observed behaviour matches that
contract exactly.

Two incidental observations, neither affecting the verdict:

- The sortable `<th>` carries the click handler directly (no inner button) and
  sits below the fold on a 1080-tall viewport; a click must be preceded by
  scrolling it into view. This is a harness note, not an app bug — hit-testing
  confirmed the header is simply outside the viewport, not overlaid.
- In both ascending states the SCORE cell renders `-` for the leading rows. The
  API returns `score: 0.0` for those findings, so this is a falsy-check in the
  cell renderer displaying `-` instead of `0.00`. Cosmetic.

## 5. Walkthrough (`docs/demo/RUNBOOK.md` on `:5174`)

18 screenshots in `docs/validation/screenshots/verify-2026-09-09/`.

| Step | Result |
| --- | --- |
| Sign in as dev test user | OK — button present in the dev build, real Supabase password grant (`01-signin.png`) |
| ALL PROJECTS | OK — 34 projects, registry table renders (`02-dashboard-all-projects.png`) |
| 1917 Piping loads on mount | OK — `Audit Findings 1,988 of 1,988`, `Cached SHA-256` badge, five chips lit (`03`, `08`) |
| Chips: untick XM-001 | OK — 1,988 -> **1,442** (-546, exactly XM-001's total); request drops to `engines=GC&CC&MC&MM` (`09`) |
| Chips: re-tick XM-001 | OK — back to 1,988 |
| Critical filter | OK — `10 of 1,988`, 10 rows, all MC-001, all Condensate Drain (`10`) |
| Finding Report | OK — modal `MC-0309 - MC-001.01 CRITICAL`, target GUID, mitigations, White Box citations (`11`) |
| Isolate in 3D | Partial — navigates to `#/viewer?org=1&project_id=1917`, model loads (`Viewing: test_hospital_mep_demo.ifc`), canvas renders, ISOLATE control present. **The URL carries no element GUID**, so automatic isolation of the finding's element could not be confirmed (`12`) |
| 1917 three exports | **FAILS — 401** (see below) (`13`) |
| 1540 | OK — `Audit Findings 29,183 of 29,183`, leading rows all `CC-001.DATA` data-quality (`14`) |
| 1542 | OK — `Audit Findings 2,937 of 2,937` (`15`) |
| 1542 both filenames on a cross row | OK, with a caveat — both `west_riverside_hospital_plumb_ifc4.ifc` and `..._str_ifc4.ifc` appear in the Finding Report, but only inside the **collapsed** `METADATA PARAMETERS` disclosure, rendered as raw JSON. Not visible on the row itself (`16`) |
| 1542 exports | **FAILS — 401** (`17`) |

### Blocking defect: every UI export returns 401

Clicking **Export BCF 2.1 / CSV / JSON** navigates the whole tab off the SPA to
the raw API URL and lands on `{"detail":"Missing bearer token"}`.

```
GET /api/analyze/export?project_id=1917&slug=corrosion&fmt=bcf&engines=GC&...  ->  401
GET /api/analyze/export?project_id=1542&slug=seismic&fmt=bcf                  ->  401
```

Cause. The backend anticipates exactly this case: `get_current_user_flexible`
(`app/auth.py:79-103`) accepts the token as a `?token=` query parameter
"for links the frontend opens via direct browser navigation ... those can't set an
Authorization header", and the export route uses
`get_project_access_checker_flexible` (`app/api/projects.py:222`) for that reason.
**The frontend never appends the token.** `getExportUrl`
(`frontend/src/lib/api.ts:1123`) builds the URL with `project_id`, `slug`, `fmt`,
`engines`, `include_low`, `band` and `include_data_quality` — and no `token`.
Consumers: `frontend/src/routes/AnalyzeView.svelte:538` (`window.location.href`)
and the three `<a href>` export links at `:1104`, `:1120`, `:1136`.

Proved directly against `:8001`:

```
GET /api/analyze/export?project_id=1917&slug=corrosion&fmt=csv            -> 401
GET /api/analyze/export?project_id=1917&slug=corrosion&fmt=csv&token=...  -> 200
```

This is a **regression introduced the day before this run** by
`47cf29b fix(security): require authentication on every previously-open API route`
(2026-09-06), which moved the export route behind the flexible checker without
the corresponding frontend change. `getExportUrl` has never carried a token in
its history.

The export *payloads* are correct — section 3 obtained all four via the API and
every figure but one matched. It is only the in-browser download path that is
broken, and it is on the runbook's demo script three times.

Not repaired, per instruction.

### Network observations

From a HAR of the full walkthrough: 761 requests, 115 to `/api/`.

**4xx/5xx — 2 total**, both the export 401 above (one on 1917, one on 1542). No
5xx anywhere; no non-API errors.

**Requests slower than 5 s — 24 of 115:**

| Endpoint | Count | Min | Max |
| --- | ---: | ---: | ---: |
| `dashboard/stats` | 19 | 5.5 s | 7.2 s |
| `analyze/results/1917/corrosion` | 1 | 19.0 s | 19.0 s |
| `projects/1917/inputs` | 1 | 6.5 s | 6.5 s |
| `projects` | 1 | 6.2 s | 6.2 s |
| `rules` | 1 | 5.3 s | 5.3 s |
| `rules/folders` | 1 | 5.3 s | 5.3 s |

Two things worth flagging for demo day:

- The 19.0 s `analyze/results` call is the XM-001 chip untick — that engine
  combination was not pre-warmed, so it recomputed live. This is precisely the
  failure mode `docs/demo/RUNBOOK.md` warns about; warm all 31 combinations
  (`scripts/prewarm_demo.py`) before presenting, or do not touch the chips.
- `dashboard/stats` was called **25 times** during the walkthrough with a median
  of 5.6 s and a maximum of 7.2 s. Both the call volume and the latency are high
  enough to be visible to an audience.

## Summary

| Section | Verdict |
| --- | --- |
| FALLBACK gate | PASS |
| 1. Counts — 1917, 1540, 1542 | **MATCH on every figure** |
| 2. MC-001 thresholds, DB-sourced | **MATCH**, proven by zero fallback warnings |
| 3. CSV / BCF topic counts / XSD validity | **MATCH** |
| 3. JSON `ruleset_version` completeness | **MISMATCH — 246 missing** |
| 4. Sort | **WORKS** |
| 5. Walkthrough | Passes except **UI exports 401 (blocking)** |

Two defects found, neither repaired:

1. **UI export 401** — blocking for the demo script.
   `frontend/src/lib/api.ts:1123` omits `&token=`; regression from `47cf29b`.
2. **246 data-quality notes without `ruleset_version`** in the JSON export.
   `app/modules/phase_6/phase_6c_corrosion_ui.py:857-880`; XM-001 exempt because
   of the bulk stamp at `:790-792`.
