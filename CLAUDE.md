# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Instructions Files Map

YOU MUST FOLLOW THEM.
| File | Who reads it | What it defines |
| --- | --- | --- |
| README.md | Humans | What the project is |
| AGENTS.md, CLAUDE.md, .github/instructions/project-specific.instructions.md | Coding agents | How to build the project |
| DESIGN.md | Design agents | How the project should look and feel |

## Repository Structure & Root Directory Protection (STRICT)

**CRITICAL RULE: NEVER CREATE OR PLACE FILES IN THE REPOSITORY ROOT.**

The repository root is strictly reserved for primary configuration files (`pyproject.toml`, `uv.lock`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `DESIGN.md`, `Dockerfile`, `docker-compose.yml`, `render.yaml`, `main.py`, `.gitignore`, `run_server.*`, etc.).

All newly generated files (code, tests, scripts, fixtures, data manifests, reports, documentation, temporary files) **MUST ALWAYS** be placed in the appropriate subfolder:

- **`app/`** — Backend application code:
  - `app/api/` — FastAPI routers, dependency injection, and SSE streaming
  - `app/modules/contracts.py` — Pydantic request/response schemas
  - `app/engines/` — Pure Python computation and compliance engines (GC-001, CC-001, MC-001, ARCH-*, etc.)
  - `app/services/` — Business logic, persistence, and pipeline runner services
  - `app/modules/` — Orchestration and parsing modules
- **`frontend/`** — Svelte 5 frontend client:
  - `frontend/src/routes/` — Svelte page views
  - `frontend/src/lib/components/` — Reusable Svelte components
  - `frontend/src/lib/types.ts` — TypeScript interfaces (mirrors Pydantic contracts)
  - `frontend/src/lib/api.ts` — Typed backend API client
  - `frontend/src/lib/sse.ts` — Server-Sent Events subscriber
- **`tests/`** — Automated test suites & test fixtures:
  - `tests/` — Pytest unit and integration test files (`test_*.py`)
  - `tests/e2e/` — End-to-end test configs and manifests (e.g. `tests/e2e/e2e-models.json`)
  - `tests/schemas/` — Test schemas and sample datasets
- **`scripts/`** — Standalone utilities, runner harnesses, benchmarking tools, and migration helpers (e.g. `scripts/e2e_server.py`, `scripts/e2e_suite.py`).
- **`docs/`** — Documentation, research, benchmarks, and validation reports:
  - `docs/validation/` — Validation reports and markdown summaries (e.g. `docs/validation/test-results.md`)
  - `docs/validation/data/` — Validation output datasets and JSON machine records (e.g. `docs/validation/data/test-results.json`)
  - `docs/benchmarks/` — Benchmark results, charts, and summaries
  - `docs/architecture/` — System architecture design documents
- **`data/`** — Seed data, static rulesets (`data/rulesets/`), schema configs, and sample IFC files.
- **`supabase/migrations/`** — Database migration SQL scripts.

**NEVER output test results, machine logs, JSON dumps, markdown summaries, or scratch scripts to the root directory `./`. Always direct outputs to the designated subdirectories above.**


## Commands

