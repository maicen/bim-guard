# Integration plan — wiring MM-001 and XM-001 into the live pipeline

**Status:** work order. No code in this plan has been written; `app/` was not touched while it was
drafted. Every file path, function name, line reference and result-dict key below was read from the
tree at commit `2701563` and is accurate as of that commit.

**Audience:** the session that performs the integration. Read sections 1–3 before writing anything;
they contain four blockers that change the order of the work.

---

## 1. What exists today

Two comparator paths coexist. They have different inputs, different outputs, and only one of them
reaches a user.

| | **Path A — live** | **Path B — dormant** |
|---|---|---|
| Element model | `ServiceElement` (`ifc_parser.py`) | `PipingElement` (`piping_schema.py`) |
| Producer | `parse_ifc_model(ifc_file)` | `produce_piping_elements(ifc_path)` |
| Engines | GC-001, CC-001, MC-001 (`app/engines/`) | MM-001, XM-001 (`comparator/`) |
| Runner | `run_compliance_checks(elements) -> list[dict]` | `compare(elements, rule_pack) -> list[Issue]` |
| Output shape | one flat dict **per element**, 30+ keys, always emitted | `Issue` dataclass, emitted **only when there is a finding** |
| Banding | `"LOW"/"MEDIUM"/"HIGH"/"CRITICAL"` strings | `RiskBand` enum, lowercase values |
| Reaches the UI | yes, via `orchestrate_workflow()` | no |

**Path A entry point.** `BIMGuard_App.orchestrate_workflow()` (`app/modules/orchestrator.py:293`)
opens the IFC once through `IFCReader`, and when `analysis_theme == "MEP"` calls
`parse_ifc_model(m2_reader.ifc_file)` then `run_compliance_checks(elements)`
(`orchestrator.py:424`). Results are band-normalised to Title case, counted into `issue_stats`, and
returned under `compliance_results`. `app/routes/analyze.py::_compliance_card` renders them.

**Path B entry point.** None. `material_media.compare()` and `cross_material.compare()` have no
caller outside `tests/`.

### The shape mismatch, concretely

Path A, per element, always:

```python
{"guid": ..., "name": ..., "floor": ..., "material_a": ..., "material_b": ...,
 "galvanic_score": 0.42, "galvanic_band": "MEDIUM", "voltage_gap_V": 0.31,
 "crevice_score": ..., "mic_score": ...,
 "overall_score": 0.42, "overall_band": "MEDIUM", "dominant_mechanism": "galvanic",
 "action": "Flag — ...", "mitigation": "...", "risk_band": "Medium"}   # risk_band added by orchestrator
```

Path B, per **finding**:

```python
Issue(id="XM-0003", element_id=<IFC GUID>, rule_id="XM-001.02",
      title=..., band=RiskBand.HIGH, score=0.71, mechanism="XM-001 cross-material",
      mitigation=..., assignee_role=..., status="open",
      metadata={...}, citations=[{"standard": ..., "clause": ...}])
```

Three structural differences drive the whole adapter design:

1. **Cardinality.** Path A is one row per element whether or not anything is wrong. Path B is zero
   or more Issues per element — and XM-001 is per *couple*, so one Issue references two elements.
2. **Absence semantics.** A compliant element is a `"LOW"` row in Path A and *nothing* in Path B.
   Merging naively would make every compliant element look unassessed by MM/XM.
3. **Identity.** Both key on the IFC GUID (`ServiceElement.guid`, `PipingElement.id`), so the join
   key exists and needs no invention. This is the one thing that is already right.

---

## 2. Blockers found while reading — resolve these first

These are not risks; they are present-tense defects verified at `2701563`.

### B1 — `ComplianceOrchestrator` does not import

`app/modules/comparator/compliance_orchestrator.py:8`:

```python
from app.modules.comparator.compliance_runner import run_compliance
```

`compliance_runner.py` defines `run_compliance_checks`. There is no `run_compliance`. The module
raises `ImportError` on import, so `ComplianceOrchestrator`, its `_results_to_issues()` adapter,
its `IssueTracker` logging and its `BCFExporter` call have never run.

This matters because `_results_to_issues()` is **a Path A → Issue adapter that already exists**. It
is the obvious base for the adapter in section 4 — but it is untested code, and its band mapping,
`BGR-%04d` id scheme and mechanism-inference chain all need review rather than adoption.

**Fix:** rename the import to `run_compliance_checks`, or add an alias in `compliance_runner.py`.
Decide which name is canonical and use only it. Do this before anything else; it unblocks B2 and B4.

### B2 — `/reports/bcf/{project_id}` never generates a BCF

`app/routes/analyze.py:3367`:

```python
bcf_file = os.path.join(_DATA_DIR, f"compliance_project_{project_id}.bcf")
if not os.path.exists(bcf_file): return Alert("BCF file not found. Run the analysis first ...")
```

