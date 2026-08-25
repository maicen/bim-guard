# AGENTS.md

## Project overview

This repository is a single-process FastHTML + MonsterUI application for BIM compliance workflows. The backend, UI, and HTMX interactions live together in Python under `app/`; there is no separate React or frontend build.

## Essential commands

- Install dependencies: `uv sync`
- Install optional ML pipeline: `uv sync --group ml-pipeline`
- Run locally: `uv run uvicorn main:app --reload`
- Lint: `uv run ruff check .`

The app is available at `http://127.0.0.1:8000`.

## Repo structure

- `app/main.py` — bootstrap and route registration
- `app/routes/` — HTTP handlers and HTMX endpoints
- `app/components/` — reusable UI building blocks
- `app/services/` — persistence, storage, and extraction services
- `app/modules/` — five-stage compliance pipeline
- `supabase/migrations/` — schema changes tracked in-repo
- `data/cache/supabase-storage/` — disposable cache for downloaded Supabase Storage objects
- `static/` — CSS, JS, and viewer assets

## Working rules

- Use `uv` and `pyproject.toml` for dependency management; do not add or maintain a separate `requirements.txt`.
- Prefer the existing FastHTML + MonsterUI patterns already used in `app/components/` and `app/routes/` instead of inventing ad hoc HTML.
- Keep route files focused on composition; move repeated UI patterns into shared components in `app/components/`.
- For code under `app/**`, follow the detailed conventions in [.github/instructions/project-specific.instructions.md](.github/instructions/project-specific.instructions.md).
- Read [docs/README.md](docs/README.md) for the authoritative markdown index before adding new documentation.
- For public modules, classes, and functions, add or update PEP 257 docstrings when changing behavior.

## Documentation map

- [README.md](README.md) — overview and local setup
- [docs/README.md](docs/README.md) — documentation index
- [.github/instructions/project-specific.instructions.md](.github/instructions/project-specific.instructions.md) — app-specific coding conventions
- [DESIGN.md](DESIGN.md) — design direction

## Quality bar

- Keep changes consistent with the repo’s FastHTML architecture and reuse existing service/component boundaries.
- Prefer small, targeted edits over broad rewrites.
- Validate with the smallest relevant command, typically `uv run ruff check .` for Python changes.