```bash
# Install backend dependencies
uv sync

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

## Architecture & Decoupled Stack

BIM-Guard uses a modern, decoupled architecture:

1. **Primary Backend API**: **FastAPI** (`app/api/`) mounted at `/api` on the ASGI app, exposing RESTful endpoints, typed Pydantic data contracts (`app/modules/contracts.py`), and real-time Server-Sent Events (SSE) tracking (`/api/events/{project_id}`).
2. **Primary Frontend Client**: **Decoupled SPA Frontend** (`frontend/`) built with **Svelte 5**, Vite, TypeScript, and Tailwind CSS, consuming `/api` endpoints via `src/lib/api.ts` and SSE via `src/lib/sse.ts`. In production, the build output is served directly as an SPA by FastAPI.
3. **Compute Kernels & Engines**: Pure Python compliance kernels (`app/engines/`, `app/modules/`, `app/services/`) remain framework-agnostic.

### Layer Structure

```text
Primary Frontend (frontend/)       → Vite + Svelte 5 SPA, TypeScript, Tailwind CSS
API Gateway (app/api/)             → FastAPI routers (/projects, /rules, /analyze, /events)
Data Contracts (app/modules/contracts.py) → Pydantic request/response schemas (mirrored in frontend/src/lib/types.ts)
Services (app/services/)           → Business logic, pipeline runner, tracker, Supabase persistence
Engines & Modules (app/modules/, app/engines/) → Pure Python compliance kernels (GC-001, CC-001, MC-001, Blue Halo)
```

### Data Flow

1. `main.py` (root) → boots uvicorn ASGI server
2. `app/main.py` → registers FastAPI router at `/api` and serves Svelte 5 SPA at `/`
3. Svelte client (`frontend/`) talks to `/api/*` via `src/lib/api.ts` and listens to live SSE progress events via `src/lib/sse.ts`
4. FastAPI routers validate requests using Pydantic schemas (`app/modules/contracts.py`), invoke domain services (`app/services/`), and run compute engines
5. Results return as typed Pydantic JSON or stream incrementally over SSE connections

### Frontend Guidelines (`frontend/`)

- **Framework**: Svelte 5 using the modern runes syntax (`$state`, `$derived`, `$props`, `$effect`).
- **Styling**: Tailwind CSS with custom theme variables matching BIM-Guard design tokens.
- **Contract Parity**: When Pydantic schemas in `app/modules/contracts.py` change, immediately update corresponding TypeScript interfaces in `frontend/src/lib/types.ts`.
- **ISO 19650 & CDE Governance**: Ensure all project and document entities carry ISO 19650 metadata (`project_code`, `originator`, `volume_system`, `level`, `type`, `role`, `number`, `suitability_code`, `revision_code`, `cde_state`). State transitions (`WIP` → `SHARED` → `PUBLISHED` → `ARCHIVED`) must be governed by `CDEStateMachine`.
- **API Client**: All HTTP calls go through `src/lib/api.ts`. Never use raw `fetch()` directly in components.
- **Real-Time Streaming**: Consume pipeline stage transitions (Validation → Parsing → Engine Run → Scoring → Reporting) using `subscribeToEvents()` from `src/lib/sse.ts`.
- **IFC 3D Viewer**: Encapsulated in `src/lib/components/IfcViewer.svelte` using `@thatopen/fragments`, `@thatopen/components`, and `web-ifc`.
- **Universal Data Table UX Standards**: Every data table in the application (Projects, Documents, Reports & BCF Topics/Deliverables, Rules Catalog, Extracted Rules Review, Audit Findings/Issues, Revit Sync, etc.) MUST provide rich, interactive, and user-friendly features:
  - Multiple selection with per-row checkboxes, header 'Select All' (with indeterminate state), selection counter badge, and clear selection action.
  - Full CRUD operations: creation/upload modals, details inspector modals with full properties, edit modals, and delete confirmations.
  - Floating or embedded `BulkActionBar` active on selection (bulk edit modal, bulk delete modal, bulk export to CSV/JSON/BCF).
  - Dedicated `TablePagination` with configurable page size selector (10, 25, 50, 100), range indicators, total items count, and page controls.
  - Reactive search, multi-field dropdown filters, and reset actions.
  - Interactive column header sorting (ascending/descending indicators).
  - Rich zero-state placeholders, loading skeletons, responsive horizontal scroll, and keyboard accessibility.
- **Reusable Frontend Component Architecture**: Always use established shared UI components from `src/lib/components/` instead of duplicating markup:
  - `<PageHeader>`: Top view header with category breadcrumbs, icon, title, subtitle, and action slots.
  - `<Modal>`: Standard modal dialog with backdrop blur, keyboard `Escape` closing, header with icon, and slot layout.
  - `<SortHeader>`: Sortable table column header with automatic sort direction indicators and ARIA attributes.
  - `<TableCheckbox>`: Accessible checkbox supporting indeterminate master toggle and row selection.
  - `<TablePagination>`: Dedicated table pagination component with page size selection.
  - `<BulkActionBar>`: Floating/inline bulk action toolbar when rows are selected.
  - `<EmptyState>`: Standardized zero-state card with icon, title, description, and primary CTA.
  - `<LoadingState>`: Spinner loading container with configurable messages.
  - `<SeverityBadge>`: Unified pill badge for severity levels and verdicts.
  - `<IsoGovernanceBadges>`: Standard ISO 19650 metadata tags (Suitability, Revision, CDE State).

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

## Coding Guidelines

Detailed coding rules covering the FastAPI backend, Svelte 5 frontend, and database operations are in [.github/instructions/project-specific.instructions.md](.github/instructions/project-specific.instructions.md).
