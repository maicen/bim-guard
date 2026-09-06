# God-mode audit — Piping and Seismic at `99cdffc`

**Audit date:** 2026-09-06 / 2026-09-07
**Worktree:** `D:\Zigurat Masters\bim-guard-godmode`
**Branch:** `audit/godmode-2026-09-07`
**HEAD:** `99cdffc4e8415a15d55f19d57c9024c8c2a4c2f1` — matches the pinned commit.
**Main tree untouched:** all work confined to the worktree above.

Scope: Shane's element only — Piping (GC-001, CC-001, MC-001, MM-001, XM-001),
Seismic (SB-001), phases 6A–6E, export (csv/json/bcf), cache, pre-warm, runbook,
and the Svelte views that render them. Architecture, auth/org shell and the
project wizard are out of scope; defects tripped over there are one-liners in
§9, not investigations.

Every claim below carries a measured number, a commit hash, or a `file:line`.

---

## 1. Baseline

### 1.1 Environment

| Item | Value |
| --- | --- |
| `git rev-parse HEAD` | `99cdffc4e8415a15d55f19d57c9024c8c2a4c2f1` ✔ equals pin |
| `origin/main` at audit time | `5b4f91739c0c3cc91128a625498551376d00c0a7` |
| Commits `99cdffc..origin/main` | 30 (appendix A) |
| `99cdffc` is ancestor of `origin/main` | yes (`git merge-base --is-ancestor` → true) |
| Python | 3.12.13, `.venv` in worktree, `uv sync` clean |
| Supabase | live; `rules` table 615 rows; `static_data_assets` reachable |

**Demo model.** `uv run python scripts/generate_demo_mep_model.py` →
`data/test_hospital_mep_demo.ifc`

| Item | Value |
| --- | --- |
| SHA-256 | `302dcad174e8b94d7196527365d95aae1596861f90457473ca7d74e451f30b54` |
| Size | 717,766 bytes |
| Elements | 420 (294 with hydraulics, 42 without material, 151 with a declared couple) |
| Byte-identical across two generations | yes — regenerated, `diff` empty, same SHA-256 |

The digest recorded by the parser when project **1917** runs
(`phase_6b_parsing:328 … sha256=302dcad1…`) is the **same digest**, so project
1917's stored model is byte-identical to the freshly generated file.

Other models fetched from storage:

| Project | Model | Bytes | SHA-256 |
| --- | --- | --- | --- |
| 1540 | West Riverside plumb IFC4 | 23,762,808 | `bb53f0eb8f7295e91e0fb6ec6b79a30022a2e0e248714aab6bb1a8930c4793dd` |
| 1542 | federated plumb + str | (two models) | see §3.3 |

### 1.2 Test suite

Command (exactly as run, from the worktree root):

```
uv run pytest -n 4 -q
```

**8 failed, 1721 passed, 15 skipped, 4 xfailed, 6 warnings in 424.64s.**

All 8 failures are the same parametrised test,
`tests/test_routes.py::test_spa_routes_served_without_error`, for
`/dashboard /projects /viewer /documents /rules /analyze /settings /reports`.
Each asserts 200 and gets **404**. Cause: `frontend/dist` does not exist in a
fresh worktree, so the SPA catch-all has nothing to serve. This is an
environment precondition, **not a code defect** — after `npx vite build` the
same selection returns **9 passed in 17.59s**. Recorded as F11 (cosmetic /
environment) rather than a finding against the code.

Scoped command:

```
uv run pytest -n 4 -q tests/ -k "corros or piping or seismic or halo or bcf or export or cache or phase_6 or galvanic or crevice or microb or material_media or cross_material or ifc_parser or piping_producer"
```

**774 passed in 262.54s. 0 failed, 0 skipped.** The 8 SPA failures are outside
this selection (`test_routes.py` matches none of the `-k` terms), so the scoped
run is clean at `99cdffc`.

---

## 2. Findings, ranked

Severity key: **BLOCKS DEMO** · **WRONG NUMBER** · **COSMETIC** · **KNOWN LIMITATION**.

### F1 — MC-001's Medium and High band boundaries are not read from the database (KNOWN LIMITATION, architectural)

The stored MC-001 ruleset writes its band ranges with an **en dash** (U+2013);
GC-001 and CC-001 use an ASCII hyphen (U+002D). Every band parser in the
repository splits on `"-"` only, so MC-001's Medium and High lower bounds parse
to `None` and the engine silently substitutes hardcoded literals.

Measured, live:

```
static_data_assets → ruleset:BIMGUARD-MC-001 → risk_bands
   Medium   range='0.25 – 0.50'   dash=[U+2013]
   High     range='0.50 – 0.75'   dash=[U+2013]
   Critical range='> 0.75'        dash=[]
ruleset:BIMGUARD-GC-001 / CC-001  → all ranges dash=[U+002D]
```

Seeded rows in `public.rules` (`reference LIKE '%.BAND.%'`, 24 rows):

```
BIMGUARD-MC-001  MC-001.BAND.HIGH     check_value='null'   <-- NULL
BIMGUARD-MC-001  MC-001.BAND.MEDIUM   check_value='null'   <-- NULL
BIMGUARD-MC-001  MC-001.BAND.CRITICAL check_value='"0.75"'
BIMGUARD-GC-001  …MEDIUM/HIGH/CRITICAL check_value='"0.35"' / '"0.65"' / '"0.85"'
BIMGUARD-MM-001  …                     check_value='0.35' / '0.65' / '0.85'
```

Runtime thresholds actually loaded (measured by calling the catalog loaders):

| Engine | `risk_band_thresholds` | Complete? |
| --- | --- | --- |
| GC-001 | `{'critical': 0.85, 'high': 0.65, 'medium': 0.35}` | yes |
| CC-001 | `{'critical': 0.8, 'high': 0.55, 'medium': 0.3}` | yes |
| **MC-001** | **`{'critical': 0.75}`** | **Medium and High absent** |

The engine then fills the gap from literals:

```python
# app/engines/bimguard_mic_engine.py:161-164
thresholds = _MC_CATALOG.get("risk_band_thresholds") or {}
med  = thresholds.get("medium", 0.25)
high = thresholds.get("high", 0.50)
crit = thresholds.get("critical", 0.75)
```

`0.25` and `0.50` happen to equal the published MC-001 values, so **the demo
counts are correct**. The defect is that the database is not authoritative for
MC-001's Medium and High boundaries: editing them in Supabase changes nothing,
because the keys never reach the dict. This directly contradicts the
"Zero hardcoded thresholds; all weights/bands read from Supabase" claim (§8).

There is a **second, independent** reason the DB rows do not reach the engine:
`check_value` is stored JSON-encoded for GC/CC/MC (the 7-character string
`"0.85"`, quotes included) and `_coerce_float('"0.85"')` returns `None`
(`app/services/corrosion_rule_catalog.py:112-119`). So for GC/CC/MC the stored
rows contribute nothing at all and the JSON payload fallback supplies the
numbers. GC and CC survive that fallback because their dash is ASCII; MC does
not. MM-001 and XM-001 store bare `0.85` and are unaffected.

Also observed: GC/CC/MC band rows are **duplicated ×2** (24 rows where 18 are
expected — GC 6, CC 6, MC 6, MM 3, XM 3), despite the `_existing_references`
guard at `app/services/ruleset_seeder.py:321-329`.

**Reproduction**

```
uv run python - <<'PY'
from app.services import corrosion_rule_catalog as C
print(C.load_mc_catalog()["risk_band_thresholds"])   # {'critical': 0.75}
print(C.load_gc_catalog()["risk_band_thresholds"])   # all three
PY
```

**Not fixed** (Part A is read-only).

---

### F2 — The IFC parser is non-deterministic: two elements on 1540 change material between identical runs (WRONG NUMBER)

Same bytes, same process, same SHA-256; `parse_ifc_bytes(..., with_piping=True)`
run six times returns two different answers for two specific elements:

```
parse1: unknown_material=3565  2hmd54FKP8m9ndYFbNXrgP='Unknown'         0St58in6H1V81MuS6hDkEi='Unknown'
parse2: unknown_material=3563  2hmd54FKP8m9ndYFbNXrgP='Copper_C12200'   0St58in6H1V81MuS6hDkEi='Copper_C12200'
parse3: unknown_material=3565  … 'Unknown'
parse4: unknown_material=3563  … 'Copper_C12200'
parse5: unknown_material=3563  … 'Copper_C12200'
parse6: unknown_material=3563  … 'Copper_C12200'
```

Flip rate **2 of 6 parses**. In the failing parses the pair also loses its
system (`PipingSystem.DOMESTIC_HOT_WATER` → `PipingSystem.UNKNOWN`), so material
and system fail together — the element's association traversal, not the
inference, is what varies.

