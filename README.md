# BIM-Guard

## Live Demo

View the published demo at [https://maicen.github.io/bim-guard/](https://maicen.github.io/bim-guard/).

## Overview

BIM-Guard is a FastHTML and MonsterUI application for BIM compliance workflows. Users can upload IFC models and regulatory documents, extract rules, review a rule library, run compliance analysis, and export artifacts such as BCF reports.

The app is a single ASGI service. UI and backend routes live together in Python, with HTMX used for partial updates and MonsterUI for the component layer.

## Stack

- FastHTML and HTMX for routing and partial page updates
- MonsterUI for UI components
- IfcOpenShell for IFC parsing
- fastlite plus adapter services for persistence
- Supabase for the default database and storage backends
- LiteLLM for rule extraction across multiple providers

## Repository Layout

```
bim-guard/
├── app/
│   ├── main.py          # App bootstrap and route registration
│   ├── components/      # Reusable UI building blocks
│   ├── routes/          # HTTP handlers and HTMX responses
│   ├── services/        # Persistence, storage, and extraction services
│   ├── modules/         # 5-step compliance pipeline
│   ├── engines/         # Corrosion engines and demo data
│   └── views/           # Shared page layout helpers
├── data/                # Local runtime data, cache, and seed rule sets
├── docs/                # Supporting documentation
├── scripts/             # Migration and backfill utilities
├── static/              # CSS, JS, and viewer assets
├── main.py              # Uvicorn entrypoint (`uv run uvicorn main:app --reload`)
├── pyproject.toml       # Project metadata and dependencies
└── example.env          # Environment template for local development
```

## Getting Started

### 1. Install dependencies

```bash
uv sync
```

Python 3.12 or later is required. If you need the optional document-processing pipeline, install the extra group as well:

```bash
uv sync --group ml-pipeline
```

### 2. Configure environment variables

Create your local `.env` file from the template:

```bash
cp example.env .env
```

The template defaults to local SQLite and local file storage for development. Switch these to Supabase if you want to use the hosted backend:

```env
BIM_GUARD_DB_BACKEND=supabase
BIM_GUARD_STORAGE_BACKEND=supabase
SUPABASE_URL=...
SUPABASE_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
```

For rule extraction, set at least one provider key. Only one is needed:

```env
OPENAI_API_KEY=...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...
MISTRAL_API_KEY=...
```

You can also pin the default LLM model with `BIM_GUARD_RULE_MODEL`.

### 3. Run the app

```bash
uv run uvicorn main:app --reload
```

The app is available at [http://127.0.0.1:8000](http://127.0.0.1:8000). You can also start it with `python main.py` if you prefer a direct entrypoint.

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

6. Results are de-duplicated and displayed for review.
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
