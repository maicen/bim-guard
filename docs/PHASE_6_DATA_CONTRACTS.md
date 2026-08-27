# Phase 6+ Data Contracts

Interfaces between the Phase 6–9 work sessions. Each session owns one side of a
boundary defined here; nobody reads another session's internals.

These contracts are **derived from code that already exists**, not invented for
this document. Where a shape is already declared in the codebase, this file
points at it rather than restating it — the code is the source of truth and this
file is the map. Every section names the module it comes from.

| Session | Branch | Owns | Produces | Consumes |
| --- | --- | --- | --- | --- |
| A | `phase-6a-upload` | IFC + document upload | stored file refs | — |
| B | `phase-6b-parsing` | IFC parsing | `ParsedIFC` | file refs from A |
| C | `phase-7-corrosion-ui` | corrosion results UI | `AnalysisResult` | `ParsedIFC` |
| D | `phase-8-seismic` | seismic engine + UI | `AnalysisResult` | `ParsedIFC` |
| E | `phase-9-export` | BCF / report export | export artefacts | `AnalysisResult` |

All five branch from `main` at `2d7d80c` (Phase 5).

---

## 0. What Phase 5 already established

Phase 5 fixed the wizard's dangling redirect and, in doing so, pinned three
patterns that Phase 6+ must follow rather than re-invent.

### 0.1 Slug routing — one mapping, no duplicates

`app/constants.py` owns the analysis-type → URL-slug mapping:

```python
ANALYSIS_ROUTES: dict[str, str] = {
    "Piping (Corrosive)": "corrosion",
    "Halo":               "seismic",
    "Architecture":       "architecture",
}
```

The wizard builds its redirect from this dict; the routes in
`app/routes/analyze_*.py` serve those slugs. Phase 5 added an import-time guard
so the two cannot silently drift — `AnalysisSpec.__post_init__` raises
`ValueError` if a spec's slug is not the registered slug for its analysis type.

> **Contract:** a new analysis type is added to `ANALYSIS_TYPES` **and**
> `ANALYSIS_ROUTES` in the same change, with a matching `AnalysisSpec`. Never
> hard-code a slug anywhere else. Session D adds nothing here — `Halo` →
> `seismic` already exists.

### 0.2 `AnalysisSpec` — per-analysis-type page config

From `app/components/analysis_ui.py`. Frozen dataclass; the three route modules
each declare one `SPEC` and share the page body.

| Field | Type | Meaning |
| --- | --- | --- |
| `slug` | `str` | URL segment; validated against `ANALYSIS_ROUTES` |
| `analysis_type` | `str` | Matching `ANALYSIS_TYPES` entry |
| `title` | `str` | Page heading |
| `summary` | `str` | One line under the heading |
| `run_href` | `str` | Where the run button goes; `""` = no engine yet |
| `run_label` | `str` | Button caption |
| `pending_note` | `str` | Shown instead of the button when `run_href` is `""` |

> **Contract:** Session D's deliverable is, in part, flipping
> `analyze_seismic.SPEC` from `pending_note` to a real `run_href`. That is the
> single switch that turns the seismic page from informational to functional.
> Do not add a fourth landing-page layout — extend `AnalysisSpec` with a field
> if the seismic page needs something the other two don't.

### 0.3 `get_analysis_inputs` — the merged-inputs pattern

From `ProjectsService.get_analysis_inputs(project_id)`. Merges project
standards and client documents into one list so a caller sees a single stream:

```python
{"kind": "standard" | "document",
 "id": "standard-12" | "document-4",   # prefixed — unique across both sources
 "label": str,                          # standard name, or document filename
 "detail": str,                         # domain, or document category
 "file_path": str}                      # storage ref; "" for notebook standards
```

> **Contract:** Sessions A and B extend this function when they add an input
> source. They do **not** add a parallel `get_ifc_inputs()`. The `kind`
> discriminator and the `<kind>-<id>` prefix convention are how callers stay
> source-agnostic.

---

## 1. `ParsedIFC` — Session B output

