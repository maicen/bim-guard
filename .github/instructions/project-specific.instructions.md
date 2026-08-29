---
description: "Authoritative instructions for BIM-Guard: covers FastAPI backend API, Svelte 5 decoupled frontend, database-driven rules, and legacy FastHTML maintenance."
applyTo: "**"
---

# BIM Guard — Project-Specific Coding Guidelines


## Instructions Files Map

| File | Who reads it | What it defines |
| --- | --- | --- |
| README.md | Humans | What the project is |
| AGENTS.md, CLAUDE.md, .github/instructions/project-specific.instructions.md | Coding agents | How to build the project |
| DESIGN.md | Design agents | How the project should look and feel |


## Project Overview & Transition Architecture

**BIM Guard** is an OpenBIM compliance platform transitioning from a legacy FastHTML monolith to a modern decoupled architecture:
1. **Primary Backend API**: A **FastAPI API Gateway** (`app/api/`) delivering strict Pydantic REST contracts (`app/modules/contracts.py`), file streaming, and real-time Server-Sent Events (SSE) tracking (`/api/events/{project_id}`).
2. **Primary Frontend Client**: A **Decoupled SPA Frontend** (`frontend/`) built with **Svelte 5**, Vite, TypeScript, and Tailwind CSS. **All new UI features and views must be built here**.
3. **Legacy Monolith (Deprecated / Maintenance Only)**: FastHTML + MonsterUI (`app/routes/`, `app/components/`) mounted alongside the API gateway at `/` during migration. Do not build new features here; only perform critical maintenance fixes.
4. **Compute engines & pipelines**: Physics engines and compliance evaluators (`app/engines/`, `app/modules/`) operating framework-agnostic, driven dynamically by database-stored rules.

**Tech stack:** FastAPI · Svelte 5 (Vite + TypeScript) · Tailwind CSS · Supabase (Postgres & Storage) · IfcOpenShell · Server-Sent Events

---

## Getting Started

```bash
# Install backend dependencies
uv sync

# Run backend with auto-reload (available at http://127.0.0.1:8000, OpenAPI docs at /api/docs)
uv run uvicorn main:app --reload

# Run frontend in development (available at http://localhost:5173 with proxy to /api)
cd frontend && npm install && npm run dev

# Or launch both dev servers concurrently (cross-platform)
./run_server.sh         # macOS/Linux (or ./run_server.bat)
run_server.bat          # Windows
```

---

## API & Backend Rules (`app/api/**`)

1. **Always use Pydantic schemas**: Every route in `app/api/` must accept and return strict Pydantic models defined in `app/modules/contracts.py`. Never return raw HTML or unvalidated dictionaries.
2. **Dependency Injection**: Use FastAPI `Depends(...)` with provider functions in `app/api/dependencies.py` to access services.
3. **HTTP Status & Errors**: Raise standard `fastapi.HTTPException` with appropriate status codes (400 for bad parameters, 404 for missing entities, 409 for pipeline conflicts, 500 for unhandled exceptions).
4. **Real-Time Streaming**: Use Server-Sent Events via `app/api/events.py` and `pipeline_tracker.py` for tracking multi-stage analysis workflows.
5. **Contract Parity**: When modifying API schemas, synchronize the corresponding TypeScript interfaces in `frontend/src/lib/types.ts`.

---

## Decoupled Frontend Rules (`frontend/**`)

1. **Svelte 5 Runes**: Use Svelte 5 modern syntax (`$state`, `$derived`, `$props`, `$effect`). Avoid legacy Svelte 3/4 stores or `export let`.
2. **TypeScript & Type Safety**: Always use `<script lang="ts">`. All API responses and model data must be typed via `src/lib/types.ts`.
3. **API Client Integration**: Make all backend calls through `src/lib/api.ts`. Never write ad hoc `fetch()` calls in individual components.
4. **Real-Time Updates via SSE**: Connect to `/api/events/{project_id}` using `subscribeToEvents()` from `src/lib/sse.ts` to stream analysis progress without polling.
5. **Styling**: Use Tailwind CSS utility classes following the design tokens in `DESIGN.md`.
6. **3D Viewport**: Reuse or extend `src/lib/components/IfcViewer.svelte` for IFC 3D visualization and BCF camera viewpoints.
7. **New Features**: All new UI views (projects, dashboards, analysis, rule editors) MUST be added to `frontend/src/routes/` or `frontend/src/lib/components/`.