It reads a file from disk and nothing in the current code path writes one. The two files that exist
(`data/compliance_project_1.bcf`, `_3.bcf`) came from a predecessor pipeline. The button's error
text tells the user to run an analysis, which will not produce the file.

**Consequence for this work:** "add MM/XM to the BCF export" is not an edit to a working exporter.
The generation step has to be built (section 6). Budget for that, not for a mapping tweak.

### B3 — `produce_piping_elements()` opens the IFC a second time

Signature (`piping_producer.py:1027`):

```python
def produce_piping_elements(ifc_path: str, *, adjacency_tolerance_m: float = 0.05) -> list[PipingElement]
```

It takes a **path** and calls `ifcopenshell.open()` itself. `orchestrate_workflow()` has already
opened the same file via `IFCReader`. Calling it as-is doubles IFC ingestion.

This is not a theoretical cost. The benchmark in `docs/benchmarks/halo_performance_analysis.md`
measures ingestion at a median **33.2 elements/s** and **98.6% of end-to-end wall-clock** on the
1 000-element scenario (n = 7). Doubling it doubles the dominant cost of the whole analysis.

**Fix:** add a model-accepting overload and keep the path form as a thin wrapper (section 8, F2).

### B4 — the XM-001 rule pack is DRAFT, and its loader needs the database

`data/rulesets/xm_001_cross_material.json` carries `"status": "DRAFT - NOT APPROVED FOR USE"`.
MM-001 carries `"status": "APPROVED v1.0"` with a named approver.

Separately, `cross_material.load_rule_pack()` calls `load_gc_catalog()`, which reads the Supabase
static asset `ruleset:BIMGUARD-GC-001`, and raises `RuntimeError` if the series is missing. So XM-001
cannot produce a finding without database access, while MM-001 can run entirely from disk.

**Consequence:** MM-001 and XM-001 must not be wired on the same switch. MM-001 can go live behind a
feature flag; XM-001 must stay behind a second flag that defaults off until the pack is approved,
and its loader failure must degrade to "not assessed", never to an empty result that reads as "no
couples found". Section 5 specifies this.

### Known issues — recorded, not scheduled

Present-tense defects found while implementing the numbered steps, each verified at the commit
noted. None is scheduled, and none blocks the step it surfaced in — they are recorded here so the
work that does touch this code inherits the knowledge rather than rediscovering it. Grouped by the
step that surfaced them.

**From F1 (B1 fix), verified at `4edba3a`.** Both are in `compliance_orchestrator.py` and both are
**downstream of B1**: the module has never imported, so neither has ever executed. Neither is
scheduled because section 8 already rules that this file is not extended beyond F1 — it is
rewritten on top of the F4 adapter, or deleted.

- **Mechanism inference is case-mismatched against the runner, silently voiding every citation.**
  `compliance_runner.py:174-182` emits `dominant_mechanism` lowercase (`"galvanic"`, `"crevice"`,
  `"mic"`); `_results_to_issues()` compares against `"Galvanic"` / `"Crevice"` / `"MIC"`
  (`compliance_orchestrator.py:58-63`, and again at `:73-78` for citations). Confirmed by calling the
  adapter directly with a runner-shaped dict: `dominant_mechanism="galvanic"` yields
  `rule_id="UNKNOWN.01"`, `mechanism="UNKNOWN galvanic"`, `assignee_role="Lead Engineer"` and
  `citations=[]`. Every issue lands unattributed, so a BCF built from this path would carry no
  standards reference at all — the failure is silent, not an exception. This is the concrete instance
  of the "mechanism-inference chain needs review rather than adoption" warning in B1; F4 must key off
  a shared constant, not repeated string literals.
- **The `__main__` smoke-test block raises `KeyError` on its last line.**
  `compliance_orchestrator.py:158` reads `result['summary - compliance_orchestrator.py:158']`, but
  `run_and_log_compliance()` returns keys `issues` / `run_name` / `timestamp` / `summary` /
  `bcf_path`. An editor or logging artifact was pasted into the subscript. The block is also the only
  caller of the hardcoded IFC path `data/uploads/ifc/f4c3f1b8...Infra-Plumbing.ifc`, so it is not a
  usable smoke test regardless — delete it with the file, or replace it with the F13/F14 tests.

**From F3 (MM-001 loader), verified at `4edba3a` plus the F3 working tree.** Both are consequences
of adding `load_rule_pack()` to `material_media.py`, not defects in it. Neither affects MM-001
behaviour today; both are maintenance hazards the F4/F6 wiring will touch.

