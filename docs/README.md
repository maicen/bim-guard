# Documentation Map

This index organizes repository markdown files (and the non-code assets sitting
alongside them) by purpose and maintenance status.

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
- `ifc-property-mapping.md`

## Client-Facing Q&A (`client-qa/`)

Twenty client-facing Q&A documents written against the shipped implementation
(not a roadmap) — see `client-qa/README.md` for the full index, grouped by
domain (Piping, Seismic, Architecture, Workflow).

## Operational Guides

- `../frontend/README.md`
- `NotebookLM/README.md`
- `NotebookLM/setup_guide.md`
- `NotebookLM/sources.md`
- `NotebookLM/master_prompt.md`
- `MonsterUI/llms.txt.md` — reference docs for the MonsterUI component library used by the retired FastHTML frontend; kept for archive context only, not the current Svelte 5 SPA
- `RESOURCES.md`
- `expert_review_process.md`
- `scraped_standards/README.md` — retrieved standards, regenerable and excluded from version control

## Validation & Research (`validation/`)

- Contains methodology documents, dataset notes, and standard research matrices.
- `data/`: JSON/CSV summaries and configs from validation sweeps.
- **Dedicated Evaluation Companion Repository**: [maicen/bim-guard-evaluation](https://github.com/maicen/bim-guard-evaluation) — all empirical research analysis (confusion matrices, 38-model validation sweeps, accuracy scoring, and NLP annotation capabilities) is conducted and maintained in this dedicated repo, not here.

## Defect Reports (`defects/`)

Point-in-time defect write-ups with reproduction scripts, kept as historical
record of investigated bugs (e.g. `defect_report_anode_convention.md`,
`defect_report_map_ordering.md`).

## Experimental (`experimental/`)

Exploratory findings and prototypes not part of the shipped product (e.g.
Navisworks ISO 19650 findings, an early static frontend prototype).

## Benchmarks (`benchmarks/`)

Performance benchmark results and summaries for the Blue Halo (seismic)
pipeline.

## Sample Exports (`bcf_exports/`)

Sample BCF export output kept for reference — see `bcf_exports/README.md`.

## Project Tracking & Historical Updates (`planning/`)

These files are useful context but are time-bound snapshots (e.g., enhancement
plans, session summaries).
- `planning/BIMGuard-enhancement-plan-20260821.md`
- `planning/session-summary-2026-06-30.md`
- `planning/improvements-20260420.md`
- `planning/enhancements-plan-20260407.md`
- `planning/update-2026-04-09.md`
- `planning/integration_plan_mm_xm.md`

## Theses & Submissions (`thesis/` & `submissions/`)

- `thesis/`: The MAICEN M10 Final Thesis documents.
- `submissions/`: Official revised submission docs.
- `Presentation-2026-May/`: Thesis and client presentation decks/documents, point-in-time.
- `_backup/`: Pre-revision thesis snapshots, kept only as a rollback point.
- `patches/`: One-off patch files applied during thesis preparation.

## Archived or Legacy Context (`archive/`)

These files are intentionally retained for historical reference.
- `archive/index.html` (Legacy frontend prototype)
- `archive/2026-04-migration-from-nextjs.md`
- `INTEGRATION_GUIDE.md`

## Documentation Maintenance Rules

- Keep dependency instructions aligned with uv and pyproject.toml.
- Prefer forward slashes in paths for cross-platform readability.
- Mark stale process docs as archived instead of silently leaving them active.
- Keep architecture claims consistent with the current repo structure.
- Update this index when adding, moving, or archiving markdown files.