---

## Legacy FastHTML UI Rules (Deprecated / Maintenance Only)

### 1. Always use MonsterUI components — never raw HTML tags

Prefer MonsterUI components over equivalent raw HTML. Examples:

| Instead of... | Use... |
|---|---|
| `Div(cls="card")` | `Card(...)` |
| `Button("Click")` | `Button("Click", cls=ButtonT.primary)` |
| `Div(cls="grid grid-cols-3")` | `Grid(..., cols=3)` |
| `H1("Title")` alone | `H1("Title")` inside a `Card` or layout container |
| `Select(Option(...))` | `Select(Option(...), name="field")` with MonsterUI `Label` |

Import from `monsterui.all import *` to get all components.

Note: this import exposes names like `Input`, `Form`, and `Link`. Use them intentionally and avoid redefining variables/functions with the same names in the same scope.

Available layout helpers from MonsterUI: `DivFullySpaced`, `DivVStacked`, `DivLAligned`, `Container`.

### 1.1 Prefer reusable components over ad hoc UI

When a UI pattern appears more than once, or is likely to be reused, extract it into a shared component instead of duplicating route-level markup.

- Prefer adding or extending reusable helpers in `app/components/ui.py` for buttons, action controls, repeated form elements, and small presentational patterns
- Reuse existing shared components before creating new inline `Button(...)`, `A(...)`, `Form(...)`, or icon combinations in route files
- Keep route files focused on composition and page structure; move repeated UI implementation details into `app/components/`
- If a component is only slightly different from an existing one, extend the existing component with parameters rather than creating a parallel copy

**Existing action button components** (from `app/components/ui.py`) — always prefer these over ad hoc icon buttons:

```python
from app.components.ui import ViewAction, EditAction, CreateAction, BackAction

ViewAction(href=f"/projects/{id}")       # eye icon link
EditAction(href=f"/projects/{id}/edit")  # pencil icon link
CreateAction(href="/projects/new")       # plus icon link
BackAction(href="/projects")             # arrow-left icon link
```

### 2. Always wrap pages in DashboardLayout with Title

Every route that renders a full page **must** return a tuple:

```python
return Title("Page Title — BIM Guard"), DashboardLayout(
    Container(
        ...,
        cls="space-y-4"
    )
)
```

- `Title(...)` sets the browser tab title
- `DashboardLayout` (from `app.components.layout`) provides sidebar + header
- `Container` from MonsterUI provides responsive centering

### 3. Card-based content sectioning

Wrap content sections in Cards:

```python
Card(
    CardHeader(CardTitle("Section Title")),
    CardContent(
        P("Description text"),
        Button("Action", cls=ButtonT.primary)
    )
)
```

### 4. Responsive grids

Use `Grid` with responsive cols props:

```python
Grid(
    Card(...), Card(...), Card(...),
    cols=1, cols_md=2, cols_lg=3
)
```

Verified in this project environment: `Grid` supports `cols`, `cols_sm`, `cols_md`, `cols_lg`, and `cols_xl`.

### 5. Status badges / alerts

Use `Alert` for page-level feedback messages:

```python
Alert("Project saved successfully.", cls=AlertT.success)  # success
Alert("Something went wrong.", cls=AlertT.danger)          # error
```

Render row-level status values with `Label` and a matching style:

```python
_STATUS_CLS = {
    "Draft":    "bg-muted text-muted-foreground",
    "Active":   "bg-green-100 text-green-800",
    "Archived": "bg-yellow-100 text-yellow-800",
}

Label(row["status"], cls=f"text-xs px-2 py-0.5 rounded {_STATUS_CLS.get(row['status'], '')}")
```

### 6. Canonical form construction

Use `DivVStacked` + `FormLabel` + `Input`/`TextArea`/`Select` for all form fields. Wrap the whole form in a `Card`:

