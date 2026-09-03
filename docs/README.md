# Documentation Map

This index organizes repository markdown files by purpose and maintenance status.

## Authoritative Documentation

These files should be treated as current sources of truth.

- `../README.md`
- `../AGENTS.md`
- `../CLAUDE.md`
- `../DESIGN.md`
- `../.github/instructions/project-specific.instructions.md`
- `architecture.md`
- `piping_schema_spec.md`
- `BIMGUARD_DATA_ARCHITECTURE.md`
- `CONVENTIONS.md`
- `HERMES_CONTEXT.md`
- `PHASE_6_DATA_CONTRACTS.md`

## Operational Guides

- `../frontend/README.md`
- `NotebookLM/README.md`
- `NotebookLM/setup_guide.md`
- `NotebookLM/sources.md`
- `NotebookLM/master_prompt.md`
- `MonsterUI/llms.txt.md`
- `RESOURCES.md`

## Validation & Research (`validation/`)

- Contains methodology documents, dataset notes, and standard research matrices.
- `logs/`: Output traces and raw text logs from full evaluation runs.
- `data/`: JSON summaries and configs from validation sweeps.
- **Dedicated Evaluation Companion Repository**: [maicen/bim-guard-evaluation](https://github.com/maicen/bim-guard-evaluation) — All empirical research analysis (confusion matrices, 38-model validation sweeps, accuracy scoring, and NLP annotation capabilities) are conducted and maintained in this dedicated repo.

## Project Tracking & Historical Updates (`planning/`)

These files are useful context but are time-bound snapshots (e.g., enhancement plans, session summaries).
- `planning/BIMGuard-enhancement-plan-20260821.md`
- `planning/session-summary-2026-06-30.md`
- `planning/improvements-20260420.md`
- `planning/enhancements-plan-20260407.md`
- `planning/update-2026-04-09.md`
- `planning/integration_plan_mm_xm.md`

## Theses & Submissions (`thesis/` & `submissions/`)

- `thesis/`: The MAICEN M10 Final Thesis documents.
- `submissions/`: Official revised submission docs.

## Archived or Legacy Context (`archive/`)

These files are intentionally retained for historical reference.
- `archive/index.html` (Legacy frontend prototype)
- `INTEGRATION_GUIDE.md`

## Documentation Maintenance Rules

- Keep dependency instructions aligned with uv and pyproject.toml.
- Prefer forward slashes in paths for cross-platform readability.
- Mark stale process docs as archived instead of silently leaving them active.
- Keep architecture claims consistent with the current repo structure.
- Update this index when adding, moving, or archiving markdown files.