Session B (`phase-6b-parsing`) turns a stored IFC reference into structured
elements. The element shape **already exists** as `ServiceElement` in
`app/modules/module2_ifc_read/ifc_parser.py`:

```python
@dataclass
class ServiceElement:
    guid: str                      # IFC GlobalId — the join key for everything downstream
    name: str
    ifc_type: str                  # "IfcPipeSegment", "IfcValve", …
    description: str
    material_a: str                # normalised via normalise_material_name()
    material_b: Optional[str]      # second material at a bimetallic junction
    location_tag: str
    floor: str
    system: str
    joint_type: str                # "JT-001" … see IFC_TO_JOINT
    anode_area_m2: float
    cathode_area_m2: float
    position: tuple                # (x, y, z) in metres
    length_m: float
    notes: str = ""
```

> **Contract:** Session B does **not** redefine this dataclass. Adding a field
> is allowed and must default, so existing constructors keep working.

`ParsedIFC` is the envelope Session B returns:

```python
{
  "source_ref":     str,            # storage ref the parse ran against
  "source_sha256":  str,            # hex digest — cache/lineage key
  "schema":         str,            # "IFC4", "IFC2X3", …
  "schema_note":    str | None,     # get_schema_compatibility_note(model)
  "elements":       list[ServiceElement],
  "element_count":  int,            # == len(elements); denormalised for summaries
  "type_counts":    dict[str, int], # ifc_type -> count
  "quality": {
      "valid":       bool,
      "error":       str | None,    # set when the file could not be read at all
      "warnings":    list[str],
      "improvements":list[dict],
  },
}
```

### Rules — ParsedIFC

1. **`guid` is the join key.** Every downstream `Issue.element_id` is a `guid`
   from this list. An `Issue` referencing an absent guid is a bug — Session C/D
   test suites already assert this (`test_every_issue_references_a_real_element`).
2. **A file that cannot be read is not an exception.** Set
   `quality.valid = False` and `quality.error`, return `elements: []`. Callers
   render the message; they never see a traceback. This mirrors how
   `ifc_quality/validator.py` already reports `{"valid": False, "error": ...}`.
3. **Parsing never writes.** No Supabase writes, no storage mutation. Session A
   owns writes; Session B is pure read → transform.
4. **`source_sha256` is how a re-parse is avoided.** `resolve_analysis_ifc()`
   already keys model lineage on the source sha256; reuse it rather than
   inventing a second cache key.

---

## 2. `AnalysisResult` — Sessions C/D output

The current pipeline result is the dict returned by
`BIMGuard_App.orchestrate_workflow()` in `app/modules/orchestrator.py`. Sessions
C and D consume and extend it. The keys that matter across the boundary:

| Key | Type | Notes |
| --- | --- | --- |
| `project` | `dict` | The projects row |
| `analysis_theme` | `str` | `"Architecture"` \| `"MEP"` |
| `ifc_element_count` | `int` | From `ParsedIFC.element_count` |
| `ifc_type_counts` | `dict[str, int]` | |
| `ifc_error` | `str \| None` | Non-`None` ⇒ render the error, skip result cards |
| `ifc_quality_warnings` | `list[str]` | |
| `audit_issues` | `list[Issue]` | **The findings.** See §3 |
| `bcf_topics` | `list[dict]` | Session E's input |
| `issue_stats` | `dict` | Counts by band |
| `cost_impact` | `dict` | |
| `compliance_is_demo` | `bool` | `True` ⇒ UI must label output as synthetic |
| `compliance_error` | `str \| None` | Engine failed; other keys may be empty |

### Rules — AnalysisResult

1. **Additive only.** Adding a key is safe; renaming or removing one breaks
   every consumer. Session D adds seismic keys alongside the corrosion ones —
   it does not branch the dict into two shapes.
2. **Errors are values, not exceptions.** `ifc_error` and `compliance_error`
   carry failure across the boundary. A route renders whichever is set. This is
   the pattern Phase 5's landing pages already use for a missing model.
3. **`compliance_is_demo` must be honoured.** Synthetic output
   (`generate_synthetic_elements`) reaching a report unlabelled is a
   correctness bug, not a cosmetic one.

