# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Instructions Files Map

| File | Who reads it | What it defines |
| --- | --- | --- |
| README.md | Humans | What the project is |
| AGENTS.md, CLAUDE.md, .github/instructions/project-specific.instructions.md | Coding agents | How to build the project |
| DESIGN.md | Design agents | How the project should look and feel |

## Commands

```bash
# Install backend dependencies
uv sync

# Install optional ML pipeline dependency group
uv sync --group ml-pipeline

# Run development backend server
uv run uvicorn main:app --reload

# Run with specific host/port
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Install & run Svelte frontend
cd frontend && npm install
npm run dev

# Run full development stack (cross-platform)
./run_server.sh         # macOS/Linux (or ./run_server.bat)
run_server.bat          # Windows

# Run production stack (build SPA + multi-worker uvicorn)
./run_production_server.sh  # macOS/Linux (or ./run_production_server.bat)
run_production_server.bat   # Windows

# Run automated tests and lint
uv run ruff check .
uv run pytest tests/ -v
```

## Dependency Management Rule

All Python dependencies must be managed via uv and declared in pyproject.toml (including optional dependency groups). Do not add or maintain separate requirements.txt files.
All frontend dependencies must be declared in `frontend/package.json`.

## Docstring and API Documentation Rule

- Follow [PEP 257](https://peps.python.org/pep-0257/) for Python docstrings.
- Interactive OpenAPI documentation is automatically served at `http://127.0.0.1:8000/api/docs`.
- For new public modules/classes/functions, add or update docstrings in the same change.

Useful commands:

```bash
uv run ruff check .
uv run pytest tests/test_api_*.py -v
```

## Architecture

BIM-Guard is evolving from a FastHTML + MonsterUI monolith into a modern, decoupled architecture: a **FastAPI API Gateway** providing strict Pydantic REST contracts and real-time Server-Sent Events (SSE) tracking, and a **standalone Vite + Svelte 5 Single-Page Application (SPA)** client.

### Layer Structure

```text
Frontend (frontend/)       → Vite + Svelte 5 SPA, TypeScript, Tailwind CSS
API Gateway (app/api/)     → FastAPI routers (/projects, /rules, /analyze, /events)
Data Contracts (app/modules/contracts.py) → Pydantic request/response schemas
Routes (app/routes/)       → FastHTML handlers, HTMX responses (legacy/coexistence)
Services (app/services/)   → Business logic, pipeline runner, tracker, Supabase persistence
Engines & Modules (app/modules/, app/engines/) → Pure Python compliance kernels (GC-001, CC-001, MC-001, Blue Halo)
```

### Key Technologies

- **FastAPI** — Modern API framework serving `/api` with automatic OpenAPI documentation (`/api/docs`), CORS, Pydantic model validation, and SSE streaming.
- **Svelte 5** — Modern reactive frontend framework powering the decoupled SPA under `frontend/`.
- **FastHTML & MonsterUI** — Coexisting Python UI layer mounted at `/` for backward compatibility during migration.
- **Server-Sent Events (SSE)** — Real-time event streaming (`/api/events/{project_id}`) for 6-stage compliance pipelines.
- **Supabase** — Managed Postgres persistence accessed through `PersistenceService` and object storage.
- **IfcOpenShell** — Server-side IFC parsing engine.

### Data Flow

1. `main.py` (root) → boots uvicorn
2. `app/main.py` → initializes FastHTML app and mounts FastAPI gateway at `/api`
3. Svelte client (`frontend/`) talks to `/api/*` via `src/lib/api.ts` and listens to real-time events via `src/lib/sse.ts`
4. FastAPI routers call service layer (`app/services/`); compute kernels execute without UI framework dependencies
5. Results return as validated Pydantic models or stream over SSE connections

### Database & Rule Management

Supabase Postgres stores application data. The primary tables are:

- `projects` — IFC project metadata + file paths
- `documents` — Uploaded PDFs with extracted text
- `rules` — Unified compliance rules table with typed fields and JSON `parameters`

#### Database-Driven Analysis Engine Architecture
All compliance and corrosion analysis workflows are strictly database-driven:
- **Zero Hardcoded Logic**: Multi-criteria scoring weights, risk band thresholds, material tables, flow velocity/dead-leg intervals, zone-to-environment mappings, and mitigations are read dynamically from database rules (`RuleService`), not hardcoded constants.
- **Corrosion Engine Catalogs**: `app/services/corrosion_rule_catalog.py` translates DB rules into engine lookups for `BIMGUARD-GC-001`, `BIMGUARD-CC-001`, and `BIMGUARD-MC-001`.
- **Live Catalog Reloading**: In-memory engine catalogs are refreshed via `reload_all_catalogs()` (calling `bimguard_*_engine.reload_rules()`) at the start of each analysis run, allowing DB rule edits to take effect immediately without server restarts.
- **Targeted Ruleset Execution**: Selecting a `rule_folder` queries rules directly from the DB via `RuleService().list_by_ruleset(rule_folder)` so custom or extracted rulesets execute immediately against the model.

### Compliance Pipeline (app/modules/)

Five sequential modules — most are stubs awaiting implementation:

1. **Module1_DocParser** — PDF text extraction and section preprocessing
2. **Module2_IFCRead** — IFC file parsing (stub)
3. **Module3_RuleBuilder** — NLP → structured rules (stub, AI integration point)
4. **Module4_Comparator** — IFC vs rules validation (stub)
5. **Module5_Reporter** — Report generation (stub)

`orchestrator.py` contains `BIMGuard_App` as the entry point for running the full pipeline.

### IFC Viewer

The viewer route (`app/routes/viewer.py`) loads a 3D model in-browser using `@thatopen/fragments`, `@thatopen/components`, and `web-ifc` loaded from CDN. The loader script is at `static/js/ifc-viewer-loader.js`.

### UI Conventions

- Page structure: `DashboardLayout` wraps all pages, with `AppSidebar` and `AppHeader` from `app/components/layout.py`
- Action icon buttons (`ViewAction`, `EditAction`, `CreateAction`, `BackAction`) are in `app/components/ui.py`
- Each domain has a `*_ui.py` component file and a `*_service.py` service file
- File uploads are stored in Supabase Storage with UUID-prefixed object keys; downloaded objects are cached under `data/cache/supabase-storage/`

## Coding Guidelines

Detailed coding rules covering UI patterns, HTMX conventions, route structure, database operations, file uploads, and the BIM module pipeline are in [.github/instructions/project-specific.instructions.md](.github/instructions/project-specific.instructions.md). This file applies automatically to all code under `app/` and is the authoritative reference for how to write code in this project.