This is **not** hash-seed randomisation: all six parses ran inside one process,
where `PYTHONHASHSEED` is fixed and set iteration order for identical strings is
stable. The variation is therefore internal to `_build_element`
(`app/modules/ifc_reader/piping_producer.py:1820-1875`) or the association
lookup it calls. The precise mechanism is not isolated; narrowing it further
requires instrumenting the parser, which is a code change and out of Part A's
read-only remit.

**Effect today is confined to data-quality counts.** It is the whole of the
1540 instability the runbook records as F5. Measured over three route-level
runs of 1540:

```
run1 29,181   run2 29,183   run3 29,181     (identical sequence to the runbook)
varying engine: MM-001 only, 3,563 vs 3,565
GC/CC/MC = 8,539 each and XM = 1 in every run
```

Two elements only, no duplicates, runs 1 and 3 identical by element:

```
element_id,in_run1,in_run2,in_run3,rule_id,engine,band,score
0St58in6H1V81MuS6hDkEi,no,yes,no,MM-001.DQ,MM-001,data_quality,0.0
2hmd54FKP8m9ndYFbNXrgP,no,yes,no,MM-001.DQ,MM-001,data_quality,0.0
```

Dumped to `docs/validation/data/godmode-1540-mm001-nondeterminism.csv`.

A note on why the raw diff looks enormous (1,711 vs 1,709 rows): finding ids are
positional (`MM-1856`, `MM-1857`, …), so inserting two elements renumbers every
later row. Compared **by element**, the difference is exactly two.

**Risk beyond data quality:** on 1540 no verdict is affected because no element
has a material at all, so every row is a data-quality note either way. On a
model that does carry materials, the same flip would change an element's
material between `Copper_C12200` and absent — which changes the GC-001/CC-001
gate outcome and therefore whether a verdict exists. Not observed; structurally
reachable.

**Reproduction:** parse 1540's model six times in one process and count
`material == "Unknown"`.

---

### F3 — `resolve_material` mis-resolves 8 of the 20 galvanic-series keys, six of them to `carbon_steel` (WRONG NUMBER, latent on the demo corpus)

`app/engines/bimguard_corrosion_engine.py:188-205` matches only against
`MATERIAL_ALIASES` and never against the galvanic series' own keys, and it
normalises with `.lower().strip()` only — no separator handling. Measured:

```
series keys that do NOT resolve to themselves (8 of 20):
   'bronze'        -> 'carbon_steel'
   'cast_iron'     -> 'carbon_steel'
   'galv_steel'    -> 'carbon_steel'
   'hastelloy_c'   -> 'carbon_steel'
   'platinum'      -> 'carbon_steel'
   'silver_solder' -> 'carbon_steel'
   'ss304_active'  -> 'ss304_passive'
   'ss316_active'  -> 'ss316_passive'
```

`platinum → carbon_steel` inverts the nobility of the most noble entry in the
table; the two `active → passive` flips move stainless to the wrong side of its
passivation potential.

**Defect E specifically.** The underscore forms named in the brief:

```
'SS_316_passive'   -> carbon_steel     (should be ss316_passive)
'Galvanized_steel' -> carbon_steel     (should be galv_steel)
```

Root cause, in one sentence: the **gate** normalises with
`ifc_parser._spaced()` (`app/modules/ifc_reader/ifc_parser.py:248-258`), which
turns `SS_316_passive` into `ss 316 passive` and matches alias `ss 316`, so the
element passes preflight; the **engine** then calls `resolve_material` on the
raw string, which does not separator-normalise, matches nothing, and returns
`carbon_steel`. Two different normalisers on the same value, one deciding
whether to score and the other deciding what to score it as.

The defect is acknowledged in-code at
`app/modules/phase_6/phase_6c_corrosion_ui.py:458-461`.

**Blast radius on 1917: zero.** The demo model declares only spaced,
human-readable names, and all six resolve correctly:

| IfcMaterial in 1917 | resolves to | correct? |
| --- | --- | --- |
| `Copper` | `copper` | yes |
| `Brass` | `brass` | yes |
| `Carbon Steel` | `carbon_steel` | yes |
| `Galvanised Steel` | `galv_steel` | yes |
| `Stainless Steel 316` | `ss316_passive` | yes |
| `HDPE` | `None` (non-metallic — correct, a verdict not an absence) | yes |

The 151 `SecondaryMaterial` values are the same five metals
(Carbon Steel 54, Copper 36, Stainless Steel 316 21, Galvanised Steel 20,
Brass 20). So **0 of 420 elements on 1917 hit this defect**, and the brief's
expected count for Defect E on 1917 is 0/0.

---

### F4 — XM-001 and SB-001 findings carry no `ruleset_version` (WRONG NUMBER, provenance)

From 1917's JSON export, over all 1,706 verdict findings, `ruleset_version` is
present on exactly **1,196** — every engine except XM-001, whose 510 findings
omit it. On 1542, **all 2,937** SB-001 findings omit it. Detail in §5.

---

### F5 — Sorting SEVERITY and SCORE cannot produce an ascending order anywhere in the stack (BLOCKS DEMO — cosmetic but visible)

Confirmed live in the browser and located in four places.

**Live:** on Piping 1917, clicking `SEVERITY` twice and `SCORE` twice leaves the
first four rows unchanged at `CRITICAL | 0.96` every time. No reversal, and on
this dataset clicking `SCORE` produces no visible change at all, because
`score_desc` and `band_then_score` both put the highest-scoring criticals first.

**The handler is not a toggle** — it maps a column to one fixed mode:

```js
// frontend/src/routes/AnalyzeView.svelte:387-389
function setSort(column: string) {
  sortMode = column === "score" ? "score_desc" : "band_then_score";
}
```

Clicking the same header again re-assigns the same value, so state never
changes and no request differs.

Three supporting causes:

| # | Location | What it does |
| --- | --- | --- |
| 1 | `frontend/src/routes/AnalyzeView.svelte:387-389` | `setSort` is not a toggle — column → one fixed mode |
| 2 | `frontend/src/lib/api.ts:905` | `IssueSort = "band_then_score" \| "score_desc" \| "natural"` — **no ascending member exists** |
| 3 | `app/api/analyze.py:331-345` | `_sort_issues` implements only `-score` and `-band_weight` orders |
| 4 | `frontend/src/routes/AnalyzeView.svelte:1212, 1238` | `sortAsc={false}` is hardcoded, so the arrow is a constant, not a state indicator |

So this is structural, not a one-line handler bug: ascending is not
representable in the contract or the server. Both later commits on `origin/main`
address exactly this — `b217b5e` *"ascending sort orders for the results page"*
and `5b4f917` *"sortable SEVERITY and SCORE columns query the API"* — neither of
which is in `99cdffc`.

---

### F6 — MC-001 issues Critical verdicts on elements whose material is absent (KNOWN LIMITATION)

MC-001's preflight gate tests hydraulics only
(`app/modules/phase_6/phase_6c_corrosion_ui.py:544-560`), so an element with no
material still reaches the engine and is scored, with the material-susceptibility
term taking the catalog's `unknown`/`default` entry. Measured on 1917, finding
`MC-0321` (element `00DXjXflHIA8cDDRFYOSGE`, score 0.958, **CRITICAL**):

```json
"material_source": "absent",
"material_confidence": "none",
"environment_source": "inferred from spatial names"
```

This is arguably correct — MIC risk does not require knowing the alloy — but a
Critical coordination issue that records its own material as `absent` should say
so on its face. All 10 of 1917's Critical MC-001 verdicts are Condensate Drain
elements, matching the runbook.

---

### F7 — `/api/health` cannot perform the check the runbook asks of it (COSMETIC, demo-procedure)

`docs/demo/RUNBOOK.md` instructs the demo driver:

> Confirm it came up on the database rather than the fallback — the second
> number must be 0: `curl.exe -s http://127.0.0.1:8000/api/health`

Measured response:

```json
{"status":"ok","service":"bim-guard-api","version":"1.0.0"}
```

There is no second number, and no fallback indicator of any kind. Both handlers
(`app/main.py:245-248` and `app/api/__init__.py:69-72`) return the same fixed
three-key dict. The documented safety check — the one that distinguishes a
backend reading Supabase from one silently on `_FALLBACK_RULESETS` — **cannot be
performed as written**. Given that a fallback run "would still show verdicts …
scored from the wrong table" (runbook), this is the one procedural gap most
likely to matter on demo day.

---

### F8 — Latent: an absent flow velocity is scored as the worst flow class (KNOWN LIMITATION, 0 occurrences on this corpus)

`app/engines/bimguard_mic_engine.py:297`:

```python
element.flow_velocity_ms if element.flow_velocity_ms is not None else 0.0
```

