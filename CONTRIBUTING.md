# Contributing to BIM-Guard

## Setup

```bash
# Install backend dependencies
uv sync

# Optional: ML pipeline extras (docling, spaCy, LLM providers)
uv sync --group ml-pipeline

# Backend dev server (auto-reloads on file changes)
uv run uvicorn main:app --reload

# Frontend dependencies and dev server
cd frontend && npm install && npm run dev
```

Or launch both together: `./run_server.sh` (macOS/Linux) or `run_server.bat` (Windows).

## Automated Tests

```bash
uv run ruff check .
uv run pytest tests/ -v
```

The test suite is grouped by pytest markers (`slow`, `llm`, `integration`) and
runs in parallel by default (`pytest-xdist`, `-n auto -m 'not slow'`). Plain
`pytest` already excludes slow tests.

```bash
uv run pytest -m slow       # only the slow tests (full engine/pipeline runs)
uv run pytest -m ""          # everything, including slow tests
uv run pytest -m "not llm"   # skip tests that call an LLM
```

For frontend changes, also run:

```bash
cd frontend && npm run build
```

## Manual Verification Checklist

Run through these after any non-trivial UI or API change:

- [ ] `uv run uvicorn main:app --reload` starts without errors
- [ ] `cd frontend && npm run dev` starts without errors; `http://localhost:5173` loads
- [ ] Create a project, upload an IFC model, and confirm it appears in Projects
- [ ] Upload a document and confirm it appears in Documents
- [ ] Run rule extraction on an uploaded document and confirm draft rules appear for review
- [ ] `/analyze` and `/arch` — running an analysis returns results and the SSE progress stream updates live
- [ ] The 3D viewer renders a loaded IFC model with no console errors

## Coding Conventions

See [docs/CONVENTIONS.md](docs/CONVENTIONS.md) for the full style guide. Key rules:

- **Backend**: FastAPI routers under `app/api/` use `APIRouter` + `Depends(...)` for
  dependency injection; every endpoint accepts and returns strict Pydantic models from
  `app/modules/contracts.py` — never raw dicts.
- **Frontend**: Svelte 5 runes only (`$state`, `$derived`, `$props`, `$effect`); all HTTP
  calls go through `frontend/src/lib/api.ts`, never raw `fetch()` in a component.
- **Database-driven rules**: Never hardcode engineering cutoffs, scoring weights, or rule
  classifications in Python engines — read them from the database via `RuleService`.
- **No AI attribution in commits**: see [CLAUDE.md](CLAUDE.md).

## Dependency Management

All Python dependencies must be declared in `pyproject.toml` (including optional
dependency groups) and managed via `uv`. Do **not** add or maintain a separate
`requirements.txt`. All frontend dependencies must be declared in `frontend/package.json`.
