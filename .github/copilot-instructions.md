# Copilot instructions

## Project guidance

Use the repo guidance in [AGENTS.md](../AGENTS.md), [CLAUDE.md](../CLAUDE.md), and [.github/instructions/project-specific.instructions.md](./instructions/project-specific.instructions.md) as the primary sources for architecture and coding conventions.

BIM-Guard is transitioning from a legacy FastHTML monolith to a **decoupled architecture**:
1. **Primary Backend API**: FastAPI mounted at `/api` (`app/api/`) with strict typed Pydantic data contracts (`app/modules/contracts.py`) and real-time Server-Sent Events (SSE) streaming (`/api/events/{project_id}`).
2. **Primary Frontend Client**: Decoupled Single-Page Application (`frontend/`) built with Svelte 5, Vite, TypeScript, and Tailwind CSS.
3. **Legacy UI**: FastHTML + MonsterUI (`app/routes/`, `app/components/`) is deprecated and kept only for backwards compatibility. **All new user-facing views and features must be built in Svelte 5 (`frontend/`)**.
4. **Compute Kernels**: Pure Python architectural compliance engines (`app/engines/`, `app/modules/`) driven dynamically by database-stored rules.

When making code changes:
- Target new endpoints to `app/api/` using Pydantic schemas from `app/modules/contracts.py`.
- Target new UI components to `frontend/src/` using Svelte 5 runes (`$state`, `$derived`, `$props`) and mirror Pydantic schemas in `frontend/src/lib/types.ts`.
- Stream real-time pipeline progress using Server-Sent Events (`/api/events/{project_id}`) via `src/lib/sse.ts`.
- Keep rules and engine thresholds database-driven via `RuleService` — never hardcode engineering constants in Python engines.
- Use PEP 257 docstrings for new public Python APIs.
- Test execution: Use targeted workflows (`uv run python scripts/test_relevant.py`, `uv run pytest --picked`, `uv run pytest -m <domain>`, `uv run pytest --lf`) to run only tests relevant to current changes; use `uv run pytest tests/ -m 'not slow'` for routine general verification (skip slow tests by default).
- Universal Data Table UX Standards: All data tables (Projects, Documents, Reports & BCF, Rules Catalog, Extracted Rules, Findings/Issues, Revit Sync) must support multiple selection, full CRUD, bulk actions/edits (`BulkActionBar`), pagination (`TablePagination`), column sorting, search/filtering, and rich zero-states.
- Reusable Component Architecture: Always reuse established UI components from `frontend/src/lib/components/` (`PageHeader`, `Modal`, `SortHeader`, `TableCheckbox`, `TablePagination`, `BulkActionBar`, `EmptyState`, `LoadingState`, `SeverityBadge`, `IsoGovernanceBadges`).
- Production Serving at https://bim-guard.xyz: Serve the full stack using `docker compose --profile tunnel up -d --build` (orchestrating `bim-guard` on `:8000`, `neo4j` on `:7474`/`:7687`, `docling-serve` on `:5001`, `opencde` on `:8081`, and `cloudflared` for outbound Zero Trust domain tunneling).

## Mermaid Diagrams

When the user asks to create, edit, or visualize a diagram, follow the instructions in [.github/instructions/mermaid.instructions.md](./instructions/mermaid.instructions.md).
