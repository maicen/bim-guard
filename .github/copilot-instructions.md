# Copilot instructions

## Project guidance

Use the repo guidance in [AGENTS.md](../AGENTS.md) and [.github/instructions/project-specific.instructions.md](./instructions/project-specific.instructions.md) as the primary sources for architecture and coding conventions.

This project is a single FastHTML + MonsterUI app. Backend routes and UI live together in Python under `app/`; the app is started with `uv run uvicorn main:app --reload` and dependencies are managed via `uv` and `pyproject.toml`.

When making code changes:
- prefer existing components and route/service boundaries already used in `app/components/`, `app/routes/`, and `app/services/`
- keep documentation linked rather than duplicated
- use PEP 257 docstrings for new public Python APIs

## Mermaid Diagrams

When the user asks to create, edit, or visualize a diagram, follow the instructions in [.github/instructions/mermaid.instructions.md](./instructions/mermaid.instructions.md).
