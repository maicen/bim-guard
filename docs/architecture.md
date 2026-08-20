# BIMGUARD AI — Architecture & FastHTML Integration Plan

| | |
| --- | --- |
| **Document** | `docs/architecture.md` |
| **Version** | 0.1 (target architecture / integration plan) |
| **Status** | Living document — update as the FastHTML migration lands |
| **Scope** | Backend structure, FastHTML/MonsterUI full-stack wiring, request lifecycle |
| **Owner** | Group 5 — Masters in BIM Management, Zigurat Global Institute of Technology |

> Note: some sections below are historical migration-plan material retained for thesis context. For current runtime setup, treat `README.md`, `docker-compose.yml`, and `render.yaml` as the operational source of truth.

---

## 1. Purpose and scope

This document describes how the BIMGUARD AI application is structured as a FastHTML / MonsterUI full-stack web application. It maps the repository layout to runtime responsibilities, shows how HTTP routes delegate to workflow modules and persistence services, and explains how the validated corrosion engines (GC-001 galvanic, CC-001 crevice) and LLM-translated engineering rulesets plug into that pipeline.

It is intentionally a **developer-facing** document. Academic rationale for OpenBIM, IFC, BCF 2.1 and the corrosion scoring model lives in the thesis chapters; this file assumes those decisions and concentrates on how they are wired together in code.

## 2. Context — what this replaces

The first working prototype of BIMGUARD AI was a six-page Streamlit application (`BIMGUARD_AI_App.zip`) which proved the end-to-end workflow against 25 synthetic elements: 9 Critical / 7 High / 9 Medium issues, 25 BCF issues generated, £170,600 estimated remediation cost, 162 working days delay.

Streamlit was the right choice for rapid prototyping but has several limitations for a FMP deliverable and any future production deployment:

- No proper HTTP routing — every interaction re-runs the whole script top-to-bottom.
- Difficult to test routes and business logic independently.
- No clean separation between presentation and domain logic.
- Session state is awkward to persist across users or restarts.
- Not a good fit for multi-user project workspaces or API consumers.

The FastHTML / MonsterUI stack addresses these issues while keeping the implementation language (Python), the corrosion engines, and the OpenBIM-only methodology unchanged.

## 3. Runtime stack

| Layer | Choice | Role |
| --- | --- | --- |
| Package / environment manager | **uv** (Astral) | Resolve, lock and install dependencies; run commands in the project venv |
| ASGI server | **uvicorn** | Serve the ASGI app; auto-reload during development |
| Web framework | **FastHTML** | Routing, request/response, FT (FastTags) rendering, HTMX integration |
| UI components | **MonsterUI** | Tailwind + FrankenUI component library exposed as Python FT functions |
| Partial rendering | **HTMX** (bundled by FastHTML) | Form submission and fragment swaps without writing JS |
| IFC processing | **ifcopenshell** | Open-source IFC 2x3 / IFC4 parser |
| Point clouds | **laspy**, **pye57** | `.las` / `.laz` / `.e57` readers (open formats) |
| Plotting | **plotly** | 3D risk maps, Gantt, charts (rendered as HTML fragments) |
| Persistence | **Supabase Postgres** (default) via adapter layer | Project state, documents, rules, audit-style records |
| Object storage | **Supabase Storage** (default) via adapter layer | IFC files, uploaded documents, generated artifacts |
| LLM rule extraction | **Gemini API** | Translate engineering standards text into structured JSON rulesets |

### 3.1 How the app is started