```python
Card(
    Form(
        DivVStacked(
            FormLabel("Field Label", fr="field_id"),
            Input(id="field_id", name="field_name", placeholder="...", required=True),
            cls="space-y-1",
        ),
        DivVStacked(
            FormLabel("Status", fr="status"),
            Select(
                Option("Draft",    value="Draft",    selected=project.get("status") == "Draft"),
                Option("Active",   value="Active",   selected=project.get("status") == "Active"),
                Option("Archived", value="Archived", selected=project.get("status") == "Archived"),
                id="status", name="status",
            ),
            cls="space-y-1",
        ),
        DivLAligned(
            Button("Save", cls=ButtonT.primary),
            A(Button("Cancel", cls=ButtonT.secondary), href="/back"),
            cls="gap-2",
        ),
        method="post",
        action="/endpoint",
        cls="space-y-4",
    ),
    header=Div(H2("Form Title"), Subtitle("Supporting text.")),
)
```

- Always use `FormLabel` (not raw `Label`) so the `fr=` attr wires to the input `id`
- Always include `name=` on every form control — this is how FastHTML maps to route params
- Never omit `method="post"` and `action="..."` on `Form`

---

## HTMX Patterns

### When to use HTMX vs. full-page redirect

| Situation | Pattern |
|---|---|
| CRUD form submit (create/update/delete) | Standard form POST → `RedirectResponse(303)` — no HTMX |
| Long-running async action (AI extraction, IFC scan) | HTMX: `hx_post` + `hx_target` + `hx_indicator` |
| Partial UI refresh (table reload, status update) | HTMX: `hx_get` + `hx_target` + `hx_swap` |

### HTMX partial response pattern

When a route is called via HTMX it must return **a fragment only** — never `Title(...)` or `DashboardLayout`:

```python
# Route handler for an HTMX endpoint
@rt("/api/rules/extract", methods=["POST"])
async def api_rules_extract(document: UploadFile):
    # ... process ...
    # Return fragment only — no DashboardLayout, no Title
    return Div(
        *[Card(P(rule["desc"])) for rule in rules],
        cls="space-y-3",
    )
```

### HTMX form attributes

```python
Form(
    Input(type="file", name="document", accept=".pdf"),
    Button("Extract", type="submit"),
    # Loading spinner (hidden until request fires)
    Div(
        Span("Processing...", cls="text-sm text-muted-foreground"),
        id="my-spinner",
        cls="htmx-indicator",
        style="display:none",
    ),
    Style(".htmx-indicator.htmx-request { display: flex !important; }"),
    hx_post="/api/rules/extract",
    hx_target="#results-container",  # CSS selector of element to update
    hx_indicator="#my-spinner",
    enctype="multipart/form-data",    # required for file uploads
)
```

- `hx_swap` defaults to `innerHTML`; use `hx_swap="outerHTML"` to replace the target element itself
- Always wire a `hx_indicator` for any endpoint that may take >200ms
- Use the compound selector `.htmx-indicator.htmx-request` for indicators targeted via `hx_indicator="#id"`

---

## File Upload Handling

File upload routes must be `async` and accept `UploadFile` from `fasthtml.common`:

```python
from fasthtml.common import UploadFile

@rt("/api/upload", methods=["POST"])
async def upload_handler(document: UploadFile):
    contents = await document.read()           # bytes
    storage_ref = ObjectStorage().save_upload(
        document.filename or "upload.bin", contents, "uploads"
    )
    # Store storage_ref in Supabase and return an HTMX fragment.
    return Div(P(f"Uploaded: {storage_ref}"), cls="...")
```

- Always use `async def` for upload handlers
- Save files through `ObjectStorage.save_upload(...)`; local disk is only a cache for downloaded Supabase objects
- The form must include `enctype="multipart/form-data"` for uploads to work
- Never trust client filenames directly; normalize with `Path(name).name` and add a server-generated prefix

---

## Route Conventions

### setup_routes pattern

Every route file must expose a `setup_routes(rt)` function — never register routes globally:

