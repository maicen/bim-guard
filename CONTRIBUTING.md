# Contributing to BIM-Guard

Thanks for your interest in contributing! This guide covers everything needed to get
a working local setup and submit a change — no internal credentials required.

## Choose a setup path

| | Docker Compose (recommended to start) | Native (`uv` + `npm`) |
|---|---|---|
| Needs | Docker only | Python 3.12+ / `uv`, Node.js / `npm` |
| External accounts | None | None (local Supabase/Neo4j optional) |
| Best for | Trying the app, full-stack changes | Fast iteration, hot reload |

### Option A — Docker Compose

Don't have Docker installed? See [Installing Docker](docs/manual/infrastructure/docker-installation.md)
for step-by-step instructions on macOS, Windows, and Linux first.

```bash
cp example.env .env
cp frontend/.env.example frontend/.env
cp docker/supabase/.env.example docker/supabase/.env

docker compose up --build
```

Once the containers are healthy, apply the database schema (the self-hosted Supabase
stack starts with an empty database):

```bash
uv run python scripts/migrate_production.py --apply
```

Visit [http://localhost:8000](http://localhost:8000) and use the **"Sign in as dev test
user"** button on the login screen — no Google OAuth setup required.

### Option B — Native (uv + npm)

```bash
uv sync
# Optional: ML pipeline extras (docling, spaCy, LLM providers)
uv sync --group ml-pipeline

cp example.env .env
# Fill in Supabase credentials — point at a local `supabase start` stack (see
# example.env for the "Disposable CLI Stack" option) or the Docker Compose stack
# from Option A running alongside this.

cd frontend
cp .env.example .env   # fill in VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY
npm install
cd ..

uv run uvicorn main:app --reload   # backend: http://127.0.0.1:8000
cd frontend && npm run dev          # frontend: http://localhost:5173
```

Or launch both together: `./run_server.sh` (macOS/Linux) or `run_server.bat` (Windows).

See [Environment Setup](docs/manual/infrastructure/environment-setup.md) for the full
walkthrough, including the local-LLM-via-Ollama option.

> **Internal team members**: if you have access to the shared credentials vault
> (hosted Supabase project, OpenRouter key, etc.), see the "Dev-Only Hosted Supabase"
> section in `example.env` instead of running a local database. This isn't available
> to external contributors — use Option A or B above.
>
> **Security note**: credentials were accidentally committed in commit `175b987`
> (Sept 28 2026) and have since been **rotated**. If you cloned the repo before those
> credentials were rotated, discard any `.env` you copied from that commit and request
> fresh values from the repo owner — the secrets in git history are dead, do not use them.

## Automated Tests

```bash
uv run ruff check .
uv run pytest tests/ -v
```

The test suite is grouped by pytest markers (`slow`, `llm`, `integration`) and runs in
parallel by default (`pytest-xdist`, `-n auto -m 'not slow'`). Plain `pytest` already
excludes slow tests.

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

- [ ] `uv run uvicorn main:app --reload` (or `docker compose up`) starts without errors
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

## Submitting changes

1. Commit with a clear, human-readable message (no AI-attribution trailers — see
   `CLAUDE.md`).
2. Push and open a pull request describing the change and how you verified it (tests
   run, manual checklist items exercised).
3. CI runs lint, backend tests, and a frontend build on every PR.

## Where to go next

- **Something broken in setup?** Check the Troubleshooting section at the bottom of
  [Installing Docker](docs/manual/infrastructure/docker-installation.md), or open an issue.
- **Architecture questions**: see `CLAUDE.md` and `AGENTS.md` for how the codebase is
  organized and the rules coding agents (and contributors) follow in this repo.
- **Product/user documentation**: `docs/manual/` (built with MkDocs — `mkdocs serve` to
  preview locally).