`0.0 m/s` is `FV0_STAGNANT`, the worst class. The hydraulics gate refuses only
the **all three absent** case ("Partial data is legitimately scorable",
`phase_6c_corrosion_ui.py:527`), so an element carrying a temperature but no
velocity opens the gate and is then handed a fabricated stagnant reading.
`_mic_element`'s own docstring warns against exactly this substitution
(`phase_6c_corrosion_ui.py:318-324`) — the parser correctly passes `None`, and
the engine substitutes anyway.

**Reachability on the demo corpus: zero.** Measured over 1917's 420
ServiceElements, hydraulics are strictly all-or-nothing:

```
vel=False temp=False deadleg=False -> 126     (gate closes, data-quality)
vel=True  temp=True  deadleg=True  -> 294     (gate opens, fully populated)
PARTIAL (gate opens, >=1 input absent): 0
```

So no 1917 verdict is affected. The coercion is a live risk for any model with
partially authored hydraulics, of which the corpus contains none.

---

### F9 — Seismic does not auto-load on a cold cache; Piping does (COSMETIC, behavioural asymmetry)

The runbook says the seismic page "loads its stored result on mount". Measured:

- Cold cache (fresh backend process): the page renders only the header and a
  **Run Audit** button — no table, no spinner, no result, for 300 s of polling.
  Clicking Run Audit produced 2,937 findings in ~195 s.
- Warm cache: navigating away to Piping 1917 and back rendered
  **"Audit Findings 2,937 of 2,937"** within 5 s.

By contrast the Piping page auto-runs even on a cold cache (1917 ~10 s,
1540 ~100 s). The runbook's sentence is true only once the cache is warm, which
the pre-warm step guarantees — so this is a documentation precision issue, not a
demo blocker.

---

### F10 — `prewarm_demo.py` builds 31 combinations per Piping project, not 33 (COSMETIC, record correction)

Measured directly from `scripts/prewarm_demo.engine_combinations()`:

```
piping combinations: 31       (2**5 - 1, as the runbook states)
full-only:            1
2 piping + 1 seismic: 63      1 piping + 1 seismic: 32
```

There is no configuration that yields 33. The runbook's own text (31 per
project, 63 against a 64-entry ceiling) is correct; the figure 33 in the audit
brief is not.

---

### F11 — 8 baseline test failures are a missing `frontend/dist`, not a code defect (COSMETIC)

See §1.2. Fixed by `npx vite build`; 9 passed afterwards.

---

## 3. Determinism (A3)

All runs via `POST /api/analyze/run` through `fastapi.testclient.TestClient`
against `app.main:app`, with `use_cache=false` so each run recomputes.

### 3.1 Project 1917 — three runs, all engines

| Engine | Crit | High | Medium | Low | DQ | Total | Runbook | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GC-001 | 0 | 0 | 56 | 322 | 42 | 420 | 0/0/56/322/42 | **MATCH** |
| CC-001 | 0 | 70 | 308 | 0 | 42 | 420 | 0/70/308/0/42 | **MATCH** |
| MC-001 | 10 | 64 | 220 | 0 | 126 | 420 | 10/64/220/0/126 | **MATCH** |
| MM-001 | 0 | 0 | 146 | 0 | 36 | 182 | 0/0/146/0/36 | **MATCH** |
| XM-001 | 0 | 34 | 476 | 0 | 36 | 546 | 0/34/476/0/36 | **MATCH** |
| **TOTAL** | **10** | **168** | **1206** | **322** | **282** | **1988** | 1,988 | **MATCH** |

Identical in all three runs. `issue_stats` also matches the runbook's stat cards
exactly: total 1,706, critical 10, high 168, medium 1,206, low 322,
data-quality 282.

Determinism is **row-level**, not merely count-level: comparing the full tuple
`(id, element_id, rule_id, engine, band, score)` for all 1,988 rows,
run1 == run2 == run3. Elapsed 9.5 s / 8.5 s / 8.7 s.

No deviation, so `docs/validation/data/godmode-1917-diff.csv` was not produced —
there is nothing to put in it.

### 3.2 Project 1540 — full run

| Engine | Crit | High | Medium | Low | DQ | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GC-001 | 0 | 0 | 0 | 0 | 8,539 | 8,539 |
| CC-001 | 0 | 0 | 0 | 0 | 8,539 | 8,539 |
| MC-001 | 0 | 0 | 0 | 0 | 8,539 | 8,539 |
| MM-001 | 0 | 0 | 0 | 0 | 3,563 / 3,565 | 3,563 / 3,565 |
| XM-001 | 0 | 0 | 0 | 0 | 1 | 1 |
| **TOTAL** | **0** | **0** | **0** | **0** | **29,181 / 29,183** | — |

**Verdicts: 0 — MATCH.** **Data-quality: 29,181 or 29,183 depending on the run —
MISMATCH against the single expected figure of 29,181**, but exactly the
±2 instability the runbook already records as F5, and reproduced here in the
same 29,181 / 29,183 / 29,181 sequence. Root cause narrowed to two named
elements in the parser: see F2. A fifth independent sample taken through the
browser-driven backend also returned 29,183.

### 3.3 Project 1542 — seismic

| Metric | Measured | Expected | Verdict |
| --- | ---: | ---: | --- |
| Total clashes | 2,937 | 2,937 | **MATCH** |
| Critical | 783 | 783 | **MATCH** |
| High | 314 | 314 | **MATCH** |
| Medium | 1,840 | 1,840 | **MATCH** |
| Intra-model | 2,051 | 2,051 | **MATCH** |
| Cross-model | 886 | 886 | **MATCH** |
| Cross rows naming **both** filenames | 886 / 886 | all | **MATCH** |
| Data-quality | 0 | — | — |

`source_model` is `west_riverside_hospital_plumb_ifc4.ifc` on all 2,937;
`clashing_source_model` is `west_riverside_hospital_str_ifc4.ifc` on the 886
cross rows and the plumb file on the 2,051 intra rows. Every finding carries
`overlap_volume_mm3` and `clearance_mm = 200.0`, jurisdiction
`EN 1998-1:2020 + DIN 4149:2022`. Cold run 180.5 s.

---

## 4. Trace table A2 — engine → ruleset → Supabase

Precedence, from `app/services/corrosion_rule_catalog.py:1-21`:
seeded `rules` rows → stored `static_data_assets` JSON → `_FALLBACK_RULESETS`
(hardcoded, logged at warning level).

| Engine | Asset key | Band boundaries supplied by | Non-null numeric in DB? |
| --- | --- | --- | --- |
| GC-001 | `ruleset:BIMGUARD-GC-001` | JSON `risk_bands` (rows fail to coerce) | yes — 0.35 / 0.65 / 0.85 |
| CC-001 | `ruleset:BIMGUARD-CC-001` | JSON `risk_bands` (rows fail to coerce) | yes — 0.30 / 0.55 / 0.80 |
| MC-001 | `ruleset:BIMGUARD-MC-001` | Critical from JSON; **Medium/High from engine literals** | **no — both stored `null`** |
| MM-001 | `data/rulesets/mm_001_material_media.json` | seeded rows (bare floats) | yes — 0.35 / 0.65 / 0.85 |
| XM-001 | `data/rulesets/xm_001_cross_material.json` | seeded rows (bare floats) | yes — 0.35 / 0.65 / 0.85 |

**En-dash-blind parse sites — every occurrence, `file:line`:**

| # | Location | Consequence |
| --- | --- | --- |
| 1 | `app/services/ruleset_seeder.py:333-336` | writes `check_value=null` for MC-001 Medium/High |
| 2 | `app/services/corrosion_rule_catalog.py:216-219` | `_risk_band_thresholds` JSON fallback drops MC Medium/High |
| 3 | `app/services/corrosion_rule_catalog.py:355-358` | GC-001 synthesised rows |
| 4 | `app/services/corrosion_rule_catalog.py:570-573` | CC-001 synthesised rows |
| 5 | `app/services/corrosion_rule_catalog.py:752-755` | MC-001 synthesised rows |

All five share the shape `if "-" in range_text: … elif ">" in range_text: …`,
so a `<`-only range (the Low band) and an en-dashed range both fall through to
`None`. Low is skipped by band-name filter, so only MC-001 Medium/High are hit
today.

Related, in the same area but not en-dash: `_risk_band_thresholds` returns early
on `if thresholds:` (`corrosion_rule_catalog.py:207-208`), so a **partially**
populated dict suppresses the JSON fallback entirely. Today GC/CC/MC all produce
an empty dict from rows (JSON-quoted `check_value`), so the fallback does run —
but if one row were ever fixed to a bare float while its siblings stayed quoted,
the remaining bands would silently vanish rather than fall back.

MC-001 temperature bounds are **not** affected by the dash: they come from a
hardcoded transcription table `_TEMPERATURE_BOUNDS`
(`app/services/ruleset_seeder.py:48-55`) keyed by class name, not by parsing the
range string. `temperature_bounds_missing` is empty on the live catalog and all
six classes load, matching the runbook.