```python
def setup_routes(rt):
    @rt("/projects")
    def projects_page():
        return Title("Projects"), DashboardLayout(...)

    @rt("/projects", methods=["POST"])
    def projects_create(name: str, description: str = "", status: str = "Draft"):
        # process...
        return RedirectResponse("/projects", status_code=303)
```

Register in `app/main.py`:
```python
from app.routes import projects
projects.setup_routes(rt)
```

### POST → Redirect pattern

After any form submission that mutates data, always redirect with `status_code=303`:

```python
return RedirectResponse("/destination", status_code=303)
```

### Private helpers

Prefix internal/helper functions with `_`:

```python
def _project_form(project=None): ...
def _projects_table_rows(): ...
def _now_iso() -> str: ...
```

### Error handling

- **Record not found**: call `_table.get(id)` — it returns `None` if missing. Return a 404 response or redirect:

```python
project = _projects.get(project_id)
if project is None:
    return Title("Not Found"), DashboardLayout(
        Container(Alert("Project not found.", cls=AlertT.danger))
    )
```

- **Validation errors**: return the form again with an `Alert` at the top — do **not** redirect:

```python
if not name.strip():
    return Title("Edit Project"), DashboardLayout(
        Container(
            Alert("Project name is required.", cls=AlertT.danger),
            _project_form(...),
        )
    )
```

- **Never** use Python `raise HTTPException` — return FastHTML components directly

---

## Database (Supabase)

Use the shared Supabase persistence service and table adapters exclusively — never a local database, FastLite, SQLAlchemy, Pydantic models, or other ORMs.

```python
from app.services.persistence import PersistenceService

_table = PersistenceService.get_table(
    "table_name",
    {"id": int, "name": str, "status": str},
    pk="id",
)

# CRUD
_table.insert({"name": "...", "status": "Draft"})
_table.get(id)                                         # returns None if missing
_table.update(updates={"name": "new", ...}, pk_values=id)  # use keyword args
_table.delete(id)
list(_table.rows)  # all rows
```

The Supabase table adapter supports the same `updates=` keyword argument for updates.

Timestamps are ISO 8601 strings:
```python
from datetime import datetime, timezone
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
```

**Never use `datetime.utcnow()`** — deprecated in Python 3.12+. Always use `datetime.now(timezone.utc)`.

**Prefer the shared DB accessor for all work.** Route-level database initialization must not be duplicated in route or service files:

```python
# app/db.py (create if it doesn't exist)
from app.services.persistence import PersistenceService

db = PersistenceService.get_db
```

Then import in service files:
```python
from app.db import db
_supabase = db()
_projects = PersistenceService.get_table("projects", PROJECT_SCHEMA)
```

---

## IFC Viewer (Frontend)

The viewer is at `app/routes/viewer.py` + `static/js/ifc-viewer.js`. It renders inside `#viewer-container` using a pure CDN ESM setup — no bundler.

### Working CDN stack (do not change without good reason)

```javascript
import * as THREE from 'https://esm.sh/three@0.160.0';
import { OrbitControls } from 'https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls';
import { IFCLoader } from 'https://esm.sh/web-ifc-three@0.0.126?deps=three@0.160.0,web-ifc@0.0.68';
```

WASM path inside `initViewer`:
```javascript
await ifcLoader.ifcManager.setWasmPath('https://unpkg.com/web-ifc@0.0.68/');
```

**Why esm.sh:** `web-ifc-three` has many internal bare specifiers (`"three"`, `"web-ifc"`, `"three/examples/..."`) that browsers cannot resolve directly. esm.sh rewrites all of them to absolute URLs at their end. The `?deps=` parameter pins exact versions so all packages share the same `three` and `web-ifc` instances — preventing duplicate module errors.

**Do not use:** jsDelivr `+esm`, unpkg direct imports, or import maps for this package — all were tried and failed due to bare specifier rewriting or version mismatches across the dependency tree.

### Viewer API contract

`ifc-viewer.js` exports one function:

```javascript
export async function initViewer(containerId: string): Promise<{
    scene: THREE.Scene,
    camera: THREE.PerspectiveCamera,
    renderer: THREE.WebGLRenderer,
    controls: OrbitControls,
    loadIfc: (urlOrFile: string | File) => Promise<void>
}>
```