- **`MM_PACK_PATH` is now defined twice, in both comparators.** F3 added it at
  `material_media.py:67`; `cross_material.py:67` already carried the same literal, which it reads at
  `:139` to borrow MM-001's `environment_severity` (see 4.1). Two copies of one path is drift
  waiting to happen: move the pack file and one comparator keeps working while the other stops.
  `material_media.py` is the correct owner, so `cross_material.py` should import the constant from
  it rather than restate it. Not done in F3 because F3's scope was additive — editing
  `cross_material.py` would have put a second module in the diff for no functional gain.
- **Ruleset paths are CWD-relative, and the project already has the fix elsewhere.**
  `Path("data/rulesets/...")` resolves against the working directory, not the repo, so every caller
  must be launched from the repository root. Five call sites share the pattern:
  `material_media.py:67`, `cross_material.py:66-67`, `bert_classifier.py:319-320`. This is fragile
  rather than wrong — it works today because uvicorn is started from the root — but it breaks any
  test runner, cron job or worker with a different CWD, and the failure is a bare
  `FileNotFoundError` far from the cause. F3's loader raises a message naming the CWD assumption,
  which mitigates the symptom, not the cause. Note that `analyze.py:58` already anchors `_DATA_DIR`
  off `__file__` — the convention exists in the codebase and these call sites simply predate it.
  The fix is one shared root constant, applied to all five; it is a cross-cutting change and does
  not belong inside an MM/XM feature step.

**From F7 (Path B feature flags), verified at `4edba3a` plus the F7 working tree.** This one is a
binding design constraint on F6, not a cleanup item — read it before wiring the orchestrator.

- **The Path B flags carry a database dependency, and deferring the import does not shed it.**
  `config.py:13` runs `_settings = SettingsService()` at module level; that constructs
  `StaticDataService()`, which calls `PersistenceService.get_table()` and raises
  `ValueError("SUPABASE_URL is required")` with no database. So **any** module that reads
  `FEATURE_PATH_B_MM` through `app.modules.config` inherits a Supabase requirement — which lands
  squarely on MM-001, whose distinction from XM-001 (B4) is that it runs offline from disk. The
  gate would defeat the property it gates.

  Moving the import inside `orchestrate_workflow()` is **necessary but not sufficient**, and this
  is the part that is easy to get wrong. A function-level `from app.modules.config import
  FEATURE_PATH_B_MM` still executes the module body on first import; it relocates the failure from
  process start to the moment the MEP branch runs, and MM-001 remains unable to run without a
  database. Measured with `SUPABASE_*` unset: the enclosing module imports cleanly, then the call
  raises `ValueError: SUPABASE_URL is required`. Deferring buys a later, more confusing failure —
  not an offline path.

  F6 therefore needs one of these, not merely a deferred import:
  1. **Read the environment directly in the MEP branch**, bypassing `config.py`:
     `os.environ.get("FEATURE_PATH_B_MM", "0") == "1"`, held in a local. Verified offline: the flag
     reads `True` and `load_rule_pack()` returns `BIMGUARD-MM-001` with no database present. Costs
     the DB-backed settings override for these two keys.
  2. **Make `config.py` lazy** — build `_settings` on first use behind a helper rather than at
     import. Keeps the settings override and fixes the problem for every future flag, but it edits
     a module the whole pipeline imports, so it wants its own step and its own test.
  3. **Tolerate the failure** — read through `config.py` inside a `try/except` that falls back to
     the environment. Preserves the override where a database exists and degrades where it does
     not; the cost is a swallowed exception that hides genuine misconfiguration.

  Option 1 is the smallest change that keeps MM-001 offline and is the recommendation for F6.
  Whichever is chosen, XM-001 is unaffected — it needs the database anyway for the GC-001 series,
  so reading its flag through `config.py` costs it nothing.

---

## 3. Decisions to make before writing code

| # | Decision | Recommendation |
|---|---|---|
| D1 | Merge Path B into Path A dicts, or lift Path A into Issues? | **Lift Path A into Issues.** `Issue` is the declared "data contract between Module4 and Module5" (`issue_schema.py:4`) and already carries citations, assignee and workflow state that the dicts cannot express. Adapting the other direction would flatten MM/XM citations away — the audit trail the white-box claim rests on. |
| D2 | Then how does the existing UI keep working? | Add a **projection** back to the dict shape for the current card (section 4.2). The card keeps its keys; nothing in `analyze.py` breaks on day one. |
| D3 | One Issue per couple (XM) or two? | **Already settled in the engine — do not change it.** `cross_material._finding()` emits one Issue with `element_id = anode.id` and both GUIDs in `metadata` (`anode_id`, `cathode_id`). The anode is the element that corrodes, so it is the right subject. The work is to make the UI and BCF surface *both* ends; the data is already there. |
| D4 | Do MM/XM contribute to `overall_band`? | **Not initially.** Keep `overall_band` as the GC/CC/MC composite it is today and add a separate `path_b_band`. Folding a DRAFT pack into the headline band changes existing numbers with no way to tell which engine moved them. Revisit once XM-001 is approved. |
| D5 | Where do Issue ids come from? | A single allocator, not per-engine counters. **Three separate code paths currently mint `BGR-%04d` from a counter starting at zero**: `material_media._finding()`, `cross_material._finding()`, and `ComplianceOrchestrator._results_to_issues()`. A run using two of them emits two `BGR-0001`. Ids must be unique per run for BCF topics and `IssueTracker` keying. Section 4.3. |

