# BIMGUARD AI — Data Architecture (Reverse-Engineered)

Produced by reading the code, not the documentation. Where the two disagree,
this document follows the code and says so.

**The two findings that matter most for frontend work, stated up front:**

1. **Analysis results are never persisted.** `orchestrate_workflow()` returns a
   plain `dict` that the route renders straight to HTML and discards. Reload the
   page and the analysis is gone. There is no results table, no cache, no job id.
2. **There is no session state.** What looks like per-user state is a handful of
   module-level globals, shared process-wide across every visitor.

---

## 1. Repository Structure

```
D:\Zigurat Masters\bim-guard\
├── main.py                     entry point — uvicorn boot only
├── app/
│   ├── main.py                 FastHTML app, route registration, middleware
│   ├── environment.py          .env discovery and loading
│   ├── utils.py                md5, upload naming, redirect helpers
│   ├── routes/                 HTTP handlers — thin, no HTML
│   │   ├── analyze.py          138 KB — compliance workflow + reports
│   │   ├── library.py           44 KB — documents + rules
│   │   ├── revit_sync.py         8 KB
│   │   ├── projects.py           6 KB — project CRUD, IFC download
│   │   ├── viewer.py             4 KB — 3D viewer page
│   │   ├── dashboard.py          3 KB
│   │   ├── settings.py           3 KB
│   │   └── modeling_manual.py    1 KB
│   ├── components/             where HTML is actually built
│   │   ├── rules_ui.py          67 KB
│   │   ├── rule_extraction_ui.py 28 KB
│   │   ├── projects_ui.py       10 KB
│   │   ├── layout.py             7 KB — DashboardLayout, AppSidebar, AppHeader
│   │   ├── documents_ui.py       4 KB
│   │   ├── themed_ui.py          2 KB
│   │   └── ui.py                 shadcn-style primitives
│   ├── services/               persistence and I/O
│   │   ├── persistence.py       Supabase client + in-memory fallback
│   │   ├── db_adapters.py       SupabaseTableAdapter (table-like API)
│   │   ├── object_storage.py    Supabase Storage + local materialisation cache
│   │   ├── projects_service.py  documents_service.py  rules_service.py
│   │   ├── settings_service.py  model_lineage.py  rule_extraction_service.py
│   │   └── revit_sync_service.py
│   ├── modules/                the compliance pipeline
│   │   ├── orchestrator.py      BIMGuard_App.orchestrate_workflow()
│   │   ├── pipeline_services.py execute_model_enhancement()
│   │   ├── document_parsing/  PDF → text → sections → candidate rules
│   │   ├── nlp_annotation/
│   │   ├── ifc_reader/    IFC parsing, geometry, spatial, egress, piping
│   │   ├── module2_producer/    Blue Halo clearance algorithm
│   │   ├── rule_builder/
│   │   ├── comparator/  corrosion engines + Issue contract
│   │   └── reporter/    BCF 2.1, cost model, report generator
│   └── engines/                 GC/CC/MC reference implementations
├── data/
│   ├── cache/supabase-storage/  local materialisation of remote objects
│   ├── uploads/ifc/             legacy local uploads
│   ├── rulesets/                versioned JSON rule packs
│   ├── validation_models/       1.4 GB corpus (gitignored)
│   ├── validation_results/      per-model sweep JSON
│   └── validation_bcf/          404 MB BCF output (gitignored)
├── supabase/migrations/         the schema of record — 11 SQL files
├── tests/                       20 files, 277 test functions
├── static/                      css/globals.css, js/, lib/web-ifc.wasm
└── .env                         SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

---

## 2. App Initialization

**`main.py`** does nothing but boot:

```python
from app.compat.monsterui import ensure_monsterui_compat
ensure_monsterui_compat()          # patch must run before app import
from app.main import app
uvicorn.run("app.main:app", host="0.0.0.0", reload=True, log_config=None)
```

**`app/main.py`** builds the FastHTML app, registers every route module's
`setup_routes(rt)`, and adds `PageLoadLoggingMiddleware`. **65 routes** register.
Import cost is ~15 s, dominated by the MonsterUI compat shim and service
construction.

### Storage: Supabase, not SQLite

`CLAUDE.md` is correct and the task brief's assumption is not:

- **No FastLite.** No import anywhere.
- **No SQLite.** No `.db`/`.sqlite` file exists in the repo. `.gitignore`
  mentions `data/bimguard.sqlite-wal`, which is a leftover from a previous
  design; the analytics repo's `data/samples/bimguard.sqlite` is sample data,
  not this app's store.
- **Supabase Postgres** via `supabase.create_client`, wrapped by
  `SupabaseTableAdapter` to present a table-like API (`get`, `insert`,
  `update`, `delete`, `rows_where`).
- **In-memory fallback.** `persistence.py` defines `_MemoryClient` /
  `_MemoryTable` / `_MemoryQuery` mimicking the Supabase client, used when no
  credentials are configured. **State is per-process and lost on restart** —
  useful for tests, not a deployment mode.

Objects (IFC, PDF) go to **Supabase Storage** under UUID-prefixed keys, with a
transparent local cache at `data/cache/supabase-storage/` so parsing does not
re-download on every request.

---

## 3. IFC Upload & Analysis Flow

### 3a. Upload

| Step | Location | Data |
|---|---|---|
| Form POST | `routes/projects.py :: projects_create` | `UploadFile` |
| Validate + hash | `services/projects_service.py :: prepare_ifc_upload` | rejects non-`.ifc`, computes MD5 |
| Store | `services/object_storage.py :: save_upload` | writes `{uuid}_{name}`, returns `sb://bucket/key` |
| Record | `projects_service.create_project` | row in `public.projects` |
| Respond | `utils.redirect_see_other("/projects")` | 303 |

