---
description: "Authoritative instructions for BIM-Guard: covers FastAPI backend API, Svelte 5 decoupled frontend, database-driven rules, and testing."
applyTo: "**"
---

# BIM Guard — Project-Specific Coding Guidelines


## Instructions Files Map

| File | Who reads it | What it defines |
| --- | --- | --- |
| README.md | Humans | What the project is |
| AGENTS.md, CLAUDE.md, .github/instructions/project-specific.instructions.md | Coding agents | How to build the project |
| DESIGN.md | Design agents | How the project should look and feel |


## Project Overview & Decoupled Architecture

**BIM Guard** is an OpenBIM compliance platform built on a decoupled architecture:
1. **Primary Backend API**: A **FastAPI API Gateway** (`app/api/`) delivering strict Pydantic REST contracts (`app/modules/contracts.py`), file streaming, and real-time Server-Sent Events (SSE) tracking (`/api/events/{project_id}`).
2. **Primary Frontend Client**: A **Decoupled SPA Frontend** (`frontend/`) built with **Svelte 5**, Vite, TypeScript, and Tailwind CSS. All UI features and views are built here and served in production by FastAPI.
3. **Compute engines & pipelines**: Physics engines and compliance evaluators (`app/engines/`, `app/modules/`, `app/services/`) operating framework-agnostic, driven dynamically by database-stored rules.

**Tech stack:** FastAPI · Svelte 5 (Vite + TypeScript) · Tailwind CSS · Supabase (Postgres & Storage) · IfcOpenShell · Server-Sent Events

---

## Getting Started

```bash
# Install backend dependencies
uv sync

# Run backend with auto-reload (available at http://127.0.0.1:8000, OpenAPI docs at /api/docs)
uv run uvicorn main:app --reload

# Run frontend in development (available at http://localhost:5173 with proxy to /api)
cd frontend && npm install && npm run dev

# Or launch both dev servers concurrently (cross-platform)
./run_server.sh         # macOS/Linux (or ./run_server.bat)
run_server.bat          # Windows
```

---

## API & Backend Rules (`app/api/**`)

1. **Always use Pydantic schemas**: Every route in `app/api/` must accept and return strict Pydantic models defined in `app/modules/contracts.py`. Never return raw HTML or unvalidated dictionaries.
2. **Dependency Injection**: Use FastAPI `Depends(...)` with provider functions in `app/api/dependencies.py` to access services.
3. **HTTP Status & Errors**: Raise standard `fastapi.HTTPException` with appropriate status codes (400 for bad parameters, 404 for missing entities, 409 for pipeline conflicts, 500 for unhandled exceptions).
4. **Real-Time Streaming**: Use Server-Sent Events via `app/api/events.py` and `PipelineTracker` for tracking multi-stage analysis workflows.
5. **Contract Parity**: When modifying API schemas, synchronize the corresponding TypeScript interfaces in `frontend/src/lib/types.ts`.

---

## Decoupled Frontend Rules (`frontend/**`)

1. **Svelte 5 Runes**: Use Svelte 5 modern syntax (`$state`, `$derived`, `$props`, `$effect`). Avoid legacy Svelte 3/4 stores or `export let`.
2. **TypeScript & Type Safety**: Always use `<script lang="ts">`. All API responses and model data must be typed via `src/lib/types.ts`.
3. **API Client Integration**: Make all backend calls through `src/lib/api.ts`. Never write ad hoc `fetch()` calls in individual components.
4. **Real-Time Updates via SSE**: Connect to `/api/events/{project_id}` using `subscribeToEvents()` from `src/lib/sse.ts` to stream analysis progress without polling.
5. **Styling**: Use Tailwind CSS utility classes following the design tokens in `DESIGN.md`.
6. **3D Viewport**: Reuse or extend `src/lib/components/IfcViewer.svelte` for IFC 3D visualization and BCF camera viewpoints.
7. **Views & Routing**: All UI views (projects, dashboards, analysis, rule editors) live in `frontend/src/routes/` or `frontend/src/lib/components/`.