---

## 4. The adapter

New module: `app/modules/comparator/issue_adapter.py`. It is the only place that knows both
shapes.

### 4.1 Path A dicts → Issues

```python
def issues_from_path_a(
    results: list[dict],
    *,
    id_allocator: "IssueIdAllocator",
    include_low: bool = False,
) -> list[Issue]:
    """Convert run_compliance_checks() dicts into Issues.

    One Issue per element per mechanism that scored at or above its own band
    floor — not one per element. A dict carrying galvanic MEDIUM and crevice
    HIGH is two findings to a reviewer and must not collapse into one.

    Args:
        results: Dicts from run_compliance_checks().
        id_allocator: Run-wide id source; see IssueIdAllocator.
        include_low: Emit Issues for LOW-band mechanisms too. Default False,
            matching Path B, where a compliant element produces nothing.

    Returns:
        Issues in input order, mechanism order galvanic, crevice, MIC.
    """
```

Per-mechanism mapping, from the keys `run_compliance_checks()` actually emits:

| Mechanism | Band key | Score key | `rule_id` | `metadata` keys lifted |
|---|---|---|---|---|
| GC-001 galvanic | `galvanic_band` | `galvanic_score` | `GC-001.01` | `voltage_gap_V`, `voltage_threshold`, `pren_fail`, `anodic_material`, `material_a`, `material_b` |
| CC-001 crevice | `crevice_band` | `crevice_score` | `CC-001.01` | `crevice_geometry`, `cct_adequate`, `joint_type` |
| MC-001 MIC | `mic_band` | `mic_score` | `MC-001.01` | `mic_flow_class`, `mic_temperature_class`, `mic_dead_leg_class` |

Common fields: `element_id = r["guid"]`, `title = f"{rule_id.split('.')[0]} on {r['name']}"`,
`mitigation = r["mitigation"]`, `description = r["action"]`,
`band = RiskBand(r[band_key].lower())`, and `metadata["path"] = "A"` plus
`metadata["source_dict_keys"]` naming the keys consumed, so a reviewer can trace a projected value
back to its origin.

**Citations are the honest gap.** Path A dicts carry no citation data — `compliance_runner.py`
discards the engine's standards references before returning. `ComplianceOrchestrator`'s existing
adapter papers over this by hardcoding `NACE SP0169-2013` per mechanism (`compliance_orchestrator.py:74-79`),
which asserts a source the engine never named. **Do not copy that.** Emit
`citations=[]` and set `metadata["citations_unavailable"] = "path_a_runner_discards_engine_citations"`.
An empty list is a visible gap; a fabricated citation is a false audit trail, and this project's
whole claim is that the trail is real. Restoring citations means widening
`run_compliance_checks()` to carry them through — worth a follow-up issue, out of scope here.

### 4.2 Issues → the dict shape the current card expects

```python
def path_a_view(issues: list[Issue], base_results: list[dict]) -> list[dict]:
    """Project Issues back onto the per-element dicts the UI renders.

    base_results supplies the one-row-per-element spine, including compliant
    elements that produce no Issue. Path B findings are merged onto the row
    with the matching guid; unmatched Issues (an XM couple whose anode is not
    in base_results) are appended as their own rows.

    Adds per row: path_b_issues (list[dict]), path_b_band (str|None),
    path_b_count (int), mm_band, mm_score, xm_band, xm_score.
    Leaves every existing key untouched.
    """
```

The spine matters. Path A's one-row-per-element output is what makes "no elements flagged" a
statement about coverage rather than about silence. Building the table from Issues alone would lose
every compliant element and the denominator with it.

### 4.3 Id allocation

```python
class IssueIdAllocator:
    """Run-wide unique Issue ids with a per-mechanism prefix.

    material_media._finding(), cross_material._finding() and
    ComplianceOrchestrator._results_to_issues() all mint 'BGR-%04d' from a
    counter that starts at zero, so any run combining two of them produces
    duplicate ids. BCF needs one topic per id and IssueTracker keys on it, so
    allocation belongs to the run rather than the engine.
    """

    def __init__(self, run_id: str) -> None: ...
    def next(self, prefix: str) -> str:
        """Return the next id, e.g. 'MM-0003'. Prefix is the mechanism code."""
```

