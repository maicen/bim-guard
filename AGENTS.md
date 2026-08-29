# AGENTS.md

## Project overview

BIM-Guard is transitioning to a modern, decoupled architecture:
1. **Primary Backend API**: **FastAPI API Gateway** (`app/api/`) mounted at `/api`, providing RESTful endpoints, typed Pydantic data contracts (`app/modules/contracts.py`), and real-time Server-Sent Events (SSE) tracking (`/api/events/{project_id}`).
2. **Primary Frontend Client**: **Decoupled SPA Frontend** (`frontend/`) built with **Svelte 5**, Vite, TypeScript, and Tailwind CSS. All new UI features, views, and components must be implemented here.
3. **Legacy Monolith (Deprecated / Maintenance Only)**: FastHTML + MonsterUI (`app/routes/`, `app/components/`) mounted alongside the API gateway at `/` during the migration period. Do not build new features here; only perform critical maintenance fixes.
4. **Compute Kernels & Engines**: Compliance and corrosion physics engines (`app/engines/`, `app/modules/`, `app/services/`) remain framework-agnostic Python libraries driven dynamically by database-stored rules.

## Essential commands

- Install backend dependencies: `uv sync`
- Install optional ML pipeline: `uv sync --group ml-pipeline`
- Run backend locally: `uv run uvicorn main:app --reload`
- Lint backend: `uv run ruff check .`
- Run backend tests: `uv run pytest tests/`
- Install frontend dependencies: `cd frontend && npm install`
- Run frontend locally: `cd frontend && npm run dev`
- Build frontend: `cd frontend && npm run build`
- Run full dev stack (FastAPI + Svelte): `./run_server.sh` (macOS/Linux) or `run_server.bat` (Windows)
- Run production stack (build + multi-worker): `./run_production_server.sh` (macOS/Linux) or `run_production_server.bat` (Windows)

The backend is available at `http://127.0.0.1:8000` (OpenAPI interactive docs at `/api/docs`).
The Svelte dev server runs at `http://localhost:5173` (with `/api` proxy to backend).

## Repo structure

- `app/api/` — FastAPI routers, dependency injection, and SSE event streaming
- `app/modules/contracts.py` — Pydantic data contracts for request/response validation
- `frontend/` — Standalone Vite + Svelte 5 Single-Page Application client
  - `src/lib/api.ts` — Typed client communicating with `/api`
  - `src/lib/sse.ts` — EventSource subscriber for `/api/events/{project_id}`
  - `src/lib/types.ts` — TypeScript types mirroring Pydantic contracts
  - `src/lib/components/` — Svelte 5 components (IfcViewer, modals, tables, stats)
- `app/engines/` — Pure Python corrosion engines (GC-001, CC-001, MC-001)
- `app/services/` — Persistence, storage, corrosion rule catalog, and pipeline services
- `app/modules/` — Multi-stage compliance orchestrator and evaluators
- `app/main.py` — Application bootstrap, route registration, and FastAPI mount at `/api`
- `app/routes/` — Legacy FastHTML handlers and HTMX endpoints (deprecated / maintenance only)
- `app/components/` — Legacy FastHTML UI building blocks (deprecated / maintenance only)
- `supabase/migrations/` — Database schema migrations tracked in-repo
- `data/cache/supabase-storage/` — Disposable cache for downloaded Supabase Storage objects
- `static/` — CSS, JS, and viewer assets

## Working rules

- **Architecture Direction**: Target all new user-facing features to the Svelte 5 frontend (`frontend/`) and FastAPI backend (`app/api/`). Do not add new pages or features to legacy FastHTML routes.
- **Contract Parity**: When modifying API endpoints in `app/api/**`, always update or create strict Pydantic schemas in `app/modules/contracts.py` and synchronize TypeScript interfaces in `frontend/src/lib/types.ts`.
- **Database-Driven Rules**: Never hardcode engineering cutoffs, scoring weights, or rule classifications in Python engines. Rules must be read dynamically from the database via `RuleService` and `corrosion_rule_catalog.py`.
- **Real-Time Streaming**: Use Server-Sent Events (`/api/events/{project_id}`) for pipeline progress; avoid polling loops.
- **Package Management**: Use `uv` and `pyproject.toml` for Python dependencies; use `npm` in `frontend/` for frontend dependencies. Do not maintain a `requirements.txt`.
- **Quality & Docs**: For public modules, classes, and functions, add or update PEP 257 docstrings.

## Documentation map

- [README.md](README.md) — overview and local setup
- [CLAUDE.md](CLAUDE.md) — developer instructions and guidelines
- [docs/README.md](docs/README.md) — documentation index
- [docs/architecture.md](docs/architecture.md) — system architecture & migration
- [.github/instructions/project-specific.instructions.md](.github/instructions/project-specific.instructions.md) — app-specific coding conventions
- [DESIGN.md](DESIGN.md) — design direction
- [frontend/README.md](frontend/README.md) — Svelte frontend setup

## Quality bar

- Build features consistent with the decoupled FastAPI + Svelte 5 architecture while preserving framework-agnostic compute engine interfaces.
- Validate backend: `uv run ruff check .` and `uv run pytest tests/`.
- Validate frontend: `cd frontend && npm run build`.

