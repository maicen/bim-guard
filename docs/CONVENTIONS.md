# BIM-Guard Coding Conventions

This document consolidates authoritative conventions across the decoupled architecture:
1. **Backend API**: FastAPI (REST + SSE) mounted with Pydantic contracts
2. **Frontend Client**: Svelte 5, Vite, TypeScript, Tailwind CSS (under `frontend/`)
3. **Database & Engines**: Pure Python physics kernels, Supabase persistence, database-driven rules

When in doubt, `CLAUDE.md` and `.github/instructions/project-specific.instructions.md` are authoritative.

---

## 1. FastAPI API Conventions (`app/api/**`)

- **Routing**: Use `APIRouter(prefix="/...", tags=["..."])` and register in `app/api/__init__.py`.
- **Strict Pydantic Contracts**: All endpoints must accept and return strict Pydantic models defined in `app/modules/contracts.py`. Never return raw dicts or unvalidated payloads.
- **Dependency Injection**: Use FastAPI `Depends(...)` with providers in `app/api/dependencies.py` to access services (`ProjectsService`, `RuleService`, etc.).
- **Error Handling**: Raise standard `fastapi.HTTPException` with appropriate status codes (400, 404, 409, 500) and descriptive detail strings.
- **Real-Time Progress Streaming**: Use Server-Sent Events via `app/api/events.py` and `PipelineTracker` for multi-stage analysis workflows.

---

## 1a. API Standards (Enforced by `tests/test_api_contracts.py`)

Every route registered on `app.main.app` is checked automatically by
`tests/test_api_contracts.py`, which walks the live route table -- this is
not just a style guide, a failing route breaks `pytest`. When adding a new
endpoint:

- **Strict response contract**: set `response_model=` (or annotate the
  return type) to a real Pydantic model/union/generic from
  `app/modules/contracts.py` -- never a bare `dict`/`list[dict]`. A route
  that genuinely returns a raw file/stream (`FileResponse`,
  `StreamingResponse`, `PlainTextResponse`, an image) is exempt; add it to
  `RESPONSE_MODEL_EXEMPT` in the test file alongside the existing entries.
- **Auth-or-Public, always a declared decision**: every route must either
  depend (directly or transitively, e.g. through `get_authorized_project`)
  on `get_current_user`/`get_current_user_flexible` from `app/auth.py`, or
  carry the `"Public"` OpenAPI tag if it is deliberately open (public
  reference data, or an OAuth handshake step that necessarily precedes
  having a token). There is no silent-gap option.
- **Tags**: every route needs at least one tag, and every tag used anywhere
  must be registered with a description in `TAGS_METADATA` in `app/main.py`
  -- this is what gives `/api/docs` real per-group descriptions instead of
  bare names.
- **Summary**: every route needs a `summary=`.
- **Versioning**: BIM-Guard does not URL-version its API (no `/api/v1`).
  `app.main.app`'s `version=` is the single source of truth for the
  deployed API's version; a breaking change bumps it and marks the
  affected route(s) `deprecated=True` for one release before removal,
  rather than forking the URL. Only introduce an actual `/api/v1` prefix
  (as an additive second `APIRouter`) if a breaking change is otherwise
  unavoidable.
- **Programmatic API parity**: a route handler must delegate to the same
  service/engine class or function documented as the programmatic surface
  in `docs/architecture.md` §8 (`app/services/__init__.py` and
  `app/engines/__init__.py`'s `__all__`) -- never reimplement logic inline
  that the programmatic surface also needs, so the two access modes can't
  drift apart.

---

## 2. Decoupled Frontend Conventions (`frontend/**`)

- **Svelte 5 Runes**: Use modern runes (`$state`, `$derived`, `$props`, `$effect`). Avoid legacy Svelte 3/4 stores or `export let`.
- **TypeScript**: Always use `<script lang="ts">`. Keep contracts synchronized with `app/modules/contracts.py` via `frontend/src/lib/types.ts`. Run `npm run generate:api-types` (backend dev server must be running) to regenerate `frontend/src/lib/generated/openapi-types.ts` (gitignored, local-only) straight from `/api/openapi.json` and diff it against `types.ts` when checking for drift.
- **API Client**: Make all HTTP calls through `frontend/src/lib/api.ts`. Never write ad hoc `fetch()` calls in individual components.
- **Real-Time Updates via SSE**: Connect to `/api/events/{project_id}` using `subscribeToEvents()` from `src/lib/sse.ts` to stream analysis progress without polling.
- **Styling**: Use Tailwind CSS utility classes following the design tokens in `DESIGN.md`.
- **3D Viewport**: Reuse or extend `src/lib/components/IfcViewer.svelte` for IFC 3D visualization and BCF camera viewpoints.
- **New Feature Development**: All new UI views (projects, dashboards, analysis, rule editors) MUST be added to `frontend/src/routes/` or `frontend/src/lib/components/`.

---

## 3. Database & Engine Access

- **Persistence Access**: Exclusively via `PersistenceService.get_table(...)` in `app/services/persistence.py`.
- **Rule Management**: Exclusively via `RuleService` in `app/services/rules_service.py`.
- **Dynamic Rule Catalogs**: Lookups and scoring models for corrosion engines are loaded via `app/services/corrosion_rule_catalog.py`.
- **Zero Hardcoded Cutoffs**: All scoring weights, risk band thresholds, material tables, and velocity intervals must be read dynamically from the database.
- **Live Catalog Reloading**: Call `reload_all_catalogs()` at the start of analysis runs so that database rule edits take effect immediately without server restarts.
- **File Uploads**: Save through `ObjectStorage.save_upload(...)` in `app/services/object_storage.py` using Supabase Storage. Local disk under `data/cache/supabase-storage` is a disposable cache only.

---

## 4. Timestamps & Timezones

- Use Python's standard UTC timezone: `datetime.now(timezone.utc).isoformat()` or `datetime.now(UTC).isoformat()`.
- Never use deprecated `datetime.utcnow()`.
- Store as ISO 8601 string timestamp columns in DB records.

---

## 5. Naming Conventions

| Layer | Pattern | Example |
|---|---|---|
| API router module | `app/api/{domain}.py` | `app/api/projects.py` |
| Service module | `app/services/{domain}_service.py` | `projects_service.py` |
| Svelte page component | `frontend/src/routes/{Domain}View.svelte` | `ProjectsView.svelte` |
| Svelte reusable component | `frontend/src/lib/components/{Name}.svelte` | `IfcViewer.svelte` |
| Internal Python helper | `_{name}` | `_build_row` |