---

## Database (Supabase) & Persistence

Use the shared Supabase persistence service and table adapters:

```python
from app.services.persistence import PersistenceService

_table = PersistenceService.get_table(
    "table_name",
    {"id": int, "name": str, "status": str},
    pk="id",
)

# CRUD
_table.insert({"name": "...", "status": "Draft"})
_table.get(id)                                         # returns None if missing
_table.update(updates={"name": "new", ...}, pk_values=id)  # use keyword args
_table.delete(id)
list(_table.rows)  # all rows
```

Timestamps are ISO 8601 strings:
```python
from datetime import datetime, timezone

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
```

**Never use `datetime.utcnow()`** — deprecated in Python 3.12+. Always use `datetime.now(timezone.utc)`.

---

## File Upload Handling

File uploads are handled by FastAPI endpoints accepting `UploadFile`:

```python
from fastapi import APIRouter, File, UploadFile
from app.services.object_storage import ObjectStorage

router = APIRouter()

@router.post("/upload")
async def upload_handler(file: UploadFile = File(...)):
    contents = await file.read()
    storage_ref = ObjectStorage().save_upload(
        file.filename or "upload.bin", contents, "uploads"
    )
    return {"storage_ref": storage_ref}
```

- Save files through `ObjectStorage.save_upload(...)`; local disk is only a disposable cache for downloaded Supabase objects.
- Never trust client filenames directly; normalize with `Path(name).name`.

---

## Database-Driven Rule Engine Architecture

All compliance and corrosion analysis workflows are strictly database-driven:
- **Zero Hardcoded Logic**: Multi-criteria scoring weights, risk band thresholds, material tables, flow velocity/dead-leg intervals, zone-to-environment mappings, and mitigations are read dynamically from database rules (`RuleService`), not hardcoded constants.
- **Corrosion Engine Catalogs**: `app/services/corrosion_rule_catalog.py` translates DB rules into engine lookups for `BIMGUARD-GC-001`, `BIMGUARD-CC-001`, and `BIMGUARD-MC-001`.
- **Live Catalog Reloading**: In-memory engine catalogs are refreshed via `reload_all_catalogs()` at the start of each analysis run.

---

## Testing Conventions

Automated testing is active and required for all changes:

### Backend Testing
- **Test execution**: `uv run pytest tests/`
- **Linting**: `uv run ruff check .`
- **API Tests**: Validate endpoint request/response payloads against Pydantic models (`tests/test_api_*.py`).
- **Engine Tests**: Validate physics and compliance rules pull dynamically from the database without hardcoded cutoffs (`tests/test_db_rules_workflow.py`).

### Frontend Testing & Verification
- **Build validation**: `cd frontend && npm run build` (verifies TypeScript types and Vite bundle)
- **Local testing**: `cd frontend && npm run dev` (runs at http://localhost:5173 with proxy to backend `/api`)

---

## Forbidden Patterns

Never use any of the following:

| Forbidden | Reason / Use instead |
|---|---|
| Creating UI in Python / FastHTML | Build all UI in `frontend/` using Svelte 5 + Tailwind CSS. |
| Hardcoding engineering cutoffs or scoring weights | Rules must be DB-driven. Read from database via `RuleService`. |
| Returning raw unvalidated dicts from `app/api/**` | Return typed Pydantic models from `app/modules/contracts.py`. |
| Ad hoc `fetch()` calls in Svelte components | Call backend methods via `frontend/src/lib/api.ts`. |
| Polling backend for analysis progress | Use Server-Sent Events via `subscribeToEvents()` in `frontend/src/lib/sse.ts`. |
| `datetime.utcnow()` | Use `datetime.now(timezone.utc)`. |
| `from typing import Optional` | Use Python 3.10+ union syntax (`X | None`). |
| Creating files in repo root (`./`) | Always place files in designated subfolders (`app/`, `frontend/`, `tests/`, `scripts/`, `docs/`, `data/`). |