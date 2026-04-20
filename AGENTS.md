# AGENTS.md

## Architecture

BIM-Guard is a **FastHTML full-stack application**. The UI and backend routes are served together from a single ASGI process — there is no separate frontend project, no React build step, and no `frontend/` folder. UI elements are generated as Python FastTags (FT) and delivered through HTMX partial swaps.

## Setup commands

- Install deps: `uv sync`
- Install optional ML deps group: `uv sync --group ml-pipeline`
- Start server: `uv run uvicorn main:app --reload`

## Dependency Management Rule

All Python dependencies must be managed via `uv` and declared in `pyproject.toml` (including optional dependency groups). Do not add or maintain separate `requirements.txt` files.

The app is available at `http://127.0.0.1:8000`.

## Docstring and API Documentation Rule

- Follow [PEP 257](https://peps.python.org/pep-0257/) for Python docstrings.
- Use Python [pydoc](https://docs.python.org/3/library/pydoc.html) when validating or generating API docs.
- For new public modules/classes/functions, add or update docstrings as part of the same change.

Useful commands:

- `uv run ruff check .`
- `uv run python -m pydoc app.modules.orchestrator`
- `uv run python -m pydoc -w app.modules.orchestrator`

## Instructions Files Map

| File | Who reads it | What it defines |
| --- | --- | --- |
| README.md | Humans | What the project is |
| AGENTS.md, CLAUDE.md, .github/instructions/project-specific.instructions.md | Coding agents | How to build the project |
| DESIGN.md | Design agents | How the project should look and feel |
