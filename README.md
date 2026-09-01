# BIMGUARD AI: Agentic RAG Pipeline for OpenBIM Compliance

BIMGUARD AI is an Automated Code Compliance Checking (ACCC) platform that bridges OpenBIM standards (IFC, BCF, IDS) with large language models. This repository contains the Python-based compliance engines and the data ingestion pipeline used to evaluate structural and material integrity against international building codes.

## Project Scope
This project focuses on two primary compliance modules:
*   **GC-001 (Seismic):** Evaluates nonstructural component clearance volumes and clash detection against seismic bracing standards (e.g., FEMA E-74, ASCE 7-22).
*   **CC-001 (Piping & Corrosion):** Evaluates material degradation, galvanic mismatch, and environmental exposure against atmospheric standards (e.g., ISO 9223, MBIE B2).

## The Agentic RAG Methodology
To eliminate AI hallucination and ensure strict engineering accuracy, this project utilizes a "Walled Garden" Retrieval-Augmented Generation (RAG) architecture:
1.  **Retrieval (`fetch_standards.py`):** An LLM-native web scraping script powered by the Firecrawl API dynamically retrieves open-access government building codes and manufacturer material specifications, converting them into clean Markdown.
2.  **Augmentation (`compile_for_notebooklm.py`):** A custom compilation pipeline packages the OpenBIM Python logic (`IfcOpenShell`), static JSON rule packs, and scraped standards into targeted, domain-isolated Markdown exports (`bimguard_seismic_rules.md` and `bimguard_corrosion_rules.md`).
3.  **Generation (Gemini Notebooks):** The compiled domains are fed into isolated Google Gemini Notebook (NotebookLM) workspaces. The AI reasoning engine evaluates the Python codebase strictly against the ingested facts (and uploaded proprietary, IP-protected PDFs) to identify gaps in the compliance algorithms.

## Repository Structure
*   `/app/engines/` - Core Python kernels for galvanic, crevice, and seismic clearance analysis.
*   `/data/rulesets/` - Static JSON configurations defining fallback rules for material mismatch (MM-001) and cross-material (XM-001) interactions.
*   `/scripts/` - The AI data ingestion and Markdown compilation pipeline.

## Usage
To pull a new open-access standard and recompile the AI workspace:
```bash
# 1. Search and extract an online standard via Firecrawl
python scripts/fetch_standards.py "MBIE B2 durability for metal components" mbie_durability --corrosion --search

# 2. Compile the updated codebase and standards for NotebookLM
python scripts/compile_for_notebooklm.py
```

## Extended Documentation & Application Stack

## BIM-Guard

### Live Demo