---

## 5. Trace table A5 — provenance on a 50-finding sample per engine

Source: 1917 JSON export, `findings` list (1,706 verdicts). Sample of 50 per
engine, `random.seed(20260907)`. Fields counted as missing when absent, `None`
or empty.

| Engine | pool | sampled | ruleset_version | material_source | environment_source | temperature_source | velocity_source | galvanic_couple |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GC-001 | 378 | 50 | 0 | 0 | 0 | 50 | 50 | 0 |
| CC-001 | 378 | 50 | 0 | 0 | 0 | 50 | 50 | 50 |
| MC-001 | 294 | 50 | 0 | 0 | 0 | **50** | **50** | 50 |
| MM-001 | 146 | 50 | 0 | 0 | 0 | 0 | 50 | 50 |
| **XM-001** | 510 | 50 | **50** | **50** | **50** | 50 | 50 | 50 |
| SB-001 (1542) | 2,937 | 50 | **50** | 50 | 50 | 50 | 50 | 50 |

Read with care — three different things are in that table:

1. **A real gap.** `ruleset_version` is absent from all 510 XM-001 findings and
   all 2,937 SB-001 findings, and present on every GC/CC/MC/MM finding
   (1,196 of 1,706). A consumer cannot tell which ruleset revision scored an
   XM-001 or SB-001 row.
2. **A vocabulary split, not an absence.** XM-001 does carry provenance, under
   per-side keys: `anode_material_source`, `anode_material_confidence`,
   `anode_environment_source`, `cathode_material_source`,
   `cathode_environment_source`, … (510 each). The flat
   `material_source` / `environment_source` spellings simply do not exist on
   XM-001, so any consumer must know both vocabularies.
3. **A field that no engine emits.** `temperature_source` and `velocity_source`
   appear on **no finding from any engine**. This matters most for MC-001, which
   is scored on temperature, velocity and dead-leg: its citations name the
   derived classes (`flow class FV0_STAGNANT`, `temperature class T2_DANGER`,
   `dead-leg class DL3_LONG`) but never say whether the underlying reading was
   authored in the IFC or inferred. `PipingElement` **does** carry
   `temperature_source` and `temperature_confidence`
   (`app/modules/ifc_reader/piping_schema.py:318-320`), so the provenance exists
   in the parser and is dropped at the reporting layer.

`galvanic_couple` is present on all 378 GC-001 findings and is correctly absent
elsewhere — it has no meaning for CC/MC/MM, and XM-001 records the pair through
`anode_id`/`cathode_id` instead.

Full metadata key inventory over the 1,706 findings is in
`docs/validation/data/` alongside the export artefacts.

---

## 6. Trace table A4 — defaults and coercions that could reach a verdict

The single decision point is `_preflight`
(`app/modules/phase_6/phase_6c_corrosion_ui.py:544-560`) — "the single place
that decides an element is Undetermined for a mechanism". It runs **before** the
engines, which is why most of the coercions below are unreachable on the live
path.

| # | `file:line` | Coercion | Can it reach a verdict? |
| --- | --- | --- | --- |
| 1 | `app/engines/bimguard_galvanic_engine.py:20` | `… or "carbon_steel"` | **No — dead code.** The module is a compatibility shim with zero importers anywhere in `app/`, `scripts/` or `tests/`. |
| 2 | `app/modules/comparator/compliance_runner.py:11` | `… or "carbon_steel"` | **No for piping.** Reached from `compliance_orchestrator` / `pipeline_services`, not from the phase-6c corrosion path the Piping audit runs. |
| 3 | `app/modules/comparator/compliance_runner.py:46` | `material=str(… or "carbon_steel")` | as above |
| 4 | `app/modules/comparator/compliance_runner.py:51` | `insulation_condition=… or "unknown"` | as above |
| 5 | `app/engines/bimguard_corrosion_engine.py:595` | `… or "carbon_steel"` | **No** — `_material_gate` refuses an absent or unrecognised material before GC-001 is entered. |
| 6 | `app/engines/bimguard_mic_engine.py:399` | `… or "carbon_steel"` | **Yes, but not on this corpus** — MC-001's gate tests hydraulics only, so a material-less element is scored (F6). On 1917 this produced 10 Critical verdicts with `material_source: "absent"`. |
| 7 | `app/engines/bimguard_mic_engine.py:423` | `… or "unknown"` | as above |
| 8 | **`app/engines/bimguard_mic_engine.py:297`** | `flow_velocity_ms … else 0.0` → FV0_STAGNANT | **Yes in principle, 0 occurrences measured.** Requires partial hydraulics; 1917 has 294 complete / 126 empty / **0 partial** (F8). |
| 9 | `app/engines/bimguard_mic_engine.py:77` | `return "T4_SAFE_HOT", …get("T4_SAFE_HOT", {"risk": 0.1})` | **Not currently** — all six temperature classes load with numeric bounds, so the fallback is not entered. Was the live path before migration `20260905220000`. |
| 10 | `app/engines/bimguard_mic_engine.py:320` | `UNDER_INSULATION_RISK.get("unknown", 0.0)` | Yes — insulation state is never authored; contributes a fixed term to every MC-001 score. |
| 11 | `app/modules/ifc_reader/piping_producer.py:632` | `DEFAULT_ENVIRONMENT_CLASS = T1_INDOOR_DAMP` | **Yes, and it fires.** On 1917, 210 of 420 elements are defaulted to `T1_indoor_damp` at low confidence (the other 210 from spatial names, 0 from IFC). Recorded honestly as `environment_source`, and severity 0.20 is the mildest class. |
| 12 | `app/engines/bimguard_corrosion_engine.py:194-195` | `if not material_name: return "carbon_steel"` | **No** — gate refuses empty material first. |
| 13 | `app/engines/bimguard_corrosion_engine.py:204-205` | unrecognised → `carbon_steel` | **Yes for recognised-but-mismapped strings** — this is F3; 0 occurrences on 1917. |
| 14 | `app/modules/phase_6/phase_6c_corrosion_ui.py:304-331` | `ASSUMED_NOMINAL_DIAMETER_M` | Yes — recorded as `assumed_nominal_diameter_m: 0.1` on all 294 MC-001 findings. Declared, not hidden. |

**Confirmation of `SS_316_passive` / `Galvanized_steel` on 1917 (Defect E):**
**0 elements affected of 420.** 1917's model declares only spaced names, all six
of which resolve correctly (F3 table). The underscore forms are mis-resolved by
`resolve_material` — that is real and reproducible — but they do not occur in
this model.

---

## 7. Timings

Measured on the audit machine, backend in-process (`TestClient`) unless noted.

| Operation | Cold | Warm (cache hit) |
| --- | ---: | ---: |
| 1917 corrosion, 5 engines | 8.5–10.6 s | 0.11 s |
| 1540 corrosion, 5 engines | 33.7–38.8 s | — |
| 1542 seismic, federated | 180.5 s | 0.10 s |
| 1917 export JSON | — | **0.151 s** |
| 1917 export CSV | — | **0.047 s** |
| 1917 export BCF | — | **0.575 s** |
| 1542 export JSON | — | 0.127 s |
| 1542 export CSV | — | 0.076 s |
| 1542 export BCF | — | 0.721 s |
| 1917 exports over HTTP from the SPA's own URLs | — | BCF 0.363 s, CSV 0.030 s, JSON 0.093 s |
| `npx vite build` | 64 s | — |
| full pytest `-n 4` | 424.64 s | — |
| scoped pytest `-n 4` | 262.54 s | — |

All three exports are **well under the 1 s expectation** from a warm cache, on
both projects and by both transports.

1540 at 33.7–38.8 s is materially faster than the runbook's 108–140 s. The
runbook figure was measured on a different machine; noted, not treated as a
defect.

### Export coherence (A6)

| Project | cache superset | CSV rows | JSON `findings` + `data_quality` | BCF topics |
| --- | ---: | ---: | ---: | ---: |
| 1917 | 1,988 | 1,988 | 1,706 + 282 = **1,988** | **1,384** |
| 1542 | 2,937 | 2,937 | 2,937 + 0 = **2,937** | **2,937** |

1917's BCF topic count of 1,384 equals Medium + High + Critical
(1,206 + 168 + 10) exactly, as expected. Note that the JSON export splits its
payload into two lists — `findings` and `data_quality` — so "JSON finding
count" only equals the CSV row count when both are summed.

Identical counts were obtained through the SPA's own export URLs over HTTP
(BCF 1,384 / CSV 1,988 / JSON 1,706+282).

### BCF 2.1 validation

```
uv run python scripts/validate_bcf_corpus.py --roots <folder with both archives>
  OK  topics=  2937  1542-seismic.bcf
  OK  topics=  1384  1917-corrosion.bcf
  archives valid           : 2
  archives empty (0 topics): 0
  topics validated         : 4321
```