`loadIfc` accepts either a URL string (preferred — avoids a round-trip) or a `File` object. `viewer.py` passes the URL directly: `await viewerAPI.loadIfc(ifcUrl)`.

### IFC file serving

`/projects/{project_id}/ifc` in `app/routes/projects.py` serves the raw IFC bytes via `FileResponse`. The viewer fetches from this endpoint.

---

## Module Architecture (BIM Workflow)

The 5-module pipeline processes BIM compliance:

| Module | File | Responsibility |
|---|---|---|
| 1 | `module1_doc_parser/` | Parse compliance documents (PDF → text) |
| 2 | `module2_ifc_read.py` | Load and extract IFC model data |
| 3 | `module3_rule_builder/` | Build SHACL/regex rules from documents |
| 4 | `module4_comparator.py` | Validate IFC data against rules |
| 5 | `module5_reporter.py` | Generate BCF/CSV compliance reports |

`orchestrator.py` wires the modules together via `BIMGuard_App`.

### Module interfaces (current state)

All modules are currently scaffold stubs — method bodies are `pass`. Before implementing a module method, define its signature explicitly:

```python
# Example contract to follow when implementing:
def load_ifc_file(self, file_path: Path) -> bool: ...
def get_all_elements(self) -> list[dict]: ...
def extract_properties(self, element_id: int) -> dict: ...
```

When route handlers call modules, always go through `orchestrator.py` — never import module classes directly in route files.

```python
from app.modules.orchestrator import BIMGuard_App

workflow = BIMGuard_App()
result = workflow.orchestrate_workflow()
```

---

## Testing Conventions

Automated testing is active and required for all changes:

### Backend Testing
- **Test execution**: `uv run pytest tests/`
- **Linting**: `uv run ruff check .`
- **API Tests**: Validate endpoint request/response payloads against Pydantic models (e.g. `tests/test_api_*.py`).
- **Engine Tests**: Validate that all physics and compliance rules pull dynamically from the database without hardcoded cutoffs (e.g. `tests/test_db_rules_workflow.py`, `tests/test_phase_6c_corrosion_ui.py`).

### Frontend Testing & Verification
- **Build validation**: `cd frontend && npm run build` (verifies TypeScript types and Vite bundle)
- **Local testing**: `cd frontend && npm run dev` (runs at http://localhost:5173 with proxy to backend `/api`)

---

## General Python & TypeScript Conventions

- Python 3.12: Use `X | None` union syntax (avoid `Optional[X]`).
- Strict Pydantic models for API request/response schemas in `app/modules/contracts.py`.
- Strict TypeScript types mirroring Pydantic schemas in `frontend/src/lib/types.ts`.
- Database access exclusively via `PersistenceService` (`app/services/persistence.py`) and `RuleService` (`app/services/rules_service.py`).
- Object storage exclusively via `ObjectStorage` (`app/services/object_storage.py`).

---

## Forbidden Patterns

Never use any of the following:

| Forbidden | Reason / Use instead |
|---|---|
| Creating new UI pages in FastHTML (`app/routes/`) | **FastHTML is deprecated**. Build all new views and features in `frontend/` using Svelte 5. |
| Hardcoding engineering cutoffs or scoring weights | **Rules must be DB-driven**. Read from database via `RuleService` and `corrosion_rule_catalog.py`. |
| Returning raw unvalidated dicts from `app/api/**` | **API contract violation**. Return typed Pydantic models from `app/modules/contracts.py`. |
| Ad hoc `fetch()` calls in Svelte components | Call backend methods via `frontend/src/lib/api.ts`. |
| Polling backend for analysis progress | Use Server-Sent Events via `subscribeToEvents()` in `frontend/src/lib/sse.ts`. |
| `datetime.utcnow()` | Use `datetime.now(timezone.utc)` or `datetime.now(UTC)`. |
| Direct SQL/SQLAlchemy queries in routes | Use `PersistenceService.get_table(...)` and service methods. |
| Creating local databases or hardcoding paths | Use Supabase via `PersistenceService`. |
| `from typing import Optional` | Use Python 3.10+ union syntax (`X | None`). |