Engines keep their internal counters; the adapter **reassigns** `issue.id` on ingest, to
`MM-0003` / `XM-0007` / `GC-0011` style. Record the engine-local `BGR-` id in
`metadata["engine_local_id"]` so a test failure traces back to the engine that produced it.

Note that `rule_id` is already unique and descriptive — `MM-001.<material>.<media>` and
`XM-001.<anode_material>.<cathode_material>` — so it needs no rewriting; only `id` collides.

---

## 5. Where `produce_piping_elements()` gets called

Inside `orchestrate_workflow()`, in the existing `if selected_theme == "MEP":` block, **after**
`run_compliance_checks()` so a Path B failure can never take Path A down with it.

```python
# app/modules/orchestrator.py, inside orchestrate_workflow(), MEP branch

path_b_issues: list[Issue] = []
path_b_errors: dict[str, str] = {}
piping_elements: list[PipingElement] = []

if selected_theme == "MEP" and FEATURE_PATH_B_MM:
    try:
        piping_elements = produce_piping_elements_from_model(
            m2_reader.ifc_file, source_path=ifc_path
        )
    except Exception as exc:
        path_b_errors["producer"] = str(exc)

    if piping_elements:
        try:
            mm_pack = load_mm_rule_pack()
            path_b_issues += material_media.compare(piping_elements, mm_pack)
        except Exception as exc:
            path_b_errors["MM-001"] = str(exc)

        if FEATURE_PATH_B_XM:
            try:
                xm_pack = cross_material.load_rule_pack()
                if xm_pack.get("status", "").startswith("DRAFT"):
                    path_b_errors["XM-001"] = "rule pack is DRAFT — not approved for use"
                else:
                    path_b_issues += cross_material.compare(piping_elements, xm_pack)
            except Exception as exc:
                path_b_errors["XM-001"] = str(exc)
```

Four properties this shape guarantees:

- **Path A is never degraded by Path B.** Each stage is independently caught.
- **The IFC is opened once** — `m2_reader.ifc_file` is reused (blocker B3).
- **A DRAFT pack cannot silently produce verdicts** (blocker B4). The status check is in the
  orchestrator rather than inside `compare()` so the reason surfaces in the UI.
- **Failure is distinguishable from a clean result.** `path_b_errors` non-empty means "not
  assessed"; empty with zero Issues means "assessed, nothing found". The card must render these
  differently — conflating them is how a compliance tool reports a crash as a pass.

Two new keys on the return dict of `orchestrate_workflow()`:

```python
"path_b_issues": [to_dict(i) for i in path_b_issues],
"path_b_errors": path_b_errors,
"piping_elements_by_id": {e.id: e for e in piping_elements},   # BCF needs it (6.1)
```

The element lookup has to survive the call. `bcf_issues_from_issues()` needs `name`, `system`,
`level_name` and `centroid` off `PipingElement`, and the BCF download runs in a later request than
the analysis. Either cache it beside the existing `_last_*` module-level caches in `analyze.py`, or
re-derive it in the download handler — which costs a second full IFC ingestion, measured at roughly
30 s per 1 000 elements. Cache it.

Feature flags live in `app/modules/config.py` beside the existing constants:

```python
FEATURE_PATH_B_MM = _settings.get("FEATURE_PATH_B_MM", os.environ.get("FEATURE_PATH_B_MM", "0")) == "1"
FEATURE_PATH_B_XM = _settings.get("FEATURE_PATH_B_XM", os.environ.get("FEATURE_PATH_B_XM", "0")) == "1"
```

Both default **off**. Turn MM on once its projection renders; leave XM off until the pack is approved.

---

## 6. BCF export

Blocker B2 says there is no working generation path, so this is build-then-map.

### 6.1 Which writer

Two exist:

| Writer | Input | Output | State |
|---|---|---|---|
| `reporter/bcf_generator.py` | `list[BCFIssue]` via `issues_from_results(list[dict])` | full BCF 2.1 **ZIP** (markup + viewpoint + snapshot) | complete; snapshot is a 1×1 placeholder |
| `app/services/bcf_exporter.py` | `list[Issue]` | markup **XML only**, no ZIP | importable now (its old broken import is gone); no viewpoint, no ZIP |

**Use `bcf_generator.py`.** A BCF consumer expects a `.bcfzip`; markup XML alone is not a loadable
deliverable. Add an `Issue`-accepting adapter beside the existing `issues_from_results()` rather than
replacing it.

```python
# app/modules/reporter/bcf_generator.py

def bcf_issues_from_issues(
    issues: list[Issue],
    elements_by_id: dict[str, PipingElement],
) -> list[BCFIssue]:
    """Convert Path B Issues into BCFIssue records.

    Mirrors issues_from_results() but reads the Issue dataclass. Unlike that
    function, Low-band findings are retained: XM-001 sets report_all_couples,
    so a mitigated couple banded Low is a deliberate teaching finding, not
    noise to suppress.

    elements_by_id is required, not optional: BCFIssue needs component_name,
    service_type, floor and a camera position, and none of those are on the
    Issue. See the note below.
    """
```