```bash
# one-time: sync the locked environment
uv sync

# development: auto-reload
uv run uvicorn main:app --reload

# explicit host/port (container, VM, demo)
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

`uv run` executes the command inside the project's managed virtualenv (resolved from `pyproject.toml` + `uv.lock`), so collaborators do not need to manually activate anything. `uvicorn main:app` tells uvicorn to import the `app` object from `main.py` and serve it as an ASGI application. `main.py` can also be executed directly with `python main.py` because FastHTML's `serve()` helper is a thin wrapper around uvicorn for convenience in development.

## 4. Repository layout

```text
bimguard-ai/
├── main.py                                # ASGI entrypoint — builds `app` and registers routes
├── pyproject.toml                         # Project metadata, dependencies (uv)
├── uv.lock                                # Locked dependency graph
├── README.md
├── docs/
│   └── architecture.md                    # THIS DOCUMENT
├── app/
│   ├── __init__.py
│   ├── routes/                            # HTTP endpoints — one file per feature area
│   │   ├── __init__.py
│   │   ├── home.py                        # GET /
│   │   ├── ingest.py                      # GET/POST /ingest, /ingest/pointcloud
│   │   ├── overview.py                    # GET /overview, /overview/filter
│   │   ├── compliance.py                  # GET /compliance, POST /compliance/run
│   │   ├── pointcloud.py                  # GET /pointcloud/compare
│   │   ├── bcf.py                         # GET /bcf, GET /bcf/download
│   │   └── schedule.py                    # GET /schedule
│   ├── modules/                           # Workflow pipeline stages (pure Python, no HTTP)
│   │   ├── __init__.py
│   │   ├── ifc_parser.py                  # IFC → normalised element list
│   │   ├── pointcloud_loader.py           # .las/.laz/.e57 → numpy point array
│   │   ├── compliance_runner.py           # Orchestrates GC-001 + CC-001 over elements
│   │   ├── bcf_generator.py               # Issues → BCF 2.1 ZIP (markup.bcf, viewpoint.bcfv)
│   │   └── schedule_impact.py             # Issues → programme delay & £ cost
│   ├── services/                          # Persistence, configuration, external integrations
│   │   ├── __init__.py
│   │   ├── persistence.py                 # DB adapter bootstrap (Supabase default)
│   │   ├── db_adapters.py                 # Supabase table adapters
│   │   ├── object_storage.py              # Object storage adapters (local + Supabase)
│   │   ├── rules_service.py               # Rule CRUD
│   │   └── gemini_rule_extractor.py       # Standards text → structured rules via Gemini
│   ├── engines/                           # Validated rule engines (lifted from prototype)
│   │   ├── bimguard_corrosion_engine.py   # GC-001 v1.0.0
│   │   └── bimguard_crevice_engine.py     # CC-001 v1.0.0
│   ├── rulesets/                          # Versioned rule JSON (the engines' truth source)
│   │   ├── galvanic_corrosion_ruleset.json
│   │   └── crevice_corrosion_ruleset.json
│   └── views/                             # MonsterUI FT components (presentation only)
│       ├── __init__.py
│       ├── layout.py                      # Page shell, nav, footer
│       ├── forms.py                       # Upload forms, environment selector, filters
│       ├── tables.py                      # Element and risk tables
│       └── charts.py                      # Plotly → FT wrappers
└── data/
    ├── rulesets/                          # Seed JSON rulesets
    └── cache/                             # Runtime cache for downloaded storage objects
