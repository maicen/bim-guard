# Copilot instructions

## Project guidance

Use the repo guidance in [AGENTS.md](../AGENTS.md), [CLAUDE.md](../CLAUDE.md), and [.github/instructions/project-specific.instructions.md](./instructions/project-specific.instructions.md) as the primary sources for architecture and coding conventions.

BIM-Guard is transitioning from a legacy FastHTML monolith to a **decoupled architecture**:
1. **Primary Backend API**: FastAPI mounted at `/api` (`app/api/`) with strict typed Pydantic data contracts (`app/modules/contracts.py`) and real-time Server-Sent Events (SSE) streaming (`/api/events/{project_id}`).
2. **Primary Frontend Client**: Decoupled Single-Page Application (`frontend/`) built with Svelte 5, Vite, TypeScript, and Tailwind CSS.
3. **Legacy UI**: FastHTML + MonsterUI (`app/routes/`, `app/components/`) is deprecated and kept only for backwards compatibility. **All new user-facing views and features must be built in Svelte 5 (`frontend/`)**.
4. **Compute Kernels**: Pure Python compliance and corrosion engines (`app/engines/`, `app/modules/`) driven dynamically by database-stored rules.

When making code changes:
- Target new endpoints to `app/api/` using Pydantic schemas from `app/modules/contracts.py`.
- Target new UI components to `frontend/src/` using Svelte 5 runes (`$state`, `$derived`, `$props`) and mirror Pydantic schemas in `frontend/src/lib/types.ts`.
- Stream real-time pipeline progress using Server-Sent Events (`/api/events/{project_id}`) via `src/lib/sse.ts`.
- Keep rules and engine thresholds database-driven via `RuleService` and `corrosion_rule_catalog.py` — never hardcode engineering constants in Python engines.
- Use PEP 257 docstrings for new public Python APIs.

## Mermaid Diagrams

When the user asks to create, edit, or visualize a diagram, follow the instructions in [.github/instructions/mermaid.instructions.md](./instructions/mermaid.instructions.md).
