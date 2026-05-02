# BIM-Guard Coding Conventions

This document consolidates conventions from `CLAUDE.md` and
`.github/instructions/project-specific.instructions.md` into one scannable reference.
When in doubt, the project-specific instructions file is authoritative.

---

## Route Conventions

- Every route module **must** expose `setup_routes(rt)` and never register routes globally.
- Call `setup_routes` from `app/main.py → _setup_routes()`.
- POST mutations redirect with HTTP **303** via `redirect_see_other("/target")`.
- HTMX endpoints return **HTML fragments only** — no `Title(...)` or `DashboardLayout(...)`.
- Prefix route-internal helpers with `_` (e.g., `_build_row`).
- Handle errors by returning a component (e.g., `MessageAlert`), never `raise HTTPException`.

## UI Composition

- Every full page: `Title("…"), DashboardLayout(Container(…))`.
- Use MonsterUI components (`Card`, `Grid`, `Button`, `Alert`, …). Do **not** hand-write raw HTML tags.
- Status feedback → `Alert` component.
- Action icon buttons (`ViewAction`, `EditAction`, `CreateAction`, `BackAction`) live in `app/components/ui/`.
- Repeated UI must be extracted to `app/components/` — prefer `app/components/ui.py` patterns.

## Database Access

- Single accessor: `PersistenceService.get_table(...)` in `app/services/persistence.py`.
- Runtime default is Supabase (`BIM_GUARD_DB_BACKEND=supabase`), with SQLite as optional fallback.
- Do not query Supabase directly from routes; keep DB access inside services.
- Table adapters expose a unified interface for `projects`, `documents`, and `rules`.

## File Uploads

- Handler must be `async def` and accept `UploadFile`.
- Save through `ObjectStorage.save_upload(...)` in `app/services/object_storage.py`.
- Runtime default is Supabase Storage (`BIM_GUARD_STORAGE_BACKEND=supabase`), with local storage as optional fallback.
- Store returned references (`sb://bucket/key` or local path) in DB records instead of constructing paths in routes.

## Naming Conventions

| Layer | Pattern | Example |
|-------|---------|---------|
| Route module | `{domain}.py` | `projects.py` |
| Service module | `{domain}_service.py` | `projects_service.py` |
| UI component module | `{domain}_ui.py` | `projects_ui.py` |
| Internal helper | `_{name}` | `_build_row` |

- Class names: `PascalCase` (`ProjectsService`, `RuleService`).
- DB table names: `snake_case` plural (`projects`, `documents`, `rules`).

## Module Pipeline

- Routes call the pipeline **only** through `orchestrator.py` (`BIMGuard_App`).
- Never import pipeline modules (Module1–5) directly in route files.
- Module methods are scaffolded stubs; implementation goes inside each module, not in routes or services.

## IFC Viewer (JS)

- Pure CDN ESM approach — no bundler.
- Imports pinned to specific versions from `esm.sh` in `static/js/ifc-viewer.js`.
- Entry point exported as `initViewer(containerId)`.
- Do not change CDN import strategy without a compelling reason.

## Timestamps

- Use ISO 8601 UTC strings: `datetime.utcnow().isoformat()`.
- Store as string timestamp columns in DB records (Supabase default backend).