---

## 3. `Issue` — the finding contract

**Already defined.** `app/modules/module4_comparator/issue_schema.py`, whose
own docstring reads *"Data contract between Module4 (comparators) and Module5
(reporter)"*. `SCHEMA_VERSION = "1.0.0"`.

Session D does **not** create a `SeismicIssue`. The schema is deliberately
mechanism-agnostic: every domain emits the same shape, differentiated by the
`mechanism` string and mechanism-specific values in `metadata`.

```python
Issue(
    id="BGR-0007",                 # human-readable, allocated by IssueIdAllocator
    element_id="<IFC GUID>",       # FK to ServiceElement.guid
    rule_id="GC-001.03",
    title="...",
    band=RiskBand.HIGH,
    score=0.71,                    # 0.0–1.0 composite
    mechanism="GC-001 galvanic",   # Session D: "SB-001 seismic bracing", etc.
    mitigation="...",
    metadata={...},                # mechanism-specific detail
    citations=[{"standard": "NASA-STD-6012", "clause": "Table 2",
                "reason": "voltage threshold 0.25V in normal environment"}],
)
```

> **Contract — citations are not optional.** The White Box Architecture audit
> trail requires every issue to name the standard and clause that produced it.
> `tests/test_cross_material.py::TestAuditTrail` and
> `tests/test_material_media.py::TestAuditTrail` already enforce this for
> corrosion; Session D is expected to add the equivalent for seismic.

---

## 4. Status mappings — score → band

### 4.1 The engine mapping

`band_from_score(score, thresholds)` in `issue_schema.py` is the **only**
sanctioned score → band conversion. Do not write comparison chains inline.

Thresholds are the **lower bound** of each band and come from the rulepack, not
from constants — `galvanic.py` requires a `risk_band_thresholds` key. The
defaults in use are:

```python
{"medium": 0.35, "high": 0.65, "critical": 0.85}
```

| Score | Band | `RiskBand` value |
| --- | --- | --- |
| `< 0.35` | Low | `"low"` |
| `0.35 ≤ s < 0.65` | Medium | `"medium"` |
| `0.65 ≤ s < 0.85` | High | `"high"` |
| `≥ 0.85` | Critical | `"critical"` |

Session D supplies its own `risk_band_thresholds` in the seismic rulepack. It
must not hard-code different cut-points in Python.

### 4.2 Casing — the band trap

**Three** casings of the same four values are live in this codebase
simultaneously. They are not interchangeable, and every mismatch between them
fails *silently* — no exception, no log, just a wrong colour or a wrong severity.

| # | Casing | Who produces it | Site |
| --- | --- | --- | --- |
| 1 | `Critical` Title | the corrosion/crevice/MIC engines | `app/engines/bimguard_*_engine.py` |
| 2 | `LOW` UPPER | `compliance_runner` fallback when a result carries no band | `compliance_runner.py:214` (`.get("band", "LOW")`) |
| 3 | `critical` lower | `RiskBand` enum — storage, BCF, `Issue` | `issue_schema.py` |

`_band_int()`'s own docstring records the drift: *"Engines emit Title-case
labels ("Low", "Critical"); the band is normalised to upper case so any casing
ranks correctly."*

#### The four silent failure modes

**1 — `_band_badge` greys out.** `app/routes/analyze.py:754` is an exact dict
lookup keyed on **Title-case**, with a grey fallback:

```text
_band_badge("Critical") -> bg-red-600     correct
_band_badge("critical") -> bg-gray-400    GREY, no error
```

A lowercase `RiskBand` value reaching the UI renders grey. It looks like a CSS
glitch, so it gets triaged as a styling bug rather than a data-flow bug. Note
the direction: **lowercase is what breaks here**; Title-case is the correct key.

**2 — `_band_int` silently ranks unknown as safest.** It *is* defensive
(`.upper()` accepts all three casings) but returns `0` for anything
unrecognised — the same rank as `LOW`. A typo or a new band label does not
raise; it demotes the finding to lowest severity in dominance ordering.