**The Issue does not carry everything BCF needs.** The metadata each engine actually emits is
narrow and mechanism-specific — MM-001 writes `material`, `media`, `environment_class`,
`operating_temperature_c`, `material_media_score`, `environment_severity`, `temperature_stress`,
`kinetics_guard_applied`, `failure_mechanism`, `predicted_lifespan_years`, `cell_confidence`,
`cell_note`; XM-001 writes `anode_id`, `anode_material`, `cathode_id`, `cathode_material`,
`voltage_gap_v`, `voltage_risk`, `separation`, `separation_factor`, `environment_class`,
`environment_severity`, `mitigation`, `mitigation_factor`, `mitigated`.

Neither carries the element's **name, system, level or centroid**. Those live on `PipingElement`
(`name`, `system`, `level_name`, `centroid`). So the BCF adapter must be given the element lookup;
it cannot work from Issues alone. The alternative — widening both engines to duplicate element
attributes into every Issue — copies data that already has one home and invites it to drift.

### 6.2 Field mapping

`el = elements_by_id[issue.element_id]`; `md = issue.metadata`.

| `BCFIssue` field | MM-001 | XM-001 |
|---|---|---|
| `guid` | fresh `uuid4()` (BCF topic guid ≠ element guid) | same |
| `title` | `issue.title` | `issue.title` |
| `description` | `issue.description` + `"\n\nCitations: "` + rendered `issue.citations` | same |
| `priority` | `Minor/Normal/Major/Critical` from band | same |
| `status` | `Info/Open/Open/Active` from band | same |
| `assigned_to` | `issue.assignee_role` (both engines set `"Mechanical engineer"`) | same |
| `due_date` | today + `{Low:60, Medium:21, High:7, Critical:2}` days | same |
| `labels` | `["BIMGUARD-AI", f"Risk-{band}", "MM-001", md["material"], md["media"]]` | `["BIMGUARD-AI", f"Risk-{band}", "XM-001", md["anode_material"], md["cathode_material"]]` |
| `component_guid` | `issue.element_id` | `issue.element_id` (= `md["anode_id"]`) |
| `component_name` | `el.name` | `el.name` (anode) |
| `service_type` | `el.system.value` | `el.system.value` |
| `floor` | `el.level_name` | `el.level_name` |
| `risk_band` | `issue.band.value.upper()` | same |
| `mechanism` | `"material-media"` | `"cross-material"` |
| `risk_score` | `issue.score` | `issue.score` |
| `mitigation` | `issue.mitigation` | `issue.mitigation` |
| camera/target | `el.centroid` | anode `el.centroid` |

A missing `elements_by_id` entry must raise, not default. A BCF topic pointing at a component that
is not in the model is worse than no topic: it fails silently in the viewer, and the reviewer
concludes the issue was cleared.

**XM-001 needs a second component.** BCF supports multiple components per topic, and a galvanic
couple is inherently two elements. `_markup_xml()` currently emits one. Extend it to take a list;
for XM-001 pass `[md["anode_id"], md["cathode_id"]]` so both highlight in the viewer. Without this the
reviewer sees only half the couple, which is precisely the confusion the anode-convention defect
report is about.

### 6.3 Generation, and fixing the dead download

```python
# app/routes/analyze.py — replace the read-only handler at :3367

@rt("/reports/bcf/{project_id}")
def bcf_download(project_id: int):
    """Generate the BCF for the last analysis run and stream it."""
```

Take issues from the run cache (the module-level `_last_*` pattern already used at
`analyze.py:2002`), merge Path A and Path B BCFIssues, call `generate_bcf(...) -> bytes`, and return
a `Response` with `media_type="application/octet-stream"`. Keep the on-disk fallback for the two
legacy files so existing project ids still resolve, but generate in preference to reading.

---

## 7. Dashboard and asset register

### 7.1 Existing card

`_compliance_card()` (`analyze.py:719`) renders seven columns: Element, Floor, Material, Engine,
Band, Score, Required Action — filtered to `risk_band != "Low"`, capped at 20 rows.

Because the adapter projects Path B onto the same spine (4.2), **the existing table needs no change
to keep working.** Two additions, both additive:

1. Title becomes `"Corrosion Compliance — GC-001 / CC-001 / MC-001 / MM-001 / XM-001"`, with MM/XM
   badges added to `_mep_engine_rules_card()`'s `engines` list (`analyze.py:862`), following its
   existing `(code, name, ruleset_id, css)` tuple shape.
2. An **Engine** column value of `MM-001` / `XM-001` — it already renders
   `dominant_mechanism.upper()`, so the projection sets that key on appended Path B rows.