```

Three design principles govern this layout:

1. **Routes know about HTTP, modules do not.** Anything in `app/modules/` is pure Python that can be unit-tested without a server. Routes adapt HTTP requests into module calls and module results into FT trees.
2. **Services are the only path to state.** Modules and routes never open the database or touch artifact storage directly; they go through `app/services/`. Supabase Postgres and Supabase Storage are accessed through the persistence and object-storage adapters.
3. **Engines are immutable from the app's perspective.** `app/engines/` contains the validated GC-001 and CC-001 logic from the Streamlit prototype. The rest of the app consumes them as a library — it does not edit them.

## 5. Request lifecycle

```text
Browser  ──HTTP──▶  uvicorn  ──ASGI──▶  FastHTML app (main.py)
                                              │
                                              ▼
                               route in app/routes/*.py
                                              │
                         (parses form / reads query / loads session)
                                              │
                                              ▼
                          workflow module in app/modules/*.py
                                              │
                                ┌─────────────┼─────────────┐
                                ▼             ▼             ▼
                         engines/       services/       rulesets/
                         (GC-001,     (project_store,   (JSON rules)
                          CC-001)      ruleset_loader,
                                       llm_rule_extractor,
                                       db)
                                              │
                                              ▼
                      route composes MonsterUI FT tree via app/views/
                                              │
                                              ▼
                   FastHTML renders FT → HTML (full page or HTMX fragment)
                                              │
                                              ▼
                                        uvicorn → Browser
```

Every interactive action in the UI follows this flow. HTMX on the client intercepts form submissions and link clicks marked with `hx-*` attributes, sends them to the route, and swaps the returned HTML fragment into the DOM — so the page does not have to reload for a compliance run to refresh the risk table.

## 6. `main.py` — the entrypoint

`main.py` is deliberately thin. Its only responsibilities are to build the FastHTML `app`, apply the MonsterUI theme, and register each route module. All business logic lives elsewhere.

```python
# main.py
from fasthtml.common import fast_app, serve
from monsterui.all import Theme

from app.routes import (
    home,
    ingest,
    overview,
    compliance,
    pointcloud,
    bcf,
    schedule,
)
from app.services.db import init_db

# Build the ASGI app and the route decorator.
# MonsterUI's Theme.blue.headers() injects Tailwind + FrankenUI CSS + HTMX.
app, rt = fast_app(
    hdrs=Theme.blue.headers(),
    pico=False,   # MonsterUI supersedes pico.css
    live=True,    # auto-reload hooks during development
)

# Run startup initialization hooks.
initialize_startup_state()

# Each route module exposes a `register(rt)` function that attaches its endpoints.
for module in (home, ingest, overview, compliance, pointcloud, bcf, schedule):
    module.register(rt)

if __name__ == "__main__":
    # Convenience for `python main.py`; production uses `uv run uvicorn main:app`.
    serve()
```

Why `register(rt)` instead of importing `app` directly in each route file? It keeps the route modules free of circular imports and makes them trivial to unit-test with a mocked `rt`.

## 7. `app/routes/` — HTTP endpoints

Each file in `app/routes/` corresponds to one page of the former Streamlit application. Every file exposes a `register(rt)` function; everything else in the file is private to that feature area.

| Route file | Endpoints | Purpose | Calls |
| --- | --- | --- | --- |
| `home.py` | `GET /` | Landing page, project selector | `services.project_store` |
| `ingest.py` | `GET /ingest`, `POST /ingest`, `POST /ingest/pointcloud` | Upload IFC and point cloud, or load the synthetic demo | `modules.ifc_parser`, `modules.pointcloud_loader`, `services.project_store` |
| `overview.py` | `GET /overview`, `GET /overview/filter` | List extracted elements, filter by system/material/floor, material inventory chart | `services.project_store`, `views.tables`, `views.charts` |
| `compliance.py` | `GET /compliance`, `POST /compliance/run` | Run GC-001 + CC-001, show risk distribution, 3D spatial map, results table, CSV export | `modules.compliance_runner`, `services.ruleset_loader`, `views.charts` |
| `pointcloud.py` | `GET /pointcloud/compare` | Overlay IFC elements against the imported point cloud in 3D | `modules.pointcloud_loader`, `services.project_store`, `views.charts` |
| `bcf.py` | `GET /bcf`, `GET /bcf/download` | List issues, expandable issue cards, download BCF 2.1 ZIP | `modules.bcf_generator`, `services.project_store` |
| `schedule.py` | `GET /schedule` | Gantt (baseline vs delayed), cost by band, delay by mechanism | `modules.schedule_impact`, `services.project_store`, `views.charts` |

### 7.1 Route template

```python
# app/routes/compliance.py
from fasthtml.common import Titled
from monsterui.all import Container, Button

from app.modules.compliance_runner import run_compliance
from app.services.project_store import current_project
from app.views.layout import page
from app.views.tables import risk_table
from app.views.charts import risk_distribution_pie


def register(rt):

    @rt("/compliance")
    def get():
        project = current_project()
        results = project.latest_results()          # may be None
        return page(
            "Compliance",
            Container(
                Button("Run compliance check",
                       hx_post="/compliance/run",
                       hx_target="#results"),
                risk_distribution_pie(results) if results else "",
                risk_table(results, id="results"),
            ),
        )

    @rt("/compliance/run")
    def post():
        project = current_project()
        results = run_compliance(project)           # pure domain call
        return risk_table(results, id="results")    # HTMX swaps this fragment
```

The `GET` handler renders the full page; the `POST` handler returns only the fragment that HTMX will swap in (`hx_target="#results"`). The domain call `run_compliance(project)` has no idea it is being invoked over HTTP — it can be called identically from a test, a CLI, or a future API.

## 8. `app/modules/` — workflow pipeline stages

Each module is one stage of the pipeline that was proven in the Streamlit prototype. Modules are pure functions over plain Python data structures; they raise exceptions on bad input and never touch `request` objects.

| Module | Input | Output | Notes |
| --- | --- | --- | --- |
| `ifc_parser.py` | Path to `.ifc` file (any IFC 2x3 / IFC4 exporter) | List of normalised element dicts — material key, system, floor, space, joint type, environment class | Uses ifcopenshell. Normalises vendor-specific material names to BIMGUARD material keys. Classifies environment from IFC `IfcSpace` metadata. |
| `pointcloud_loader.py` | Path to `.las` / `.laz` / `.e57` | Numpy array of XYZ (+ intensity where present), bounds, density | Open formats only. No proprietary SDK dependency. |
| `compliance_runner.py` | Normalised element list + active rulesets | Per-element risk results (GC-001 score, CC-001 score, combined band, mitigation) | Orchestrates both engines; `combined_risk_assessment()` from `engines/bimguard_crevice_engine.py` is the core call. |
| `bcf_generator.py` | Results at Medium risk or above | BCF 2.1-compliant ZIP on disk (`markup.bcf`, `viewpoint.bcfv`, `snapshot.png` per issue) | Embeds GUID, service metadata, risk band, mitigation, engineer assignment, history. buildingSMART schema compliance. |
| `schedule_impact.py` | Results + project programme activities | Per-issue delay (working days) and £ cost, aggregated by band and mechanism | Cost/duration model will be user-configurable via CSV upload (see §12 open items). |

### 8.1 Module contract

Modules follow a simple convention that routes rely on:

```python
# app/modules/compliance_runner.py
from dataclasses import dataclass
from typing import Iterable

from app.engines.bimguard_crevice_engine import combined_risk_assessment
from app.services.ruleset_loader import load_active_rulesets


@dataclass
class ComplianceResult:
    element_id: str
    galvanic_score: float
    crevice_score: float
    combined_band: str          # "Low" | "Medium" | "High" | "Critical"
    mitigation: str
    # ... etc.


def run_compliance(project) -> list[ComplianceResult]:
    gc_rules, cc_rules = load_active_rulesets()
    elements = project.elements()
    return [
        _assess(el, gc_rules, cc_rules) for el in elements
    ]


def _assess(element, gc_rules, cc_rules) -> ComplianceResult:
    raw = combined_risk_assessment(element, gc_rules, cc_rules)
    return ComplianceResult(**raw)
```

Dataclasses are used instead of free-form dicts so that views (tables, charts) get static attribute access and type hints.

## 9. `app/services/` — persistence, configuration, rule ingestion

Services are the only components that perform I/O (besides reading uploaded files in modules).

| Service | Responsibility | Key functions |
| --- | --- | --- |
| `persistence.py` | Supabase client and table bootstrap | `get_db()`, `get_table(...)` |
| `db_adapters.py` | Table API over Supabase Postgres | `SupabaseTableAdapter` |
| `object_storage.py` | Supabase Storage API with local materialization cache | `save_upload(...)`, `materialize_local_path(...)`, `delete(...)` |
| `gemini_rule_extractor.py` | Extract candidate rules from standards text using Gemini | `extract_rules(...)`, validation helpers |

### 9.1 Persistence schema (current)

Supabase Postgres is the default runtime backend. Core tables:

- `projects (id, name, created_at, active_gc_version, active_cc_version)`
- `elements (id, project_id, guid, material, system, floor, space, joint_type, env_class, …)`
- `results (id, element_id, gc_score, cc_score, combined_band, mitigation, created_at)`
- `issues (id, project_id, element_id, bcf_guid, band, mechanism, engineer, status, history_json, created_at)`
- `audit (id, project_id, action, actor, payload_json, created_at)` — the Golden Thread hook (Building Safety Act 2022).

### 9.2 LLM-translated rule extraction

"LLM-translated engineering rules" is the mechanism by which new compliance rules (for example, a new grade/environment pair from CIRIA or IMOA) are on-boarded without hand-coding JSON. The flow is:

1. User uploads the relevant extract (text / PDF page) of a standard.
2. `gemini_rule_extractor` sends the extract to Gemini with a constrained prompt that targets the project's JSON rule schema.
3. The response is parsed and diffed against the currently active ruleset.
4. The diff is shown to the user for approval; on approval it is written to `app/rulesets/` with a new semantic version number.

The engine code itself is unchanged — it always reads the latest active version via `ruleset_loader`. This preserves the White Box Architecture commitment: every score remains traceable to a named, versioned rule with a named standard reference, regardless of whether the rule was authored by a human or LLM-proposed and human-approved.

## 10. Integration matrix — who calls what

| HTTP endpoint | Module(s) | Service(s) | Engine(s) | Writes |
| --- | --- | --- | --- | --- |
| `POST /projects/create` | `module2_ifc_read` (indirect via services) | `projects_service`, `object_storage` | — | Supabase Storage + `projects` table |
| `POST /api/documents/upload` | `module1_doc_parser` | `documents_service`, `object_storage` | — | Supabase Storage + `documents` table |
| `POST /analyze/results` | `orchestrator` | `projects_service`, `documents_service`, `rules_service` | GC-001, CC-001 | read-mostly (analysis output in response) |
| `GET /projects/{id}/ifc` | — | `projects_service`, `object_storage` | — | storage read + cache write |
| `POST /library/rules/create` | `module3_rule_builder` (service path) | `rules_service` | — | `rules` table |

A route may call multiple modules; a module may call multiple services; services and engines are leaves and do not call back up the stack.

## 11. OpenBIM compliance boundary

The architecture explicitly preserves the OpenBIM commitment stated in the thesis:

- **Inputs:** IFC (ISO 16739-1), `.las` / `.laz` (ASPRS), `.e57` (ASTM). No Revit API, no Dynamo, no proprietary SDKs.
- **Outputs:** BCF 2.1 (buildingSMART) ZIPs, CSV, and (planned) Word/PDF reports.
- **Processing:** ifcopenshell is the only IFC library; it reads IFC from any authoring tool that exports the standard.
- **Rulesets:** Plain JSON referencing named public standards (NASA-STD-6012, EN ISO 15329, ASTM G48, CIRIA C692, IMOA, BS 8539, EN 1993-1-4).
- **UI:** FastHTML / MonsterUI produces plain HTML — no vendor lock-in.

Nothing in `app/routes/`, `app/modules/` or `app/services/` should ever import a proprietary SDK. If a future feature requires one, it belongs in a separately packaged adapter under `app/adapters/<vendor>/` and must be optional.

## 12. Migration path from the Streamlit prototype

The Streamlit prototype already contains `modules/ifc_parser.py`, `modules/compliance_runner.py`, `modules/bcf_generator.py` and `modules/schedule_impact.py`. These transfer essentially verbatim into `app/modules/` — they were written without any Streamlit-specific imports in their cores, so the migration is a move plus light refactor:

1. Copy the existing four modules into `app/modules/` and remove any `st.*` calls that slipped in.
2. Copy `bimguard_corrosion_engine.py` and `bimguard_crevice_engine.py` into `app/engines/` unchanged (they are already pure).
3. Copy `galvanic_corrosion_ruleset.json` and `crevice_corrosion_ruleset.json` into `app/rulesets/` unchanged.
4. Replace each Streamlit page (`pages/1_Data_Ingestion.py`, etc.) with a route module in `app/routes/`, rebuilding the UI using MonsterUI components.
5. Introduce `app/services/project_store.py` + `app/services/db.py` to replace Streamlit's `st.session_state`.
6. Add `app/services/ruleset_loader.py` so engines consume rules via the service layer, not via direct `json.load()`.
7. Add `app/services/llm_rule_extractor.py` to realise the "AI" half of BIMGUARD AI as an explicit, reviewable step.

The corrosion logic — the part with validated test output — is not touched.

## 13. Deployment

**Local / demo:**

```bash
uv sync
uv run uvicorn main:app --reload
# open http://localhost:8000
```

**Container (current):**

```dockerfile
docker compose up --build
```

**Render.com:** Deployment is defined in `render.yaml` and runs the same Docker image with environment variables injected in the Render dashboard.

**Static assets:** FastHTML serves MonsterUI / HTMX assets via app headers, so no separate frontend build step is required.

## 14. Open items and assumptions

These are called out explicitly so reviewers can see what is deliberate vs. still-to-decide:

- **Persistence store.** Supabase Postgres is the application database and the source of truth for persisted state.
- **Authentication.** Not in scope for the FMP demo. When added, it belongs in `app/services/auth.py` and is enforced via a FastHTML middleware registered in `main.py`.
- **BCF viewpoint screenshots.** Currently placeholder PNGs. The plan is to render actual screenshots from the Plotly 3D viewer; tracked in the thesis Chapter 5 "limitations" section.
- **Cost / duration model.** Hardcoded in the prototype; to be made user-configurable via CSV upload, handled by `schedule_impact.py` + `project_store`.
- **LLM rule extraction UI.** The Gemini extraction service is in scope; a full curation UI may be deferred post-submission.
- **Migration status.** The repository is now FastHTML-first. Treat this file as a living architecture reference and update it whenever routes, modules, or deployment assumptions change.

## 15. Change log

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-04 | Initial integration plan based on task brief + validated Streamlit workflow |
