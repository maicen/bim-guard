# Contributing to BIM-Guard

## Setup

```bash
# Install dependencies
uv sync

# Optional: ML pipeline extras (docling, spaCy, openai)
uv sync --group ml-pipeline

# Run dev server (auto-reloads on file changes)
uv run uvicorn main:app --reload
```

## No automated tests are configured

Verify changes manually using the checklist below before committing.

## Manual Verification Checklist

Run through these after every non-trivial change:

- [ ] `uv run uvicorn main:app --reload` starts without errors in the terminal
- [ ] `/` — home page renders with "Welcome to BIM Guard"
- [ ] `/projects` — project list page renders; existing projects appear
- [ ] Create a project (fill form, submit) — redirects back to `/projects` with HTTP 303
- [ ] `/library` — documents panel and rules panel render
- [ ] Upload a PDF to the library — file appears in the documents list
- [ ] `/viewer` — IFC viewer canvas renders (no JS console errors)
- [ ] Load an IFC model in the viewer — model appears in 3D
- [ ] `/analyze` — analysis page renders; running an analysis returns results
- [ ] HTMX endpoints (e.g., rule extraction) — response is an HTML fragment, not a full page

## Coding Conventions

See [docs/CONVENTIONS.md](docs/CONVENTIONS.md) for the full style guide.
Key rules:

- Route files expose `setup_routes(rt)` — never register routes globally.
- POST mutations redirect with HTTP 303.
- Use `from app.db import db` for database access.
- Use MonsterUI components; do not hand-write raw HTML tags.
- Never import pipeline modules directly in route files — use `BIMGuard_App` from `orchestrator.py`.

## Dependency Management

All Python dependencies must be in `pyproject.toml`. Do **not** add or maintain `requirements.txt`.