```text
_band_int("critical") = 3   _band_int("Critical") = 3   _band_int("CRITICAL") = 3
_band_int("nonsense") = 0   <- ranks LOWEST, silently
```

**3 — `RiskBand` is a `str` subclass, so wrong-case comparison is just `False`.**

```python
RiskBand.CRITICAL == "critical"   # True
RiskBand.CRITICAL == "Critical"   # False — no error, the branch never fires
```

A capitalised `==` against a `RiskBand` never matches and never complains.

**4 — Sorting band values alphabetically inverts severity.** `_BAND_RANK` in
`issue_adapter.py` carries the warning; the effect is worth seeing:

```python
sorted(["critical","low","high","medium"])   # ['critical','high','low','medium']  WRONG
max(["critical","low","high","medium"])      # 'medium'  <- a Critical demoted to Medium
```

Never `sort`, `max` or `min` on raw band strings.

#### The pattern to copy

`issues_from_path_a()` in `app/modules/module4_comparator/issue_adapter.py`
already does this correctly and is the reference implementation:

```python
# Normalise "CRITICAL" -> RiskBand.CRITICAL -> "critical".
try:
    band = RiskBand(band_str.strip().lower())
except ValueError:
    raise ValueError(
        f"Unknown band '{band_str}' for {element_name} / {mechanism_code}"
    ) from None
```

Two properties make it right, and both matter:

1. **One normalisation point.** `.strip().lower()` into the enum, at the
   boundary where external band strings enter the `Issue` world.
2. **It raises.** An unrecognised band is a `ValueError` naming the element and
   mechanism — not a grey badge, not a rank of 0.

For ordering, use `_BAND_RANK` (or `_band_int()` in `compliance_runner.py`),
never an ad-hoc dict and never string comparison.

> **Contract**
>
> - `RiskBand` members — not strings — are the currency between layers. Compare
>   members; convert to `.value` only at a serialisation boundary.
> - Normalise **once, on entry**, with `RiskBand(s.strip().lower())`, and let it
>   raise. Do not normalise defensively at each use site; that is how three
>   casings became normal.
> - Title-case exists **only** inside the render call. Never persist, export, or
>   compare it.
> - Never `sort`/`max`/`min` raw band strings.

#### What Sessions C and D should fix

This section documents the trap; it does not change the code. Two follow-ups
belong to the sessions that own those files:

- **Session C (`phase-7-corrosion-ui`)** owns `app/routes/analyze.py`. Make
  `_band_badge` normalise its input through `RiskBand` and render from the
  member, rather than exact-matching a Title-case key with a grey fallback. Its
  call site at `analyze.py:855` defaults to `"Low"` — a Title-case literal that
  should become `RiskBand.LOW`.
- **Session D (`phase-8-seismic`)** must not add a fourth casing. Seismic bands
  are `RiskBand` members from the moment they leave the engine. Route them
  through the `issues_from_path_a` normalisation pattern, not around it.

Both are behaviour changes to shipped UI, so each deserves its own commit with a
test that asserts an unknown band now fails loudly instead of rendering grey.

> **Not a band:** `HIGH`/`MEDIUM`/`LOW` in
> `app/modules/module1_doc_parser/` are rule-extraction **confidence** levels, a
> separate concept with its own scale. Do not feed them to `_band_badge`,
> `_band_int` or `RiskBand`.

### 4.3 Issue workflow status

Distinct from band. `IssueStatus = Literal["open", "assigned", "in_review", "closed"]`,
default `"open"`. Lowercase, same rule as bands.

---

## 5. Testing patterns

Follow what the suite already does. `tests/conftest.py` is the reference.

### 5.1 The live-database rule — read this before writing a test

**The suite runs against the live Supabase project.** There is no test double
and no transactional rollback. `tests/test_routes.py` states it plainly: a test
that creates a project leaves it there.

> **Contract:** tests never create, update, or delete real records. Drive
> mutating routes with empty or malformed form data that handlers reject before
> touching persistence, and use a `NONEXISTENT_ID` for any id in a mutating
> path. Anything needing real writes belongs in a manual walkthrough.
>
> If you must write during a manual check, delete what you created in the same
> script and assert the deletion — a verification that leaves rows behind is a
> verification that failed.