**Violations = 0.** Both archives validate against
`tests/schemas/bcf21/markup.xsd` and `visinfo.xsd`.

Archives are not committed (2.5 MB and 5.3 MB, both over the 1 MB limit):

| Archive | Bytes | Topics | SHA-256 |
| --- | ---: | ---: | --- |
| 1917 corrosion BCF | 2,597,166 | 1,384 | recorded in `docs/validation/data/godmode-export-digests.txt` |
| 1542 seismic BCF | 5,510,727 | 2,937 | same |

---

## 8. Stale-record table (A9)

Sources: `docs/planning/ai-continuation-prompt-2026-09.md` (P),
`docs/FMP_SUBMISSION_CANDIDATE_ac55b0b.md` (F), `docs/demo/RUNBOOK.md` (R).
Neither document was edited.

| # | Claim | Where | Measured at `99cdffc` | Source of truth |
| --- | --- | --- | --- | --- |
| 1 | "MM-001 produces 13,069 real findings on real MEP models" | P:16, P:85, P:140, P:190 | On 1540 (a real MEP model) MM-001 produces **0 verdicts** and 3,563/3,565 **data-quality notes**. On 1917, 146 Medium + 36 DQ. Nothing in the corpus yields 13,069. | §3.2, §3.1 |
| 2 | "Zero hardcoded thresholds; all weights/bands read from Supabase" | F:78 | **False for MC-001.** Medium 0.25 and High 0.50 come from literals at `bimguard_mic_engine.py:162-163`; the DB values are stored `null` and never reach the engine. | F1 |
| 3 | "No fallback to carbon_steel (honest tri-state: None when unclassified)" | P:63 | **False in the engine.** `resolve_material` returns `carbon_steel` for any unrecognised metallic string (`bimguard_corrosion_engine.py:204-205`), and 8 of 20 series keys mis-resolve, 6 of them to `carbon_steel`. The *gate* is honest; the engine underneath is not. | F3 |
| 4 | Material coverage "1.9% → 33.9%" | P:60, P:203, P:209, F:70 | **58.3%** on 1540 (4,976 of 8,539 elements carry a material); **100%** on 1917 (420/420 — 378 from IFC, 42 inferred). 33.9% matches neither project. | parser coverage log |
| 5 | Temperature coverage "0% → 32.1%" | P:75, F:72 | **100%** on 1917 (420/420 — 294 from IFC, 126 inferred). | parser coverage log |
| 6 | Environment "T1 default (low confidence, 99.5%)" | P:70 | Depends on the model, and the claim is defensible for real ones: **100%** defaulted on 1540 (8,539/8,539) but only **50.0%** on 1917 (210 defaulted, 210 from spatial names, 0 from IFC). No project measures 99.5%. | parser coverage log |
| 7 | "Tests: 1,365 passing (was 1,302)" | P:88 | **1,721 passed** (8 failed on a missing `frontend/dist`, 15 skipped, 4 xfailed). | §1.2 |
| 8 | `UnknownMaterialError` | audit brief | **Does not exist** anywhere in the repository — no match in any `.py`, `.ts` or `.svelte` file. | ripgrep, whole worktree |
| 9 | Branches `fix/ruleset-source`, `fix/material-vocabulary` | audit brief | **Neither exists.** 31 branches present locally and on the remote; no match for either name. | `git branch -a` |
| 10 | "the second number must be 0" in `/api/health` | R (Start §) | `/api/health` returns `{"status","service","version"}` — **no numbers at all**, and no fallback indicator. The documented check is impossible to run. | F7 |
| 11 | Pre-warm rebuilds "33 combinations" | audit brief | **31 per Piping project**, 1 per Seismic. 63 for the runbook's two-piping-plus-one-seismic warm-up. No configuration produces 33. | F10 |
| 12 | Seismic page "loads its stored result on mount" | R §3 | True with a warm cache (result in <5 s); on a cold cache the page shows only **Run Audit** and loads nothing. | F9 |

---

## 9. Out-of-scope defects tripped over (one line each, not investigated)

- The project selector lists 30+ projects including obvious scratch entries
  (`dsadasd`, `klksmdkfmk;sdmf`, `test`, `fefefg`, `Test 1`) and two identically
  named "Clinic Architectural Imported Project" rows — a demo-day hazard in the
  dropdown, out of scope here.
