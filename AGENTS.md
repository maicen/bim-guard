# AGENTS.md

## Project overview

BIM-Guard supports a dual architecture:
1. **FastAPI API Gateway** (`app/api/`) providing RESTful endpoints, typed Pydantic data contracts (`app/modules/contracts.py`), and real-time Server-Sent Events (SSE) tracking (`/api/events/{project_id}`).
2. **Decoupled SPA Frontend** (`frontend/`) built with Vite, Svelte 5, TypeScript, and Tailwind CSS.
3. **Legacy FastHTML + MonsterUI monolith** (`app/routes/`, `app/components/`) mounted alongside the API gateway at `/` during the migration period.
4. **Compute Kernels & Pipelines** (`app/engines/`, `app/modules/`, `app/services/`) remain framework-agnostic Python libraries.

## Essential commands

- Install backend dependencies: `uv sync`
- Install optional ML pipeline: `uv sync --group ml-pipeline`
- Run backend locally: `uv run uvicorn main:app --reload`
- Lint backend: `uv run ruff check .`
- Install frontend dependencies: `cd frontend && npm install`
- Run frontend locally: `cd frontend && npm run dev`
- Build frontend: `cd frontend && npm run build`
- Run full dev stack (FastAPI + Svelte): `./run_server.sh` (macOS/Linux) or `run_server.bat` (Windows)
- Run production stack (build + multi-worker): `./run_production_server.sh` (macOS/Linux) or `run_production_server.bat` (Windows)

The backend is available at `http://127.0.0.1:8000` (API docs at `/api/docs`).
The Svelte dev server runs at `http://localhost:5173`.

## Repo structure

- `app/api/` — FastAPI routers, dependency injection, and SSE event streaming
- `app/modules/contracts.py` — Pydantic data contracts for request/response validation
- `app/main.py` — bootstrap, route registration, and FastAPI mount at `/api`
- `app/routes/` — FastHTML handlers and HTMX endpoints (migration in progress)
- `app/components/` — reusable FastHTML UI building blocks
- `app/services/` — persistence, storage, and extraction services
- `app/modules/` — five-stage compliance pipeline
- `frontend/` — standalone Vite + Svelte 5 Single-Page Application client
- `supabase/migrations/` — schema changes tracked in-repo
- `data/cache/supabase-storage/` — disposable cache for downloaded Supabase Storage objects
- `static/` — CSS, JS, and viewer assets

## Working rules

- Use `uv` and `pyproject.toml` for Python dependency management; do not add or maintain a separate `requirements.txt`.
- For API endpoints (`app/api/**`), always define or reuse strict Pydantic schemas in `app/modules/contracts.py`.
- For Svelte components (`frontend/**`), use TypeScript and mirror Pydantic schemas in `frontend/src/lib/types.ts`.
- Prefer streaming real-time progress via Server-Sent Events (`/api/events/{project_id}`) over polling.
- For legacy FastHTML code under `app/routes/` and `app/components/`, maintain existing MonsterUI patterns.
- Read [docs/README.md](docs/README.md) for the authoritative markdown index before adding new documentation.
- For public modules, classes, and functions, add or update PEP 257 docstrings when changing behavior.

## Documentation map

- [README.md](README.md) — overview and local setup
- [docs/README.md](docs/README.md) — documentation index
- [docs/architecture.md](docs/architecture.md) — system architecture & migration
- [.github/instructions/project-specific.instructions.md](.github/instructions/project-specific.instructions.md) — app-specific coding conventions
- [DESIGN.md](DESIGN.md) — design direction
- [frontend/README.md](frontend/README.md) — Svelte frontend setup

## Quality bar

- Keep changes consistent with the dual FastAPI + Svelte architecture and preserve existing compute engine interfaces.
- Prefer small, targeted edits over broad rewrites.
- Validate backend with `uv run ruff check .` and `uv run pytest tests/test_api_*.py`.
- Validate frontend with `npm run build` in `frontend/`.