### 5.2 Fixtures over engine runs

Domain fixtures in `conftest.py` (`path_a_results`, `mock_element`,
`allocator`) are built by hand rather than by running the engines, "so the band
under test is the band asserted". Include a compliant row alongside failures so
a projection keeps a denominator instead of only listing findings.

### 5.3 Subprocess probes for package-wide sweeps

Anything importing large parts of `app` runs in a child interpreter via the
`run_probe` fixture — module-level database clients and settings singletons
would otherwise leak into whatever test ran next.

### 5.4 The two import registries

- `KNOWN_IMPORT_FAILURES` — never imported in a plain checkout; environmental,
  not regressions.
- `IMPORT_REGRESSIONS` — imported at the baseline commit and stopped. **Must
  shrink to empty.** Each entry has a strict-xfail test, so repairing a module
  makes it XPASS and fails the run until the entry is deleted. The registry
  cannot rot into an allowlist.

> **Contract:** a new module that cannot import does not get added to a
> registry. Fix it.

### 5.5 Known-gap tests

Several routes answer `200` for ids that do not exist. Those are marked
`xfail(strict=False)` and named for the behaviour they *want*. When a route is
fixed the xfail flips to XPASS — the signal to remove the marker.

### 5.6 Running the suite

`pyproject.toml` sets `testpaths = ["app/modules/tests"]`, so a bare `pytest`
does **not** run `tests/`. Run both explicitly:

```bash
uv run pytest tests/ -q          # route, contract and regression suite
uv run pytest -q                 # app/modules/tests (unit)
```

Baseline at `2d7d80c`, for comparison when judging whether a failure is yours:

```text
tests/            16 failed, 352 passed, 2 skipped, 13 xfailed, 54 errors
```

The 16 failures are a known corrosion-comparator `compare()` signature
mismatch; the 54 errors are a missing spaCy model
(`uv run python -m spacy download en_core_web_sm`). Measure against this
baseline rather than assuming a red suite is pre-existing.

---

## 6. Conventions that apply to all five sessions

1. **Dependencies via `uv` in `pyproject.toml`.** No `requirements.txt`.
2. **PEP 257 docstrings** on new public modules, classes and functions, in the
   same change.
3. **UI through MonsterUI components**, wrapped in `DashboardLayout` with a
   `Title`. Route files compose; repeated markup moves into `app/components/`.
   See `.github/instructions/project-specific.instructions.md`.
4. **File uploads** go through `ObjectStorage.save_upload(...)`; local disk is
   only a cache for downloaded Supabase objects. Session A owns this path.
5. **Client document categories** come from `DOCUMENT_CATEGORIES` in
   `app/constants.py`; custom standard uploads are limited to
   `STANDARD_UPLOAD_EXTENSIONS` (`.pdf`, `.docx`).
6. **UTF-8, no BOM.** `app/constants.py` was corrupted twice by a Latin-1
   round-trip (`Côte d'Ivoire` → `C├┤te`). Check before committing:

   ```bash
   python -c "d=open('app/constants.py','rb').read(); \
   assert not d.startswith(b'\xef\xbb\xbf'); d.decode('utf-8')"
   ```

---

## 7. Boundary checklist

Before merging a Phase 6+ branch:

- [ ] No new score → band comparison chain; `band_from_score` used
- [ ] Band values lowercase outside the render call
- [ ] Every `Issue.element_id` resolves to a `ServiceElement.guid`
- [ ] Every `Issue` carries at least one citation
- [ ] Failures surfaced as `*_error` values, not raised across the boundary
- [ ] `AnalysisResult` keys added, none renamed or removed
- [ ] No test creates, updates or deletes a live record
- [ ] `IMPORT_REGRESSIONS` still empty
- [ ] `uv run pytest tests/ -q` no worse than the baseline above
- [ ] New/changed public functions have docstrings
- [ ] Touched files are UTF-8 without BOM