### 7.2 New Path B card

A second card, not a widened first one — the two paths have different evidence quality (Path A has
no citations, per 4.1) and merging them into one table implies parity they do not have.

```python
def _path_b_card(issues: list[dict], errors: dict[str, str], is_demo: bool):
    """Render MM-001 / XM-001 findings with their citation trail."""
```

Columns: **Element · Level · System · Mechanism · Band · Score · Anode → Cathode · Mitigation ·
Citations**. The last is the point of the card — MM/XM carry `citations[]` per finding and nothing
in the current UI displays a citation anywhere. Render as a count with the standards on hover, and
the full list in the detail panel.

Errors render above the table as a warning band: *"XM-001 not assessed: rule pack is DRAFT — not
approved for use."* Never as an empty table.

### 7.3 Asset register

There is no asset-register table or route — "asset register" appears only inside mitigation strings
(`compliance_runner.py:32`, `cost_model.py:172`, `schedule_impact.py:69`). The register is currently
a phrase, not a feature.

If it is in scope, the minimum is a CSV export beside `/reports/compliance-csv` (`analyze.py:3159`):

```python
@rt("/reports/asset-register-csv/{project_id}")
def asset_register_csv(project_id: int):
    """Every assessed element with its per-mechanism bands — including compliant ones."""
```

Columns: `guid, name, ifc_class, level, system, media, material, environment_class, joint_type,`
`gc_band, cc_band, mc_band, mm_band, xm_band, worst_band, worst_mechanism, open_issue_count,`
`mitigation, assessed_at, ruleset_versions`.

Two properties to preserve: it lists **every** element including compliant ones (that is what makes
it a register rather than a defect list), and `ruleset_versions` records which pack version produced
each verdict — without it a register row cannot be reproduced after a pack is amended.

### 7.4 Cost model

`CostModel._lookup_rate()` (`cost_model.py:273`) normalises via `mechanism.upper()[:2]`, so
`"MM-001"` → `"MM"` and `"XM-001"` → `"XM"`. Neither has rows, so both fall to the last-resort
£3 000 / 2 days with the text *"Remediation cost estimated — rate not found in model"*.

That is a silent wrong number on a commercial figure. Either add 8 rows (4 bands × 2 mechanisms) to
`DEFAULT_RATES`, or make the last-resort branch return `None` and have `calculate_impact()` report
unpriced findings separately. **Prefer the second**: an explicit "3 findings unpriced" is honest,
whereas a made-up £3 000 propagates into the cost total that §1.4.2 of the submission already flags
as unverified.

---

## 8. File-by-file change list

| # | File | Change | Signature |
|---|---|---|---|
| F1 | `comparator/compliance_runner.py` | Fix B1: export the canonical name | `run_compliance = run_compliance_checks` (alias) or rename at the import site |
| F2 | `ifc_reader/piping_producer.py` | Fix B3: accept an open model | `def produce_piping_elements_from_model(model: Any, *, source_path: str \| None = None, adjacency_tolerance_m: float = 0.05) -> list[PipingElement]` — existing `produce_piping_elements()` becomes a two-line wrapper that opens the path and delegates |
| F3 | `comparator/material_media.py` | Add the loader XM-001 already has | `def load_rule_pack(*, path: Path \| None = None) -> dict` — reads `data/rulesets/mm_001_material_media.json`, validates `_REQUIRED_KEYS`, raises `ValueError` naming the missing keys |
| F4 | **new** `comparator/issue_adapter.py` | The adapter | `issues_from_path_a(results, *, id_allocator, include_low=False) -> list[Issue]`; `path_a_view(issues, base_results) -> list[dict]`; `class IssueIdAllocator` |
| F5 | `comparator/issue_schema.py` | Nothing structural | Confirm `summarise()` counts by band for the new card; no schema change needed |
| F6 | `modules/orchestrator.py` | Call Path B (section 5) | `orchestrate_workflow()` gains the guarded block; returns `path_b_issues: list[dict]`, `path_b_errors: dict[str, str]` |
| F7 | `modules/config.py` | Feature flags | `FEATURE_PATH_B_MM: bool`, `FEATURE_PATH_B_XM: bool`, both default `False` |
| F8 | `reporter/bcf_generator.py` | Issue → BCF | `def bcf_issues_from_issues(issues: list[Issue], elements_by_id: dict[str, PipingElement]) -> list[BCFIssue]` — the lookup is required, see 6.1; extend `_markup_xml(issue, index, component_guids: list[str] \| None = None) -> str` for the XM couple |
| F9 | `routes/analyze.py` | Render + fix B2 | `def _path_b_card(issues: list[dict], errors: dict[str, str], is_demo: bool)`; rewrite `bcf_download(project_id: int)` to generate; add MM/XM to `_mep_engine_rules_card()` |
| F10 | `reporter/cost_model.py` | Stop inventing rates | `_lookup_rate(...) -> dict \| None`; `calculate_impact()` gains `unpriced_count: int` on `ImpactSummary` |
| F11 | **new** `routes/analyze.py` route | Asset register (if in scope) | `def asset_register_csv(project_id: int)` |
| F12 | `data/rulesets/xm_001_cross_material.json` | Gate | Leave DRAFT. Flip to APPROVED only via the Expert Review process in `docs/expert_review_process.md`, with `approved_by` recorded |
| F13 | **new** `tests/test_issue_adapter.py` | Cover F4 | see section 9 |
| F14 | **new** `tests/test_path_b_integration.py` | Cover F6 | see section 9 |

