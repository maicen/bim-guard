# BIM-Guard

## Live Demo

View the published demo at [https://maicen.github.io/bim-guard/](https://maicen.github.io/bim-guard/).

## Overview

BIM-Guard is an OpenBIM compliance platform supporting a **FastAPI API Gateway** and a **decoupled Vite + Svelte 5 SPA Frontend**, backed by framework-agnostic Python physics engines and compliance pipelines. Users can upload IFC models and regulatory specifications, extract compliance rules, manage rule libraries, run multi-engine audits (galvanic corrosion, crevice corrosion, MIC, seismic clearance), and stream live progress via Server-Sent Events (SSE).

During migration, the legacy FastHTML + MonsterUI interface remains mounted alongside the API Gateway.

## Stack

- **Backend API**: FastAPI (REST + SSE) mounted with Pydantic contracts
- **Frontend SPA**: Svelte 5, Vite, TypeScript, Tailwind CSS (under `frontend/`)
- **Legacy UI**: FastHTML and MonsterUI (coexisting during transition)
- **IFC & BIM Processing**: IfcOpenShell, ThatOpenCompany / Web-IFC viewer
- **Database & Storage**: Supabase (Postgres) and Supabase Object Storage
- **LLM Engine**: LiteLLM for rule extraction across multiple providers

## Repository Layout

```
bim-guard/
├── app/
│   ├── api/             # FastAPI routers (/projects, /rules, /analyze, /events)
│   ├── main.py          # App bootstrap, FastHTML + FastAPI mount at /api
│   ├── components/      # Reusable FastHTML UI building blocks
│   ├── routes/          # FastHTML HTTP handlers and HTMX responses
│   ├── services/        # Persistence, runner, tracker, and extraction services
│   ├── modules/         # Compliance pipeline stages & Pydantic contracts
│   ├── engines/         # Corrosion physics engines (GC-001, CC-001, MC-001)
│   └── views/           # Shared page layout helpers
├── frontend/            # Standalone Vite + Svelte 5 Single-Page App (SPA)
│   ├── src/
│   │   ├── lib/         # Typed API client, SSE subscriber, UI components
│   │   └── routes/      # Projects, Audit, Rules, and 3D Viewer views
│   ├── package.json     # Frontend dependencies (Svelte 5, Tailwind CSS)
│   └── vite.config.ts   # Dev server with /api proxy to FastAPI
├── data/                # Local runtime data, cache, and seed rule sets
├── docs/                # Architectural and technical documentation
├── scripts/             # Migration and backfill utilities
├── static/              # CSS, JS, and viewer assets
├── main.py              # Uvicorn entrypoint (`uv run uvicorn main:app --reload`)
├── pyproject.toml       # Project metadata and backend dependencies
└── example.env          # Environment template for local development
```

## Getting Started

### 1. Install dependencies

```bash
uv sync
```

Python 3.12 or later (tested with 3.12.13) is required. If you need the optional document-processing pipeline, install the extra group as well:

```bash
uv sync --group ml-pipeline
```

### 2. Configure environment variables

Create your local `.env` file from the template:

```bash
cp example.env .env
```

Configure Supabase credentials in `.env`:

```env
SUPABASE_URL=...
SUPABASE_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
```

OpenRouter is the default provider for rule extraction and the Python agent:

```env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_SITE_URL=http://127.0.0.1:8000
OPENROUTER_APP_NAME=BIM Guard
```

Other extraction providers remain available:

```env
OPENAI_API_KEY=...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...
OLLAMA_API_BASE=http://localhost:11434
```

Pin the default app model with `BIM_GUARD_LLM_MODEL`; it defaults to
`openrouter/auto`.

Supabase schema changes are now tracked in-repo under `supabase/migrations/`. For a fresh Supabase environment, apply the migrations in that folder instead of relying on runtime table creation.

### 3. Run Development Servers (FastAPI Backend + Svelte Frontend)

You can launch both the backend and frontend concurrently using the cross-platform launcher:

- **macOS / Linux / WSL**: `./run_server.sh` (or `./run_server.bat`)
- **Windows**: `run_server.bat`

Alternatively, run each service individually in separate terminals:

**Backend API & app:**
```bash
uv run uvicorn main:app --reload
```
The app is available at [http://127.0.0.1:8000](http://127.0.0.1:8000).
Interactive FastAPI Swagger docs are at [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs).

**Svelte SPA Frontend:**
```bash
cd frontend
npm install
npm run dev
```
The Svelte frontend is available at [http://localhost:5173](http://localhost:5173). Requests to `/api/*` are automatically proxied to the backend at port 8000.

### 4. Run Production Server

To build the frontend and serve the compiled single-page application with multi-worker Uvicorn:

- **macOS / Linux / WSL**: `./run_production_server.sh` (or `./run_production_server.bat`)
- **Windows**: `run_production_server.bat`

### 5. Run the Python agent

The terminal agent uses OpenRouter, repository-local coding tools, bounded tool
turns and cost, server-side web search, and append-only JSONL sessions:

```bash
uv run bim-guard-agent
```

Use `--model`, `--max-steps`, `--max-cost`, or `--no-web-search` to override
the environment for one run. Inside the agent, `/model` fetches the current
OpenRouter catalogue, `/new` starts a fresh session, and `/help` lists commands.
Session logs are written under `data/agent-sessions/` and ignored by Git.

## Main Routes

- `/` landing page
- `/dashboard` dashboard
- `/projects` project management
- `/library` document and rule library
- `/library/documents` document uploads
- `/library/rules/extract` AI-assisted rule extraction
- `/analyze` compliance analysis
- `/viewer` IFC viewer

## Deployment

### Docker Compose

```bash
docker compose up --build
```

`docker-compose.yml` wires the Supabase environment variables from your shell or `.env` file and mounts a cache volume for downloaded artifacts.

### Render

The repository includes `render.yaml` for Docker-based deployment on Render. Set the Supabase variables and any AI provider keys you intend to use.

## Notes

- `app/main.py` is the application bootstrap used by the root `main.py` entrypoint.
- `README.md`, `AGENTS.md`, `CLAUDE.md`, and `.github/instructions/project-specific.instructions.md` are the main source files for project guidance.
- There is no separate `requirements.txt`; dependency management is handled with `uv` in `pyproject.toml`.

1. Results are de-duplicated and displayed for review.
2. Accepted rules can be saved directly to the Rule Library.

## Documentation Map

Use [docs/README.md](docs/README.md) as the authoritative index for repository documentation. It groups markdown files by purpose and marks which docs are current vs. archival/reference.

## Next Development Steps

- Verify the reported issues.
- Verify the BCF exported.

Output rule fields:

- `ref`
- `desc`
- `target`

## Notes

- If `.env` is not loaded (for custom scripts/tests), call `load_env_file()` from `app.utils` before creating AI extraction services.
- Document upload validation includes extension, MIME type, and content checks.

## Python Docstrings and API Docs

This repository follows [PEP 257](https://peps.python.org/pep-0257/) docstring conventions and uses Python's built-in [pydoc](https://docs.python.org/3/library/pydoc.html) for API documentation.

Lint docstring style (PEP 257) with Ruff:

```bash
uv run ruff check .
```

Generate terminal docs for a module:

```bash
uv run python -m pydoc app.modules.orchestrator
```

Generate HTML docs for a module:

```bash
uv run python -m pydoc -w app.modules.orchestrator
```

Docstring policy for contributors:

- Add docstrings for new public modules, classes, and functions.
- Keep docstrings imperative and concise (PEP 257).
- Include parameters/return behavior when it improves clarity.
