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
# Install dependencies
uv sync

# Install optional ML pipeline dependency group
uv sync --group ml-pipeline

# Run development server
uv run uvicorn main:app --reload

# Run with specific host/port
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

There are no automated tests or lint commands configured.

## Dependency Management Rule

All Python dependencies must be managed via uv and declared in pyproject.toml (including optional dependency groups). Do not add or maintain separate requirements.txt files.

## Docstring and API Documentation Rule

- Follow [PEP 257](https://peps.python.org/pep-0257/) for Python docstrings.
- Use Python [pydoc](https://docs.python.org/3/library/pydoc.html) to inspect and generate API docs.
- For new public modules/classes/functions, add or update docstrings in the same change.

Useful commands:

```bash
uv run ruff check .
uv run python -m pydoc app.modules.orchestrator
uv run python -m pydoc -w app.modules.orchestrator
```

## Architecture

BIM-Guard is a FastHTML + MonsterUI web application for BIM (Building Information Modeling) compliance checking. Users upload IFC models and specification documents, extract compliance rules, and generate compliance reports.

### Layer Structure

```text
Routes (app/routes/)       → HTTP handlers, HTMX responses
Services (app/services/)   → Business logic, Supabase persistence
Components (app/components/) → Reusable FastHTML UI elements
Modules (app/modules/)     → 5-step compliance pipeline
```

### Key Technologies

- **FastHTML** — Python framework where HTML is generated programmatically as Python objects (no template files). Every UI element is a Python function returning HTML nodes.
- **MonsterUI** — Tailwind-based component library layered on top of FastHTML. Components like `Card`, `Button`, `Grid` are imported and used directly.
- **Supabase** — Managed Postgres persistence accessed through `PersistenceService` and the table adapters in `app/services/persistence.py`.
- **HTMX** — Used via FastHTML's `hx_*` attributes for partial page updates without full reloads.

### Data Flow

1. `main.py` (root) → boots uvicorn
2. `app/main.py` → initializes FastHTML app, mounts all routes
3. Routes call services for data; services call Supabase through the shared persistence layer
4. Routes return FastHTML components (which become HTML) or trigger HTMX swaps

### Database

Supabase Postgres stores the application data. The primary tables are:

- `projects` — IFC project metadata + file paths
- `documents` — Uploaded PDFs with extracted text
- `rules` — Compliance rules with JSON `parameters` field

### Compliance Pipeline (app/modules/)

Five sequential modules — most are stubs awaiting implementation:

1. **Module1_DocParser** — PDF text extraction and section preprocessing
2. **Module2_IFCRead** — IFC file parsing (stub)
3. **Module3_RuleBuilder** — NLP → structured rules (stub, AI integration point)
4. **Module4_Comparator** — IFC vs rules validation (stub)
5. **Module5_Reporter** — Report generation (stub)

`orchestrator.py` contains `BIMGuard_App` as the entry point for running the full pipeline.

### IFC Viewer

The viewer route (`app/routes/viewer.py`) loads a 3D model in-browser using `@thatopen/fragments`, `@thatopen/components`, and `web-ifc` loaded from CDN. The loader script is at `static/js/ifc-viewer-loader.js`.

### UI Conventions

- Page structure: `DashboardLayout` wraps all pages, with `AppSidebar` and `AppHeader` from `app/components/layout.py`
- Action icon buttons (`ViewAction`, `EditAction`, `CreateAction`, `BackAction`) are in `app/components/ui.py`
- Each domain has a `*_ui.py` component file and a `*_service.py` service file
- File uploads are stored in Supabase Storage with UUID-prefixed object keys; downloaded objects are cached under `data/cache/supabase-storage/`

## Coding Guidelines

Detailed coding rules covering UI patterns, HTMX conventions, route structure, database operations, file uploads, and the BIM module pipeline are in [.github/instructions/project-specific.instructions.md](.github/instructions/project-specific.instructions.md). This file applies automatically to all code under `app/` and is the authoritative reference for how to write code in this project.
