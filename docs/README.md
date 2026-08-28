# Documentation Map

This index organizes repository markdown files by purpose and maintenance status.

## Authoritative Documentation

These files should be treated as current sources of truth.

- ../README.md
- ../AGENTS.md
- ../CLAUDE.md
- ../DESIGN.md
- ../.github/instructions/project-specific.instructions.md
- architecture.md
- piping_schema_spec.md

## Operational Guides

- ../frontend/README.md
- NotebookLM/README.md
- NotebookLM/setup_guide.md
- NotebookLM/sources.md
- NotebookLM/master_prompt.md
- MonsterUI/llms.txt.md
- RESOURCES.md

## Project Tracking and Historical Updates

These files are useful context but are time-bound snapshots.

- enhancements-plan-20260407.md
- revised-issues-20260408.md
- update-2026-04-09.md

## Archived or Legacy Context

These files are intentionally retained for historical reference and may not reflect the current FastHTML architecture.

- INTEGRATION_GUIDE.md
- docs/archive/2026-04-migration-from-nextjs.md

## Module-Level Documentation

- ../app/modules/README.md
- ../app/modules/tests/TEST_README.md

## Supporting Documents

- ../.Jules/palette.md

## Generated or Internal Markdown Files

These are not project docs and should not be edited as source documentation.

- ../data/uploads/fbd19cfd9d764dc0a1b4537a75ba45b1_docling.md

## Documentation Maintenance Rules

- Keep dependency instructions aligned with uv and pyproject.toml.
- Prefer forward slashes in paths for cross-platform readability.
- Mark stale process docs as archived instead of silently leaving them active.
- Keep architecture claims consistent with the current repo structure.
- Update this index when adding, moving, or archiving markdown files.