**Persists:** yes — the file in Storage, the reference and MD5 in Postgres.

### 3b. Analysis

| Step | Location | Data |
|---|---|---|
| Form POST | `routes/analyze.py :: analysis_run_post` (`/analysis/results`) | `project_id`, `document_ids[]`, theme, flags |
| Parse/validate | `_run_analysis_request` | returns `(dict, None)` or `(None, Alert)` |
| Run pipeline | `modules/orchestrator.py :: BIMGuard_App.orchestrate_workflow` | **plain dict** |
| Materialise IFC | `object_storage.materialize_local_path` | downloads to local cache if needed |
| Read IFC | `ifc_reader` | elements, geometry, spatial, egress |
| Compare | `comparator` | `Issue` dataclasses |
| Render | `_compliance_card`, `_rule_compliance_card`, … | FastHTML component tree |
| Respond | `Div(*sections)` | **HTML fragment** (HTMX swap) |

**Persists: no.** The result dict is rendered and dropped. There is no analysis
run table, no job id, no cache key. **Reloading the page loses the analysis.**

---

## 4. Project / Test Data Management

- **Projects** are real rows in `public.projects`. **One IFC per project** —
  `ifc_file_path` is a single scalar column, not a join.
- **Documents** are rows in `public.documents`, de-duplicated by MD5, carrying
  `extracted_text` inline.
- **Model lineage** (`model_enhancement_lineage`) is append-only, enforced by
  migration, versioning generated IFC outputs.
- **Test fixtures:**
  - `data/test_hospital_mep_scenario.ifc` — deterministic synthetic model
    generated by `app/modules/module2_producer/build_test_ifc.py`
    (4 MEP + 4 structural elements, byte-identical on every run)
  - `app/modules/tests/pdf_stairs_mock.pdf`, `fixtures/`, `snapshots/`
  - `data/validation_models/` — 37-model external corpus (gitignored, re-downloads)
- **Point cloud data:** none. No `.las`, `.laz` or `.e57` anywhere, and no
  reader for them. If point clouds are in scope, that work does not exist yet.

---

## 5. State Management

**There is no session or per-user state.** No session middleware, no cookie
handling, no user table, no auth. The only middleware logs page loads.

Two kinds of process-level state exist:

**Service singletons** — constructed at import, stateless, safe:

```python
_projects_service = ProjectsService()      # routes/projects.py, analyze.py, viewer.py
_rule_service     = RuleService()          # routes/analyze.py, library.py
_object_storage   = ObjectStorage()        # routes/projects.py
```

**Mutable module-level globals** — *not* safe, and the most important thing on
this page for anyone building a frontend:

| Global | File | Purpose |
|---|---|---|
| `_last_compliance_results` | `routes/analyze.py:3152` | cache for the CSV download |
| `_last_simple_compliance` | `routes/analyze.py:3021` | cache for summary export |
| `_last_extracted` | `routes/library.py:795, 848, 988` | extracted rules pending save |
| `_last_extracted_filename` | `routes/library.py:848, 988` | filename for the above |

These are **shared across every request and every visitor**. Two users running
an analysis concurrently overwrite each other's export data, and the second
user's CSV download returns the first user's results. Single-user local use
hides this completely.

---

## 6. Database Schema

Source of record: `supabase/migrations/` (11 files). Every column is
`not null default ''` — the schema does not distinguish "absent" from "empty".

```sql
public.projects
  id bigint identity PK, name text, description text, status text,
  ifc_file_path text,        -- "sb://bucket/key" storage reference
  ifc_md5_hash text, created_at text, updated_at text

public.documents
  id bigint identity PK, md5_hash text, filename text, file_path text,
  extracted_text text,       -- full document text inline
  upload_date text

public.rules
  id bigint identity PK, reference text, rule_type text, description text,
  target_ifc_class text, property_name text, property_set text, operator text,
  check_value / value_min / value_max, unit text, severity text,
  parameters text            -- JSON blob for rule-specific settings

public.issues            -- exists; NOT written by the analysis workflow
public.issue_history     -- historical corrosion runs
public.settings          -- key/value application settings
public.static_data_assets -- versioned rulesets for display
public.model_enhancement_lineage -- append-only, enforced by trigger
```

**Timestamps are `text`, not `timestamptz`** — sorting is lexicographic and
works only because values are ISO-8601.

**`issues` is not populated by the workflow.** `IssueTracker` /
`issue_adapter` exist in `comparator` but are not referenced by
`orchestrator.py`, `pipeline_services.py`, or any route. The table is
vestigial with respect to the live analysis path.