- `.env` in the repo root carries `SUPABASE_SERVICE_ROLE_KEY` on a line indented
  with three spaces; `python-dotenv` tolerates it, but a naive
  `grep '^SUPABASE'` (including the one in the runbook's own pre-flight snippet)
  reports the key as missing.

---

## 10. Cache (A8)

Verified against `app/services/analysis_cache.py`.

| Property | Expected | Measured | `file:line` |
| --- | --- | --- | --- |
| Key composition | project + slug + SHA-256 + canonical engine set + include_low | `CacheKey(project_id, slug, source_sha256, engines: tuple, include_low: bool)` — exactly those five | `analysis_cache.py:122-126` |
| Engines canonicalised, stable order | yes | yes, documented and enforced | `analysis_cache.py:109-114` |
| TTL | 24 h | `TTL_SECONDS = 86400.0`, override `BIMGUARD_CACHE_TTL_SECONDS` | `analysis_cache.py:96` |
| Max entries | 64 | `MAX_ENTRIES = 64`, override `BIMGUARD_CACHE_ENTRIES`, LRU eviction | `analysis_cache.py:88` |
| Emptied by restart | yes | store is an in-process `OrderedDict` on the instance; no disk or external backing of any kind | `analysis_cache.py:52, 138` |

A restart empties the cache **by construction** — there is no persistence path
to fail. Confirmed incidentally in practice: the browser-driven backend started
for §11 had a cold cache and recomputed 1917, 1540 and 1542 from scratch despite
those results having been computed minutes earlier in a different process.

Pre-warm covers 31 combinations per Piping project (2⁵−1) and 1 per Seismic;
the 64-entry ceiling admits two full Piping projects plus one Seismic (63) with
one entry to spare, as the runbook states. See F10 on the "33" figure.

---

## 11. UI pass (A7)

Backend `127.0.0.1:8001`, SPA dev server `127.0.0.1:5174`
(`VITE_API_URL=http://127.0.0.1:8001/api`, backend started with
`BIM_GUARD_ALLOWED_ORIGINS` covering 5174). Both launched detached via
`Start-Process`. Shane's own stack on :8000/:5173 was left untouched.

Sign-in used the **"Sign in as dev test user"** button, which appeared as
expected in the dev build and completed a real Supabase password grant.

| # | Screenshot | What it shows |
| --- | --- | --- |
| 01 | `01-landing.png` | Landing page |
| 02 | `02-login.png` | Login with the dev test-user button present |
| 03 | `03-dashboard.png` | Post-sign-in dashboard |
| 04 | `04-piping-1917-all-engines.png` | Piping 1917, five chips lit, **1,988 of 1,988** on mount |
| 05 | `05-piping-1917-XM-unticked.png` | XM-001 unticked → **1,442 of 1,442** |
| 06 | `06-piping-1917-sort-score.png` | After two SCORE clicks — order unchanged (F5) |
| 07 | `07-piping-1917-critical-filter.png` | Severity = Critical → **10 of 1,988** |
| 08 | `08-piping-1917-finding-report.png` | Finding Report for `MC-0309`, citations + metadata |
| 09 | `09-piping-1917-isolate-3d.png` | Isolate-in-3D action |
| 10 | `10-viewer-3d-isolated.png` | Viewer at `#/viewer?project_id=1917&element_guid=…`, canvas rendered |
| 11 | `11-piping-1540.png` | Piping 1540 — **29,183 of 29,183**, all data quality |
| 12 | `12-seismic-1542.png` | Seismic 1542 — **2,937 of 2,937** |
| 13 | `13-seismic-1542-warm-automount.png` | Same page auto-loading from a warm cache |
| 14 | `14-seismic-finding-report.png` | SB-001 Finding Report with measured overlap and both standards |
| 15 | `15-piping-1917-export-controls.png` | BCF 2.1 / CSV / JSON export controls |

15 files in `docs/validation/screenshots/godmode-2026-09-07/`.

**Chip toggling is exact.** 1,988 − 546 (XM-001's total from §3.1) = 1,442,
which is what the page showed with XM unticked. Re-ticking restored 1,988.

**Sort.** Confirmed broken as described in F5.

**Finding Report** renders the full citation set and the metadata block. The
1917 report shown carries `ruleset_version: BIMGUARD-MC-001 v1.0.0`,
`material_source: absent` (F6), `environment_source: inferred from spatial
names`. The 1542 report carries the real measured overlap
(`44,225,542 mm^3 (44.3% of the halo volume)`), the 200.0 mm clearance and both
`EN 1998-1` and `DIN 4149` citations.

**Isolate in 3D** navigates to
`#/viewer?project_id=1917&element_guid=20KeDvTYrO59MhDS4MnkZ9` and the viewer
renders a canvas. The piping route accepts `project_id` as a query parameter
read reactively — relevant to Part B's ReferenceLink row.

**Requests over 5 s.** Three, all of them analysis computes on a cold cache, all
expected: 1917 ~10 s, 1540 ~100 s, 1542 ~195 s. No other request exceeded 5 s.

**4xx / 5xx.** None observed on any audited page. Every export URL returned 200.

One methodological note: an early ref-based click on a **Details** button
appeared to do nothing, which looked like a defect. It was a stale element
reference from a snapshot taken before the severity filter re-rendered the
table. Clicking the live DOM node opens the modal correctly. Recorded here so
the negative result is not mistaken for a finding.

---

## Appendix A — commits after the pinned SHA

`origin/main` moved 30 commits past `99cdffc` during the audit. Not rebased onto;
listed for context only. The two most relevant to this report are `b217b5e` and
`5b4f917`, which fix F5.

```
5b4f917 fix(results): sortable SEVERITY and SCORE columns query the API
b217b5e feat(results): ascending sort orders for the results page
bf06c66 Fix infinite refetch loops in Documents/Projects/Rules views and stale project fallback
f46ac70 Batch database operations for ruleset and document access grants
9aa1435 Merge pull request #68 from maicen/perf/fix-n-plus-one-document-access
6db0ff5 Fix circular import in config by inlining DB_BACKEND constant
670d213 Enhance insert_many to handle insert results
96852e9 Optimize delete_many to handle bulk deletions
a4d9c9a perf: fix N+1 queries in document access control bindings
537642d Merge pull request #67 from maicen/fix/ifc-file-signature-validation
3471d86 Refactor IFC content validation for header probing
7a2bd89 Fix unsafe IFC file upload validation
c1329e9 Merge pull request #66 from maicen/bolt-optimizations
f227d95 Bolt: backend lookup optimization for duplicate document checks
a045e4d docs: add Jules environment setup instructions and remove obsolete scripts README
b4b7ec4 Enforce API standardization: strict contracts, auth, tags, and a stable programmatic surface
47cf29b fix(security): require authentication on every previously-open API route
610aca4 fix(frontend): type the piping explainer's snippet prop correctly
29fe9d0 docs(validation): engine matrix and validation report from the 5 Sept harness run
3932bca chore: ignore local Claude Code settings
57d247b docs(validation): rehearsal-ready screenshots
4c413b4 docs(demo): plain-English explanation of the five piping checks
558d63b fix(auth): gate the first authenticated request on session restore, not retries
f00c49c ui(findings): Finding Report layout
772d8a7 feat(findings): deterministic narrative and mitigation text per engine
29ac6e0 fix(viewer): retry IFC/BCF loads once if the auth token wasn't ready yet
259a730 fix(auth): stop 401s on projects/rules/IFC loads from unauthenticated requests
0b3d60d ui(header): align top-bar titles with the audit rename
800d374 ui(piping): add plain-English explainer beside the engine selector
af5c17b ui(audit): rename Piping and Seismic audit headings
```

Note that `47cf29b` ("require authentication on every previously-open API
route") post-dates this audit's commit, so the runbook's known limitation
"`/api/analyze/*` has no authentication" is accurate **at `99cdffc`** and has
since been addressed on `main`.

---
---

# Part B — BCF 2.1 conformance gap matrix

Read-only. Nothing in this section was changed; it is the plan Part C works to.

## B1. Writer inventory — what is live, what is dead

| Module | Lines | Status | Called by |
| --- | ---: | --- | --- |
| `app/modules/reporter/bcf_generator.py` | 475 | **LIVE — the only writer that produces the demo's archives** | `phase_6e_export.py:36`; also imported by the three corrosion engines (`bimguard_corrosion_engine.py:37`, `bimguard_crevice_engine.py:36`, `bimguard_mic_engine.py:36`), `report_artifacts.py:10`, `blue_halo_bcf_exporter.py:43`, `reporter/__init__.py:17` |
| `app/modules/phase_6/phase_6e_export.py` (`_bcf_issue`, `to_bcf`) | — | **LIVE — the mapping layer the UI's Export BCF 2.1 button reaches** | `app/api/analyze.py` export endpoint |
| `app/services/report_artifacts.py` | 166 | **LIVE, separate path** — persists BCF artefacts to storage and serves `/api/analyze/bcf/*`. Builds its own `BCFIssue` list from stored topic dicts (`_topic_to_issue`, line 118) rather than from `Issue` objects, so it is a **second, independently-drifting mapping** of the same target schema. | `analyze.py:818,848,876,884`, `arch_analysis_service.py:17` |
| `app/services/bcf_sync_service.py` | 364 | **LIVE as an API, but purely in-memory.** Despite the docstring "In-memory & persistent store", state lives in three plain dicts on the instance (`bcf_sync_service.py:41-44`) with no database or storage backing. Status and assignment changes do not survive a restart and never reach the export path. | `app/api/bcf_routes.py:27` |
| `app/api/bcf_routes.py` | 335 | **LIVE** — registered in `app/main.py:23`. REST surface over `BCFSyncService`. | FastAPI app |
| `app/services/bcf_exporter.py` | 538 | **DEAD for the product.** No importer anywhere in `app/`. Used only by `scripts/run_full_pipeline.py:52`, `scripts/run_seismic_matrix.py:68` and `tests/test_bcf_exporter.py:14`. | harness scripts + its own test |
| `app/modules/reporter/blue_halo_bcf_exporter.py` | 218 | **DEAD for the product.** No importer in `app/`; referenced only by `scripts/validate_blue_halo.py:70`. The seismic BCF the demo downloads comes from `phase_6e_export.to_bcf`, not from here. | one validation script |

**Consequence for Part C:** all conformance work belongs in `bcf_generator.py`
and `phase_6e_export._bcf_issue`. `report_artifacts._topic_to_issue` is a
second mapping that will drift unless it is fed from the same helper; it is
called out per-row where relevant. The two dead exporters are deliberately left
alone — changing them would alter no archive the demo produces.

## B2. Measured "before" state, whole-archive

Counted across every topic in both freshly generated archives:

| Property | 1917 (1,384 topics) | 1542 (2,937 topics) |
| --- | --- | --- |
| `TopicType` | `Issue` x1,384 | `Issue` x2,937 — **including every SB-001 clash** |
| `CreationAuthor` | `BIMGUARD AI — GC-001/CC-001 v1.0.0` x1,384 | same string x2,937 — **on seismic topics** |
| Viewpoint `Color` | `FF888888` x1,384 | `FF888888` x2,937 |
| `Component` per viewpoint | 2 (1 selection + 1 coloring) x1,384 | 2 x2,937 |
| `extensions.xsd` in archive | **absent** (declared by `project.bcfp`) | **absent** |
| Root entries | `bcf.version`, `project.bcfp` | same |

**Two defects fall straight out of that table and were not previously recorded:**

- **B-DEF-1 — every topic in every archive is coloured grey.**
  `_risk_colour` (`bcf_generator.py:298-305`) keys on `"LOW"/"MEDIUM"/"HIGH"/"CRITICAL"`
  (upper case) but `_bcf_issue` passes `risk_band=issue.band.value`,
  which is lower case (`"medium"`). Every lookup misses and returns the
  `FF888888` default. Measured: **4,321 of 4,321 topics grey.** The band
  colouring has never worked in any archive this path produced.
- **B-DEF-2 — `project.bcfp` declares `ExtensionSchema extensions.xsd`
  but `generate_bcf` never writes that file** (`bcf_generator.py:348-359`
  writes only `bcf.version` and `project.bcfp` at the root). Every archive
  references a schema it does not contain. It validates today only because the
  corpus validator checks `markup.xsd`/`visinfo.xsd` and does not resolve the
  extension schema reference.

## B3. Data availability — proof from real records

**One real 1917 finding** (`MC-0391`, the topic dumped in B5):

```json
{"id": "MC-0391", "element_id": "1tcMzQAf1O$QGXNveYm5Cf",
 "rule_id": "MC-001.01", "band": "medium", "score": 0.297,
 "mechanism": "MC-001 microbiologically influenced corrosion",
 "assignee_role": "Mechanical engineer",
 "metadata": {"mechanism_code": "MC-001",
              "ruleset_version": "BIMGUARD-MC-001 v1.0.0",
              "floor": "Level 00 Basement", "system": "LTHW Heating",
              "ifc_type": "IfcValve",
              "material_source": "...", "environment_source": "...",
              "assumed_nominal_diameter_m": 0.1},
 "citations": [{"standard": "ASTM G-187", "clause": "...", "reason": "flow class ..."},
               {"standard": "EN ISO 9308-1", "clause": "...", "reason": "..."},
               {"standard": "BIMGUARD-MC-001 v1.0.0", "clause": "Composite scoring", "reason": "..."}]}
```

**One real 1542 clash** (`SB-0002`):

```json
{"metadata": {"mechanism_code": "SB-001",
  "halo_id": "ad20a6b4-...",
  "clashing_element_id": "3W4UPvPfv6vOSdYhV7_PW$",
  "clashing_element_class": "IfcBeam",
  "source_model": "west_riverside_hospital_plumb_ifc4.ifc",
  "clashing_source_model": "west_riverside_hospital_str_ifc4.ifc",
  "overlap_volume_mm3": 131822370.75410318,
  "clearance_mm": 200.0,
  "brace_type": "angle_iron", "rule_variant": "angle_fire",
  "jurisdiction": "EN 1998-1:2020 + DIN 4149:2022"}}
```

Every field the matrix below calls "available" is a key in one of those two
records, in `projects` (section 1.1 schema dump), or in `app/constants.py`.

## B4. The matrix

Legend for (a): `file:line` of what writes it today, or **absent**.
Hours are implementation + tests + one regeneration/validation cycle.

### Topic

| Field | (a) written today | (b) where the data already is | (c) gap | hrs |
| --- | --- | --- | --- | ---: |
| `Guid` | `bcf_generator.py:150,220` — `bcf_topic_guid(issue.guid)`, deterministic UUIDv5 from the finding id; folder name and attribute always agree | `Issue.id` | **none** | 0 |
| `Title` | `:221` from `issue.title` | `Issue.title`; engine, floor, system in `metadata` | Convention `{DOMAIN}-{ENGINE}-{FLOOR}-{seq:04d} {problem}` not applied. Seismic titles truncate the GUID to 8 chars ("clash on 19FnYm9E") and name no element. Floor is empty on all 2,937 seismic findings, so `{FLOOR}` needs a fallback token rather than an empty segment | 3 |
| `TopicType` | `:220` — **hardcoded `"Issue"`** | `Issue.mechanism` (`data_quality`), `metadata.mechanism_code` (`SB-001`) | All 4,321 topics say `Issue`. Needs Clash for SB-001, Warning for data-quality, Issue for verdicts — and the three values declared in `extensions.xsd` | 2 |
| `TopicStatus` | `:220` from `issue.status`, always `"Open"` | — | **none** (Open is correct for a freshly exported finding) | 0 |
| `Priority` | `:223` from `BAND_TO_BCF_PRIORITY[issue.band]` giving Critical/Major/Normal/Minor | `Issue.band` | Values are BCF-conventional but **undeclared** in `extensions.xsd`, and the band-to-priority mapping is documented nowhere. Also note `_priority_int` (`:307`) defines a *second*, unused mapping | 1 |
| `Index` | `:224` from enumeration order | — | **none** | 0 |
| `Labels` | `:190` from `issue.mechanism`, `issue.band`, plus `data-quality` and `check` for DQ (`phase_6e_export.py:232-237`); ISO tags appended at `:152-159` | `metadata.mechanism_code`, `.system`, `.floor`, `.ruleset_version`; `source_model`; `metadata.check` | Missing: engine id as its own label, mechanism, system, floor, source model filename, `ruleset:{ruleset_version}`. The `check:` prefix is not applied to the DQ label. Today only two labels on a verdict topic | 3 |
| `Stage` | **absent** | `projects` has no stage column (section 1.1: 31 columns, none is `stage`) | **Omit — no real source.** Recorded here as a deliberate omission, per the no-fabrication rule | 0 |
| `CreationDate` | `:227` from `_utc_now()` | — | **none** | 0 |
| `CreationAuthor` | `:228` — **hardcoded `"BIMGUARD AI — GC-001/CC-001 v1.0.0"`** | `metadata.mechanism_code` + `metadata.ruleset_version` | Wrong on every MC/MM/XM/SB topic (4,321 of 4,321 carry the GC/CC string). Target `BIMGUARD AI {ENGINE} {ruleset_version}`. **Blocked for XM-001 and SB-001**, which carry no `ruleset_version` at all (F4) — those must either gain the field upstream or omit the version half | 2 |
| `ModifiedDate` | `:229` — **always emitted**, `_utc_now()`, on a topic that has never been edited | `BCFSyncService` topic dicts carry `modified_date`/`modified_author` (`bcf_sync_service.py:85-86`) but are in-memory only and never reach the exporter | Emit only when a real edit exists; today it asserts an edit that did not happen | 1 |
| `ModifiedAuthor` | **absent** | as above | Pair with ModifiedDate | 0.5 |
| `DueDate` | `phase_6e_export.py:246` — **`datetime.now()`**, i.e. the export date, on every topic | no project or rule field carries a due date | **Fabricated. Remove.** `bcf_generator.py:164-169` already omits the element when `due_date` is falsy, so this is a one-line deletion in the mapper | 0.5 |
| `AssignedTo` | `:230` from `issue.assignee_role` | `Issue.assignee_role` | **none** | 0 |
| `Description` | `:231` from `issue.description or issue.mitigation or issue.title` | all inputs, scores, thresholds, citations in `metadata` + `citations` | Corrosion descriptions are one sentence ("MC-001 assessed this element as medium.") carrying no element identity, no inputs, no provenance, no threshold, no clause. Seismic is materially better — it already names both elements, the overlap volume and the percentage. Target is the structured block in the brief | 6 |
| `ReferenceLink` | `:222` — **emitted empty** | project id known; route verified in section 11 to accept `?project_id=` | Route accepts `project_id` (confirmed live) but **there is no `finding` parameter** — `AnalyzeView` reads only `project_id` off the querystring. Deep-linking to a *finding* requires a frontend change, so this is a genuine gap, not a link to invent. Two options: link to the project view only (honest, cheap), or add `&finding=` handling first | 1 project-level / +4 finding-level |
| `DocumentReference` | **absent** | `app/constants.py` holds the standards with URLs/DOIs; citations name the exact clause per finding | One `DocumentReference` per standard the ruleset cites, `Description` = clause, `ReferencedDocument` = the constant's URL | 3 |
| `RelatedTopics` | **absent** | XM-001: `anode_id`/`cathode_id`; SB-001: `clashing_element_id` + `halo_id` | Needs a second pass over the finding set to resolve a partner finding's topic GUID. Deterministic GUIDs (`bcf_topic_guid`) make this cheap once the pairing is known | 4 |
| `BimSnippet` | **absent** | the whole finding dict is already serialised for the JSON export | Write `finding.json` into the topic folder, reference it as `BimSnippet` with `SnippetType="JSON"`, declare `JSON` in `extensions.xsd` | 3 |

### Comment

| Field | (a) | (b) | (c) | hrs |
| --- | --- | --- | --- | ---: |
| Auto comment | `:232-236` — one comment, GUID + date + author `BIMGUARD AI` + body | — | Body says "corrosion compliance engine" **on seismic topics**, and prints an empty `Service type:` and `Floor/zone:` for all 2,937 (neither is populated for SB-001) | 1 |
| Status/assignment audit trail | **absent** | `BCFSyncService._topics_by_project` / `_comments_by_topic` | **Blocked.** The sync service is in-memory only (B1), so there is no durable record to turn into comments. Persisting it is a schema change — outside the export-layer-only constraint of Part C | out of scope |

### Viewpoint

| Field | (a) | (b) | (c) | hrs |
| --- | --- | --- | --- | ---: |
| `PerspectiveCamera` | `:276-296` — camera `(camera_*+5, -8, +3)`, direction toward `target_*`, up `0,0,1`, FOV 60 | `ServiceElement.position_x/y/z` (`phase_6c_corrosion_ui.py:248-250`); `ifc_geometry` bboxes for SB-001 and the 3D isolate | Structure is correct and already XSD-valid, but `_bcf_issue` never sets `camera_*`/`target_*`, so the dataclass defaults apply and **every topic in both archives has the identical camera** at `(5, -8, 8)` looking at `(-5, 8, -8)`. Up-vector and FOV already match the target | 4 |
| `Components/Selection` | `:255-262` — one `Component` per id from `_component_guids`, with `OriginatingSystem` and `AuthoringToolId`; `IfcGuid` only when it is a real 22-char GlobalId | `metadata.clashing_element_id` (SB-001), `anode_id`/`cathode_id` (XM-001) | Shape is exactly right; the **partners are never passed**. `_bcf_issue` does not set `related_component_guids`, so all 4,321 viewpoints select one element. Wiring the partner in is a mapper change, not a generator change | 2 |
| `Visibility` | `:265` — `DefaultVisibility="true"` | — | **none** | 0 |
| `ViewSetupHints SpacesVisible=false` | **absent** | — | Add inside `Components`, before `Selection` (XSD sequence order) | 0.5 |
| `Coloring` | `:266-270` — `Color` per band over the component list | `Issue.band` | **Broken — always grey** (B-DEF-1). One-line case fix, plus a second colour for the partner once partners are selected | 1 |
| `ClippingPlanes` | **absent** | bbox where it exists | Optional +/-2 m section box; only where a bbox is available, else omit | 3 |
| `Snapshot` | `:311-324` — a 1x1 red PNG placeholder, written to every topic | no rendered view exists server-side | **Gap named, not closed.** A real snapshot needs headless rendering, which is not an export-layer change | out of scope |

### Container

| Field | (a) | (b) | (c) | hrs |
| --- | --- | --- | --- | ---: |
| `bcf.version` | `:340-346` — `VersionId="2.1"`, `DetailedVersion 2.1` | — | **none** | 0 |
| `project.bcfp` `ProjectId` | `:350,354` — **a fresh random UUID per export** | `projects.id` (1917 / 1542) | Carries no relationship to the project | 0.5 |
| `project.bcfp` `Name` | `:355` — constant `"BIMGUARD AI — Corrosion Compliance Report"` | `projects.name` (e.g. "BIMGUARD Demo — Hospital MEP (data)") | Constant, and wrong for seismic | 0.5 |
| `extensions.xsd` | **declared at `:357`, never written** | the emitted TopicType / TopicStatus / Priority / Label / SnippetType / Stage values | **B-DEF-2.** Must be written, and must list exactly what BIMGUARD emits | 2 |
| `Header/File/Filename` | `:217` — hardcoded `BIMGUARD_AI_Model.ifc` | `projects.ifc_file_path`; `metadata.source_model` and `.clashing_source_model` per seismic finding | Wrong on every topic. Cross-model seismic topics need **two** `File` entries — the data is present on all 886 | 3 |
| `Header/File/@IfcProject` | `:206-208` — emitted only when `project_code` is a 22-char IFC GUID; 1917's `project_code` is `""`, so **never emitted** | `IfcOpenShell` `by_type("IfcProject")[0].GlobalId` — requires reading the model | Needs the parser to surface the IfcProject GlobalId onto the result. The guard at `:206` is correct and should stay | 3 |
| `Header/File/@Date` | **absent** | `projects.created_at` / `updated_at` (both populated: `2026-09-06T07:50:03+00:00`) | Model upload timestamp | 1 |

### Totals

| Group | Hours |
| --- | ---: |
| Topic | 29.0 (+4 optional for finding-level deep links) |
| Comment | 1.0 |
| Viewpoint | 10.5 |
| Container | 10.0 |
| **Total** | **50.5** (+4 optional) |

Excluded as outside the export layer: real snapshots, and a durable
status/assignment audit trail — both need work beyond `bcf_generator` and
`_bcf_issue`.

## B5. One topic, before — 1917

Topic folder `006A2816-44CF-545F-B3FD-D516EE2A4F3D`, finding `MC-0391`.

```xml
<Markup xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Header>
    <File>
      <Filename>BIMGUARD_AI_Model.ifc</Filename>
    </File>
  </Header>
  <Topic Guid="006A2816-44CF-545F-B3FD-D516EE2A4F3D" TopicType="Issue" TopicStatus="Open">
    <ReferenceLink></ReferenceLink>
    <Title>Microbiologically influenced corrosion risk on LTHW-065 LTHW Plant Room DN108</Title>
    <Priority>Normal</Priority>
    <Index>743</Index>
    <Labels>MC-001 microbiologically influenced corrosion</Labels>
    <Labels>medium</Labels>
    <CreationDate>2026-09-06T21:31:47.597000Z</CreationDate>
    <CreationAuthor>BIMGUARD AI — GC-001/CC-001 v1.0.0</CreationAuthor>
    <ModifiedDate>2026-09-06T21:31:47.597000Z</ModifiedDate>
    <DueDate>2026-09-06T00:00:00Z</DueDate>
    <AssignedTo>Mechanical engineer</AssignedTo>
    <Description>MC-001 assessed this element as medium.</Description>
  </Topic>
  <Comment Guid="105A1ABA-B555-4A44-9313-4ACB85D63551">
    <Date>2026-09-06T21:31:47.597000Z</Date>
    <Author>BIMGUARD AI</Author>
    <Comment>Issue automatically generated by BIMGUARD AI corrosion compliance engine.
Source finding id: MC-0391
Mechanism: MC-001 microbiologically influenced corrosion | Risk score: 0.2970 | Band: medium
Component: IfcValve (1tcMzQAf1O$QGXNveYm5Cf)
Service type: LTHW Heating | Floor/zone: Level 00 Basement
Mitigation: MIT-MIC-009</Comment>
  </Comment>
  <Viewpoints Guid="7F215461-3472-4F03-A3B4-7B073E23E0A3">
    <Viewpoint>viewpoint.bcfv</Viewpoint>
    <Snapshot>snapshot.png</Snapshot>
    <Index>0</Index>
  </Viewpoints>
</Markup>
```

```xml
<VisualizationInfo Guid="7F215461-3472-4F03-A3B4-7B073E23E0A3">
  <Components>
    <Selection>
      <Component IfcGuid="1tcMzQAf1O$QGXNveYm5Cf">
        <OriginatingSystem>BIMGUARD AI</OriginatingSystem>
        <AuthoringToolId>1tcMzQAf1O$QGXNveYm5Cf</AuthoringToolId>
      </Component>
    </Selection>
    <Visibility DefaultVisibility="true"/>
    <Coloring>
      <Color Color="FF888888">
        <Component IfcGuid="1tcMzQAf1O$QGXNveYm5Cf"/>
      </Color>
    </Coloring>
  </Components>
  <PerspectiveCamera>
    <CameraViewPoint><X>5.0</X><Y>-8.0</Y><Z>8.0</Z></CameraViewPoint>
    <CameraDirection><X>-5.0</X><Y>8.0</Y><Z>-8.0</Z></CameraDirection>
    <CameraUpVector><X>0</X><Y>0</Y><Z>1</Z></CameraUpVector>
    <FieldOfView>60</FieldOfView>
  </PerspectiveCamera>
</VisualizationInfo>
```

## B6. One topic, before — 1542

Topic folder `000240C7-2F50-5242-A8DE-E09A93C9AFD5`, finding `SB-0337`.

```xml
<Markup xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Header>
    <File>
      <Filename>BIMGUARD_AI_Model.ifc</Filename>
    </File>
  </Header>
  <Topic Guid="000240C7-2F50-5242-A8DE-E09A93C9AFD5" TopicType="Issue" TopicStatus="Open">
    <ReferenceLink></ReferenceLink>
    <Title>Seismic bracing clearance clash on 19FnYm9E</Title>
    <Priority>Major</Priority>
    <Index>935</Index>
    <Labels>SB-001 seismic bracing</Labels>
    <Labels>high</Labels>
    <CreationDate>2026-09-06T21:39:20.282430Z</CreationDate>
    <CreationAuthor>BIMGUARD AI — GC-001/CC-001 v1.0.0</CreationAuthor>
    <ModifiedDate>2026-09-06T21:39:20.282430Z</ModifiedDate>
    <DueDate>2026-09-06T00:00:00Z</DueDate>
    <AssignedTo>Mechanical engineer</AssignedTo>
    <Description>IfcPipeFitting (19FnYm9EH0DhpCzeZN3XNH) intrudes into the seismic bracing clearance halo of IfcPipeSegment (19FnYm9EH0DhpCzeZN3XNC) by 4,624,067 mm^3 (6.4% of the halo volume).</Description>
  </Topic>
  <Comment Guid="F71B70A6-88B0-4319-94DA-456FA757DABA">
    <Date>2026-09-06T21:39:20.282430Z</Date>
    <Author>BIMGUARD AI</Author>
    <Comment>Issue automatically generated by BIMGUARD AI corrosion compliance engine.
Source finding id: SB-0337
Mechanism: SB-001 seismic bracing | Risk score: 0.7000 | Band: high
Component: 19FnYm9EH0DhpCzeZN3XNC (19FnYm9EH0DhpCzeZN3XNC)
Service type:  | Floor/zone:
Mitigation: Relocate 19FnYm9E or re-route the braced service to restore 200.0mm clearance.</Comment>
  </Comment>
  <Viewpoints Guid="17140ED1-4338-46E2-84C0-C223867E53E7">
    <Viewpoint>viewpoint.bcfv</Viewpoint>
    <Snapshot>snapshot.png</Snapshot>
    <Index>0</Index>
  </Viewpoints>
</Markup>
```

Note on this topic specifically: the archive knows from `metadata` that the
clashing element is `19FnYm9EH0DhpCzeZN3XNH` and which model each element came
from, yet the `Header` names a file that does not exist, the viewpoint selects
only one of the two elements, and the auto-comment calls a seismic clash a
"corrosion compliance engine" result with an empty service type and floor.