`compliance_orchestrator.py` is deliberately **not** in this list beyond F1. It duplicates the
adapter this plan puts in F4, hardcodes citations it should not, and has never executed. Once F4
lands, either rewrite it on top of the adapter or delete it — do not extend it.

---

## 9. Tests

Adapter (`tests/test_issue_adapter.py`):

| # | Assertion |
|---|---|
| A1 | A dict with galvanic MEDIUM and crevice HIGH yields **two** Issues, not one |
| A2 | A dict with every band LOW yields zero Issues by default, three with `include_low=True` |
| A3 | `RiskBand` round-trips: `"CRITICAL"` → `RiskBand.CRITICAL` → `"critical"` |
| A4 | Every Path A Issue has `citations == []` and the `citations_unavailable` marker — pins the honesty rule in 4.1 against a future "helpful" hardcode |
| A5 | `path_a_view()` preserves every key of every input dict (compare key sets before/after) |
| A6 | `path_a_view()` row count ≥ `len(base_results)`; compliant elements survive the merge |
| A7 | `IssueIdAllocator` emits no duplicate id across MM and XM findings in one run |

Integration (`tests/test_path_b_integration.py`), using the existing `piping_fixtures`:

| # | Assertion |
|---|---|
| I1 | With `FEATURE_PATH_B_MM=False`, `orchestrate_workflow()` returns `path_b_issues == []` and Path A results unchanged byte-for-byte against a recorded baseline |
| I2 | With MM on and a producer that raises, `path_b_errors["producer"]` is set and `compliance_results` is still populated — Path B cannot take Path A down |
| I3 | With XM on and the pack still DRAFT, `path_b_errors["XM-001"]` names the DRAFT status and no XM Issue is emitted |
| I4 | With XM on and `load_gc_catalog()` raising, the error is captured, not swallowed into an empty result |
| I5 | The IFC is opened exactly once per run — assert on a patched `ifcopenshell.open` call count. This is the regression guard for B3 |

BCF (`tests/test_bcf_path_b.py`): an XM Issue produces a topic with **two** components; a Low-band
XM Issue is retained (not filtered like Path A's Low rows); generated bytes open as a valid ZIP with
`markup.bcf` present.

---

## 10. Sequence

1. **F1** — fix the broken import. Nothing else can be tested until the module imports.
2. **F2, F3** — producer overload and MM loader. Both are self-contained and independently testable.
3. **F4 + F13** — the adapter, with its tests. This is the risk centre of the work; land it before
   any UI or export code depends on its shape.
4. **F6, F7 + F14** — orchestrator wiring behind flags, MM only. Verify I1–I5 with both flags off,
   then MM on.
5. **F9 (card only)** — render the Path B card. Turn `FEATURE_PATH_B_MM` on in a dev environment.
6. **F8 + F9 (BCF)** — build generation, fix the dead download (B2).
7. **F10** — cost-model honesty fix.
8. **F11** — asset register, if in scope.
9. **F12** — XM-001 approval through Expert Review; only then does `FEATURE_PATH_B_XM` default on.

Steps 1–4 are the integration proper; 5–9 are the surfacing. If the session runs short, stopping
after step 4 leaves the tree in a coherent state: Path B computes and is tested, nothing user-facing
has changed, and both flags are off.

---

## 11. What this plan does not decide

- **Whether MM/XM should influence `overall_band`.** Deferred by D4 until XM-001 is approved and
  its numbers have been seen against real models.
- **The anode-convention defect** (`docs/defects/defect_report_anode_convention.md`). XM-001 sidesteps
  it by reading the `noble` flag rather than the potential sign, so this integration is not blocked
  by it — but if the live GC-001 engine is found to name the wrong material, Path A's
  `anodic_material` key, which the adapter lifts into `metadata`, inherits that defect. Re-check
  after that report is resolved.
- **Restoring citations to Path A.** Named as a follow-up in 4.1, not scoped here.
- **Whether `compliance_orchestrator.py` is rewritten or deleted.** Decide once F4 exists.