View the published demo at [https://maicen.github.io/bim-guard/](https://maicen.github.io/bim-guard/).

### Overview

BIM-Guard is an OpenBIM compliance platform built on a modern decoupled architecture: a high-performance **FastAPI API Gateway** and a **decoupled Vite + Svelte 5 SPA Frontend**, backed by framework-agnostic Python physics engines and compliance pipelines. Users can upload IFC models and regulatory specifications, extract compliance rules, manage rule libraries, run multi-engine audits (galvanic corrosion, crevice corrosion, MIC, seismic clearance), and stream live progress via Server-Sent Events (SSE).

### Stack

- **Backend API**: FastAPI (REST + SSE) with strict Pydantic data contracts
- **Frontend SPA**: Svelte 5, Vite, TypeScript, Tailwind CSS (under `frontend/`)
- **IFC & BIM Processing**: IfcOpenShell, ThatOpenCompany / Web-IFC viewer
- **Database & Storage**: Supabase (Postgres) and Supabase Object Storage
- **LLM Engine**: LiteLLM for rule extraction across multiple providers

### Repository Layout

```
bim-guard/
├── app/
│   ├── api/             # FastAPI routers (/projects, /rules, /analyze, /events)
│   ├── main.py          # App bootstrap, FastAPI API Gateway, and SPA static mount
│   ├── services/        # Persistence, runner, tracker, and extraction services
│   ├── modules/         # Compliance pipeline stages & Pydantic contracts
│   └── engines/         # Corrosion physics engines (GC-001, CC-001, MC-001)
├── frontend/            # Standalone Vite + Svelte 5 Single-Page App (SPA)
│   ├── src/
│   │   ├── lib/         # Typed API client, SSE subscriber, Svelte 5 components
│   │   └── routes/      # Projects, Audit, Rules, and 3D Viewer views
│   ├── package.json     # Frontend dependencies (Svelte 5, Tailwind CSS)
│   └── vite.config.ts   # Dev server with /api proxy to FastAPI
├── data/                # Local runtime data, cache, and seed rule sets
├── docs/                # Architectural docs, validation reports, and planning
├── scripts/             # Evaluation, build, benchmark, and utility scripts
├── tests/               # Pytest test suites for the backend
├── static/              # CSS, JS, and viewer assets
├── main.py              # Uvicorn entrypoint (`uv run uvicorn main:app --reload`)
├── pyproject.toml       # Project metadata and backend dependencies
└── example.env          # Environment template for local development
```

### Getting Started

#### 1. Install dependencies

```bash
uv sync
```

Python 3.12 or later (tested with 3.12.13) is required. If you need the optional document-processing pipeline, install the extra group as well:

```bash
uv sync --group ml-pipeline
```

#### 2. Configure environment variables

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

#### 3. Run Development Servers (FastAPI Backend + Svelte Frontend)

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

#### 4. Run Production Server

To build the frontend and serve the compiled single-page application with multi-worker Uvicorn:

- **macOS / Linux / WSL**: `./run_production_server.sh` (or `./run_production_server.bat`)
- **Windows**: `run_production_server.bat`

#### 5. Run the Python agent

The terminal agent uses OpenRouter, repository-local coding tools, bounded tool
turns and cost, server-side web search, and append-only JSONL sessions:

```bash
uv run bim-guard-agent
```

Use `--model`, `--max-steps`, `--max-cost`, or `--no-web-search` to override
the environment for one run. Inside the agent, `/model` fetches the current
OpenRouter catalogue, `/new` starts a fresh session, and `/help` lists commands.
Session logs are written under `data/agent-sessions/` and ignored by Git.

### Application Architecture & Routes

#### Svelte 5 SPA Client (`frontend/`)
The primary modern client runs on `http://localhost:5173`:
- **Dashboard**: System overview, recent runs, and status
- **Projects**: Project creation, IFC upload, and metadata inspection
- **Documents**: Document management and text extraction
- **Rule Library**: Rule and folder catalog management
- **Rule Extraction**: AI-assisted rule extraction from documents
- **Audit / Analyze**: Multi-engine MEP corrosion & architectural compliance
- **3D Viewer**: Interactive OpenBIM viewport and BCF clash inspection
- **Reports**: BCF issue export, Excel/PDF compliance reports

#### FastAPI API Gateway (`/api`)
The RESTful backend with interactive Swagger docs at `http://127.0.0.1:8000/api/docs`:
- `/api/projects` — Project CRUD, model file uploads, IFC metadata
- `/api/documents` — Document upload, PDF text extraction
- `/api/rules` — Rule folders, rulesets, and custom rule CRUD
- `/api/analyze` — Compliance and corrosion analysis execution
- `/api/events/{project_id}` — Real-time Server-Sent Events (SSE) progress streaming

### Deployment

#### Docker Compose

```bash
docker compose up --build
```

`docker-compose.yml` wires the Supabase environment variables from your shell or `.env` file and mounts a cache volume for downloaded artifacts.

#### Render

The repository includes `render.yaml` for Docker-based deployment on Render. Set the Supabase variables and any AI provider keys you intend to use.

### Notes

- `app/main.py` is the application bootstrap used by the root `main.py` entrypoint.
- `README.md`, `AGENTS.md`, `CLAUDE.md`, and `.github/instructions/project-specific.instructions.md` are the main source files for project guidance.
- There is no separate `requirements.txt`; dependency management is handled with `uv` in `pyproject.toml`.

1. Results are de-duplicated and displayed for review.
2. Accepted rules can be saved directly to the Rule Library.

### Documentation Map

Use [docs/README.md](docs/README.md) as the authoritative index for repository documentation. It groups markdown files by purpose and marks which docs are current vs. archival/reference.

### Next Development Steps

- Verify the reported issues.
- Verify the BCF exported.

Output rule fields:

- `ref`
- `desc`
- `target`

### Notes

- If `.env` is not loaded (for custom scripts/tests), call `load_env_file()` from `app.utils` before creating AI extraction services.
- Document upload validation includes extension, MIME type, and content checks.

### Python Docstrings and API Docs

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