---

## 7. Current Test Data

| Location | Content | Loading |
|---|---|---|
| `data/test_hospital_mep_scenario.ifc` | 4 MEP + 4 structural, exact known extents | `ifcopenshell.open` in `test_real_ifc_pipeline.py` |
| `app/modules/module2_producer/build_test_ifc.py` | Generator for the above | deterministic, byte-identical per run |
| `data/validation_models/` | 37-model external corpus, 1.4 GB | downloaded by `test_all_38_models.py`, gitignored |
| `data/validation_results/` | Per-model sweep records | cached JSON, resumable |
| `app/modules/tests/fixtures/`, `snapshots/` | Module-1 doc-parser fixtures | pytest |
| `data/rulesets/*.json` | Versioned rule packs | `load_rule_pack()` |

The "25 synthetic demo elements" in the brief does not correspond to anything
found. The nearest match is `piping_fixtures.generate_synthetic_piping_network()`,
used by the corrosion unit tests.

---

## 8. File Storage Locations

| Kind | Location | Lifetime |
|---|---|---|
| Uploaded IFC / PDF | Supabase Storage, `{uuid}_{name}` | permanent |
| Local materialisation | `data/cache/supabase-storage/` | disposable, re-downloads |
| Legacy uploads | `data/uploads/ifc/` | pre-Storage; gitignored |
| BCF exports | streamed in the response | not retained server-side |
| CSV / XLSX / PDF reports | generated per request from a **global** | not retained |
| Validation artefacts | `data/validation_bcf/`, `docs/validation/` | gitignored / committed |

---

## 9. Key Functions a New Frontend Must Not Break

| Function | File | Contract |
|---|---|---|
| `BIMGuard_App.orchestrate_workflow(project_id, doc_ids, …)` | `modules/orchestrator.py` | returns the result `dict` — **the single source of analysis data** |
| `_run_analysis_request(req)` | `routes/analyze.py:501` | `(dict, None)` on success, `(None, Alert)` on failure |
| `ProjectsService.list_projects / get_project / create_project` | `services/projects_service.py` | project CRUD |
| `ProjectsService.prepare_ifc_upload(file)` | same | `(storage_ref, md5)`; validates extension |
| `ObjectStorage.save_upload / materialize_local_path` | `services/object_storage.py` | storage boundary |
| `DocumentService`, `RuleService` | `services/` | document and rule access |
| `redirect_see_other(path)` | `utils.py` | 303 after POST |
| `DashboardLayout(...)` | `components/layout.py` | page chrome every route wraps in |

---

## Critical Question

> *If I build a new frontend component that displays analysis results, what data
> structure would it receive, and where would it come from?*

**It receives a plain Python `dict`** returned by
`orchestrate_workflow()` — not a database record, not JSON over an API, not a
typed object. It is constructed in memory and passed directly to component
functions in the same request.

Keys observed on the result:

```python
{
  "project":                  dict,   # the projects row
  "analysis_theme":           str,    # "Architecture" | "MEP"
  "rule_folder":              str,
  "ifc_element_count":        int,
  "building_summary":         dict,   # storeys, rooms, areas, element counts
  "compliance_results":       list,   # corrosion engine findings
  "compliance_is_demo":       bool,
  "compliance_error":         str | None,
  "rule_compliance":          list,   # per-rule, per-element results
  "rule_compliance_summary":  dict,
  "rule_compliance_error":    str | None,
  "rule_validations":         list,
  "spatial_checks":           dict,   # adjacency, daylight, fire separation
  "egress_checks":            dict,   # exits, travel distance
  "cost_impact":              dict,
  "issue_stats":              dict,
  "documents":                list,
  "bcf_topics":               list,
  "bcf_project_id":           int,
  "audit_issues":             list,
  "error":                    str,    # present only on failure
}
```

### Four consequences for frontend design

1. **The data is request-scoped.** No endpoint returns it as JSON; no id
   retrieves it later. A component that renders results must be called during
   the POST that produced them, or the data is gone.
2. **HTMX partials, not an API.** `/analysis/results` returns an HTML fragment
   for swapping. A React/Lovable frontend would need a JSON endpoint that does
   not currently exist — a genuine addition, not a re-skin.
3. **Exports depend on a global.** `/reports/compliance-csv` reads
   `_last_compliance_results`. Any redesign that changes when analysis runs, or
   serves two users, breaks CSV export in a way that fails silently and returns
   *someone else's data*.
4. **Nothing is cached.** Re-analysing means re-reading the IFC and re-running
   every engine — measured at ~97 s per model on the validation corpus. A UI
   that re-runs analysis on navigation will feel broken.

### What a JSON API would need

Adding `GET /api/analysis/{run_id}` requires an analysis-run table that does not
exist. The minimum viable change:

1. Persist the result dict (a `jsonb` column keyed by run id would do).
2. Return the run id from the POST.
3. Replace the four `_last_*` globals with lookups by run id.

That is the single change which most improves this architecture, and it happens
to be the same change a decoupled frontend requires.
