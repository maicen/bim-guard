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

## Architecture & Migration Status

BIM-Guard is transitioning from a legacy FastHTML + MonsterUI monolith into a modern, decoupled architecture:
1. **Primary Backend API**: **FastAPI** (`app/api/`) mounted at `/api` on the ASGI app, exposing RESTful endpoints, typed Pydantic data contracts (`app/modules/contracts.py`), and real-time Server-Sent Events (SSE) tracking (`/api/events/{project_id}`).
2. **Primary Frontend Client**: **Decoupled SPA Frontend** (`frontend/`) built with **Svelte 5**, Vite, TypeScript, and Tailwind CSS, consuming `/api` endpoints via `src/lib/api.ts` and SSE via `src/lib/sse.ts`.
3. **Legacy Monolith (Deprecated / Maintenance Only)**: FastHTML + MonsterUI routes (`app/routes/`) and UI components (`app/components/`) mounted at `/` during the transition period. **Do not create new user-facing features in FastHTML**; build all new views, forms, and interactive components in `frontend/`.
4. **Compute Kernels & Engines**: Pure Python compliance kernels (`app/engines/`, `app/modules/`, `app/services/`) remain framework-agnostic.

### Layer Structure

```text
Primary Frontend (frontend/)       → Vite + Svelte 5 SPA, TypeScript, Tailwind CSS
API Gateway (app/api/)             → FastAPI routers (/projects, /rules, /analyze, /events)
Data Contracts (app/modules/contracts.py) → Pydantic request/response schemas (mirrored in frontend/src/lib/types.ts)
Services (app/services/)           → Business logic, pipeline runner, tracker, Supabase persistence
Engines & Modules (app/modules/, app/engines/) → Pure Python compliance kernels (GC-001, CC-001, MC-001, Blue Halo)
Legacy Monolith (app/routes/, app/components/) → FastHTML + MonsterUI (deprecated / maintenance only)
```

### Data Flow

1. `main.py` (root) → boots uvicorn ASGI server
2. `app/main.py` → registers FastAPI router at `/api` and legacy FastHTML routes at `/`
3. Svelte client (`frontend/`) talks to `/api/*` via `src/lib/api.ts` and listens to live SSE progress events via `src/lib/sse.ts`
4. FastAPI routers validate requests using Pydantic schemas (`app/modules/contracts.py`), invoke domain services (`app/services/`), and run compute engines
5. Results return as typed Pydantic JSON or stream incrementally over SSE connections

### Frontend Guidelines (`frontend/`)

- **Framework**: Svelte 5 using the modern runes syntax (`$state`, `$derived`, `$props`, `$effect`).
- **Styling**: Tailwind CSS with custom theme variables matching BIM-Guard design tokens.
- **Contract Parity**: When Pydantic schemas in `app/modules/contracts.py` change, immediately update corresponding TypeScript interfaces in `frontend/src/lib/types.ts`.
- **API Client**: All HTTP calls go through `src/lib/api.ts`. Never use raw `fetch()` directly in components.
- **Real-Time Streaming**: Consume pipeline stage transitions (Validation → Parsing → Engine Run → Scoring → Reporting) using `subscribeToEvents()` from `src/lib/sse.ts`.
- **IFC 3D Viewer**: Encapsulated in `src/lib/components/IfcViewer.svelte` using `@thatopen/fragments`, `@thatopen/components`, and `web-ifc`.

### API & Backend Guidelines (`app/api/`)

- **Strict Contracts**: Every endpoint must accept and return strict Pydantic schemas defined in `app/modules/contracts.py`. Never return raw dicts or unvalidated payloads.
- **Dependency Injection**: Use FastAPI `Depends(...)` with providers from `app/api/dependencies.py` to obtain service instances.
- **Error Handling**: Raise standard `fastapi.HTTPException` with appropriate status codes (400, 404, 409, 500) and clear detail messages.
- **Real-Time Events**: Publish progress through `PipelineTracker` and stream via `/api/events/{project_id}`.

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

### Legacy FastHTML UI (Maintenance Only)

- Code under `app/routes/` and `app/components/` is legacy FastHTML + MonsterUI.
- **Maintenance rule**: Only modify legacy FastHTML files when fixing existing bugs or preserving backward compatibility during the migration phase. Do NOT build new pages or features in FastHTML.

## Coding Guidelines

Detailed coding rules covering the FastAPI backend, Svelte 5 frontend, database operations, and legacy maintenance are in [.github/instructions/project-specific.instructions.md](.github/instructions/project-specific.instructions.md).
