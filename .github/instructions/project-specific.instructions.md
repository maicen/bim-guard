---
description: "Use when writing, reviewing, or modifying any code in this project. Covers FastHTML + MonsterUI UI patterns, route conventions, database operations, and BIM module structure."
applyTo: "app/**"
---

# BIM Guard — Project-Specific Coding Guidelines

## Project Overview

**BIM Guard** is a BIM compliance application built with FastHTML (Python) and MonsterUI. It lets users upload IFC models, define compliance rules from documents, and generate reports.

**Tech stack:** FastHTML · MonsterUI · FastLite (SQLite) · IfcOpenShell · HTMX

---

## Getting Started

```bash
# Install dependencies
uv sync

# Run the app
uv run uvicorn main:app --reload

```

## UI / Frontend Rules (highest priority)

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
            A(Button("Cancel", cls=ButtonT.ghost), href="/back"),
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
from pathlib import Path
import uuid

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@rt("/api/upload", methods=["POST"])
async def upload_handler(document: UploadFile):
    contents = await document.read()           # bytes
    original_name = document.filename or "upload.bin"
    safe_base = Path(original_name).name       # strips path traversal segments
    safe_name = f"{uuid.uuid4().hex}_{safe_base}"
    save_path = UPLOAD_DIR / safe_name
    save_path.write_bytes(contents)            # save to disk
    # Return HTMX fragment
    return Div(P(f"Uploaded: {safe_name}"), cls="...")
```

- Always use `async def` for upload handlers
- Save files under a dedicated directory (e.g. `data/uploads/`), never in `static/`
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

## Database (FastLite)

Use `fastlite` exclusively — never SQLAlchemy, Pydantic models, or other ORMs.

```python
from pathlib import Path
from fastlite import database

# DB_PATH is defined at the top of each route file that needs DB access:
DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "bimguard.sqlite"

_db = database(str(DB_PATH))
_table = _db["table_name"]
_table.create({
    "id": int,
    "name": str,
    "status": str,
}, pk="id", if_not_exists=True)

# CRUD
_table.insert({"name": "...", "status": "Draft"})
_table.get(id)                                         # returns None if missing
_table.update(updates={"name": "new", ...}, pk_values=id)  # use keyword args
_table.delete(id)
list(_table.rows)  # all rows
```

Verified in this project environment: `Table.update` supports `updates=` keyword argument.

Timestamps are ISO 8601 strings:
```python
from datetime import datetime, timezone
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
```

**Never use `datetime.utcnow()`** — deprecated in Python 3.12+. Always use `datetime.now(timezone.utc)`.

Note: route-level DB initialization is currently acceptable for this codebase, but prefer a shared `app/db.py` accessor for new work to avoid duplicated path/bootstrap logic.

---

## Module Architecture (BIM Workflow)

The 5-module pipeline processes BIM compliance:

| Module | File | Responsibility |
|---|---|---|
| 1 | `module1_doc_reader.py` | Parse compliance documents (PDF → text) |
| 2 | `module2_ifc_read.py` | Load and extract IFC model data |
| 3 | `module3_rule_builder.py` | Build SHACL/regex rules from documents |
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

There are no automated tests currently. Use manual verification via the running Uvicorn server (`uv run uvicorn main:app --reload`). When writing new functionality:

- Verify happy path in the browser
- Verify empty-state rendering (no DB records)
- Verify form validation (missing required fields)

Automated tests are not currently required. Use manual browser verification by default unless test work is explicitly requested.

---

## General Python Conventions

- **No class-based views** — use plain functions everywhere
- **No type annotation required** on return types, but annotate parameters
- Use Python 3.10+ union syntax: `dict | None` not `Optional[dict]`
- Database path via `pathlib.Path` — never hardcode strings
- Functional style preferred; no unnecessary abstractions

---

## Forbidden Patterns

Never use any of the following:

| Forbidden | Use instead |
|---|---|
| `datetime.utcnow()` | `datetime.now(timezone.utc)` |
| `from sqlalchemy import ...` | `from fastlite import database` |
| `from pydantic import BaseModel` | plain `dict` or FastLite schema |
| `from flask import ...` / `@app.route(...)` | FastHTML `@rt(...)` inside `setup_routes(rt)` |
| `class MyView(View):` | plain `def` functions |
| `from typing import Optional` | `X | None` (Python 3.10+ union syntax) |
| Returning raw HTML strings | Return FastHTML component trees |
| `raise HTTPException(...)` | Return component with `Alert(cls=AlertT.danger)` |
| Registering routes globally outside `setup_routes` | Always use `setup_routes(rt)` pattern |
| Hardcoding `"data/bimguard.sqlite"` string | Use `Path("data") / "bimguard.sqlite"` |