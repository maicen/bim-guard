# TODO

Last reviewed: 2026-08-29

## Completed Foundations

- [x] Centralize deterministic `.env` loading for application startup, logging,
  persistence, object storage, and module configuration.
- [x] Remove stale database-backed storage/model settings and legacy configuration
  paths.
- [x] Separate enhancement planning/execution from read-only analysis services.
- [x] Execute IFC enhancement against a temporary output instead of overwriting the
  source model.
- [x] Upload versioned enhanced IFC artifacts to Supabase Storage under
  `enhancements/{project_id}`.
- [x] Deploy the `model_enhancement_lineage` ledger with project/version uniqueness,
  source/output validation, and append-only application privileges.
- [x] Add dependency-injected storage, improver, and lineage contracts to the
  enhancement pipeline.
- [x] Add a rule-evaluator protocol and registry for GC-001, CC-001, and MC-001.
- [x] Add IDS XML import/export for compatible property rules.
- [x] Add extracted-rule preview, inline correction, confidence/review badges, and
  per-rule save controls.

## Priority 1: Production Pipeline Separation

- [x] Replace placeholder `AnalysisService` results with the real comparator registry.
- [x] Make the audit pipeline the controlling application analysis path.
- [x] Guarantee that audit processing never invokes IFC mutation or `improver.py`.
- [x] Return typed audit issues and BCF topics from the audit pipeline.
- [x] Connect DB-backed rules to audit execution. Owner: Osama.
- [x] Add a separately authorized enhancement command/API; do not expose enhancement
  as an audit option.
- [x] Allocate enhancement versions transactionally from the lineage repository rather
  than accepting arbitrary caller-provided versions.
- [x] Add project UI for enhancement history, source version, generated version, status,
  summary, and artifact download.

Completion evidence (2026-08-22):

- `BIMGuard_App` routes MEP evaluation through the immutable audit service and merges
  DB-backed rule failures into the same issue/BCF topic contract.
- Supabase migration `20260822141146_allocate_model_enhancement_versions` provides
  collision-free database-owned version allocation; eight concurrent calls returned
  unique consecutive versions.
- The enhancement route is fail-closed behind `BIM_GUARD_ENHANCEMENT_TOKEN` and is
  separate from all audit routes.
- Production smoke test generated project 5 version 1, preserved the source SHA-256,
  uploaded a 231,306-byte IFC artifact, and recorded lineage row 2.
- Desktop and 390 px mobile browser checks passed; invalid authorization left lineage
  unchanged, and history/download controls rendered correctly.

## Priority 2: Dependency Inversion

- [ ] Replace broad evaluator `Any`/`dict` contracts with typed request and result models.
- [ ] Make each physics engine implement the evaluator interface directly instead of
  relying on `CallableRuleEvaluator` adapters.
- [ ] Keep custom Python evaluators limited to geometry, topology, proximity, and other
  checks IDS cannot express.
- [x] Provide central dependency injection for FastAPI service layer in `app/api/dependencies.py`.
- [ ] Inject project, document, rule, storage, and lineage repositories into services;
  remove internal construction of Supabase adapters from business logic.
- [ ] Move default engine/repository composition to an application bootstrap module.

## Priority 3: Rules and IDS

- [x] Drive compliance and corrosion engines dynamically from database-stored rules (`RuleService` & `corrosion_rule_catalog.py`). Owner: Osama.
- [x] Implement in-memory engine catalog hot-reloading (`reload_all_catalogs()`) on analysis runs without server restarts.
- [x] Extend rule engine with advanced validation operators: field consistency (`compare_property`, `name_pattern`), element uniqueness within scope (`uniqueness_scope`), and relative property thresholds (`value_min_property`, `value_max_property`, offsets).
- [x] Seed standard building code rulesets (`BUILDING-CODE-PART9`, `BUILDING-CODE-PART9-EXT`) and corrosion rulesets (`BIMGUARD-GC-001`, `BIMGUARD-CC-001`, `BIMGUARD-MC-001`) via `ruleset_seeder.py`.
- [x] Scope architectural analysis runs by rule folder / ruleset ID in `orchestrator.py` via `RuleService.list_by_ruleset(rule_folder)`.
- [ ] Replace handwritten LLM rule normalization with strict Pydantic schemas in `rule_extractor.py`.
- [ ] Reject or quarantine invalid structured responses with actionable validation
  messages instead of silently returning an empty rule list.
- [ ] Define a durable extraction-draft model separate from canonical rules.
- [ ] Add explicit approve/reject decisions, reviewer identity, timestamps, comments,
  and an immutable review audit trail.
- [ ] Prevent `Save all` from inserting unapproved or `needs_review` drafts into the
  canonical rule table.
- [ ] Preserve source text and extraction metadata through draft approval.
- [ ] Transition alphanumeric and Property Set checks to `ifcopenshell.ids` validation.
- [ ] Map IDS validation results into the shared issue and BCF model.
- [ ] Validate imported/exported IDS documents with the buildingSMART IDS schema.
- [ ] Retire TF-IDF, dependency-parser, confidence-scorer, and BERT routing only after
  the Pydantic LLM workflow meets an agreed evaluation threshold.
- [ ] Add precision, recall, F1, and confusion-matrix evaluation for extraction.
- [ ] Expose the architectural rule folder selector in `ArchAnalyzeView.svelte` UI dropdown (backend endpoint already supports `rule_folder`). Owner: Marc / Osama.
- [ ] Review and retire non-production rule folders (`door_mock`, `test`,
  `test_folder`), or exclude them from the folder picker.
- [ ] Document that selecting a named rule folder excludes the built-in seeded code
  rules rather than narrowing them; update help text in UI.

Owner: Osama.

## Priority 4: Background Processing and Progress

- [ ] Select and document the queue architecture (Celery, Supabase Queues/pgmq, or
  external n8n orchestration).
- [ ] Add a persistent job repository with queued, running, completed, failed, and
  cancelled states.
- [ ] Move IFC parsing, geometry extraction, compliance analysis, enhancement, and
  report generation out of request handlers into dedicated background workers.
- [ ] Add retry, idempotency, timeout, cancellation, and worker recovery behavior.
- [x] Add authenticated Server-Sent Events endpoints for job progress (`GET /api/events/{project_id}`).
- [x] Replace polling and HTMX swaps with Server-Sent Events (SSE) stream in FastAPI gateway and Svelte client.

## Priority 4.1: FastAPI Gateway & Decoupled Svelte 5 SPA Architecture

- [x] Add `fastapi>=0.115.0` to backend dependencies (`pyproject.toml`).
- [x] Formalize strict Pydantic data contracts for Project, Rule, Analysis, Workflow, and Revit Sync entities (`app/modules/contracts.py`).
- [x] Synchronize TypeScript types in `frontend/src/lib/types.ts` with Pydantic contracts.
- [x] Initialize FastAPI API Gateway under `app/api/` with CORS and OpenAPI documentation (`/api/docs`).
- [x] Implement REST routers: `projects.py`, `rules.py`, `analyze.py`, `events.py`, `documents.py`, `settings.py`, and `dashboard.py`.
- [x] Implement EventBroadcaster and async queue subscription in `pipeline_tracker.py` for real-time SSE streaming.
- [x] Decommission and purge all legacy FastHTML and MonsterUI residuals (`app/components/`, `app/routes/`, `app/views/`, `app/compat/`), reducing technical debt by 14,500+ lines of Python code.
- [x] Refactor `app/main.py` into a pure FastAPI application serving API routes and the built Svelte 5 SPA fallback.
- [x] Scaffold and build standalone Vite + Svelte 5 SPA client under `frontend/` (zero build errors).
- [x] Implement typed API client (`frontend/src/lib/api.ts`) and SSE subscriber (`frontend/src/lib/sse.ts`).
- [x] Build comprehensive Svelte 5 views:
  - `ProjectsView.svelte` (project catalog, creation modal, delete confirmation)
  - `AnalyzeView.svelte` (MEP/corrosion pipeline, stage runner, issue table, BCF export)
  - `ArchAnalyzeView.svelte` (architectural compliance, building summary, spatial checks, 3D element inspector)
  - `RulesView.svelte` (ruleset folder sidebar, rule editor modal, bulk actions, seed action, IDS export)
  - `RuleExtractionView.svelte` (document upload, raw text parsing, rule extraction preview)
  - `DocumentsView.svelte` (project standards and client documents catalog and upload)
  - `ViewerView.svelte` (standalone 3D OpenBIM model viewer)
  - `WorkflowView.svelte` (live pipeline dashboard with per-engine stage tracking)
  - `DashboardView.svelte` (system overview KPIs, database connection health, quick navigation)
  - `SettingsView.svelte` (runtime settings management, persistent theme configuration)
  - `RevitSyncView.svelte` (bidirectional pyRevit live element synchronization)
  - `ReportsView.svelte`, `ModelingManualView.svelte`, and `UserManualView.svelte`
- [x] Implement persistent dark/light theme switching with smooth transitions (`ThemeToggle.svelte` and `settings_service.py`).
- [x] Remove artificial max-width constraints on route view containers for fluid high-density layouts.
- [x] Implement native `@thatopen/components` Svelte wrapper in `IfcViewer.svelte` to retire iframe embedding.
- [ ] Add user authentication (Supabase Auth / JWT) across FastAPI endpoints and Svelte client.

## Priority 5: 3D OpenBIM Viewer Integration

- [x] Port 3D OpenBIM viewer from legacy iframe embed to native Svelte component (`IfcViewer.svelte`).
- [x] Implement lifecycle management via Svelte `onMount` and `onDestroy` (releasing renderers, loaders, and WebGL contexts).
- [x] Provide reactive properties for `projectId`, `elementGuid`, and `bcfArtifactId`.
- [x] Implement camera viewpoint navigation and highlight framing from compliance issue selection.
- [x] Add direct local IFC file upload and client-side rendering.
- [ ] Add desktop/mobile Playwright checks for nonblank rendering, framing, loading,
  interaction, and overlap.
- [ ] Profile and optimize WebGL memory usage for multi-model loading sessions.

## Priority 6: Analysis and Reporting UX

- [x] Fully implement "Architectural Analysis" User Interface (`ArchAnalyzeView.svelte`). Owner: Malak / Team.
- [x] Fully implement "MEP Analysis" User Interface (`AnalyzeView.svelte`). Owner: Shane / Team.
- [x] Consolidate BCF report generation and export behind `ReportArtifactService` and `app/api/analyze.py` endpoints (`/api/analyze/bcf/*`).
- [x] Fix BCF topic viewpoints and camera GUID synchronization for seamless 3D navigation.
- [x] Add color-coded severity badges (Critical, High, Medium, Low) to rules presentation in `RulesView.svelte` and issues in `AnalyzeView.svelte`.
- [x] Support multi-format compliance report exports: BCF 2.1 zip, CSV, and JSON (`/api/analyze/export`).
- [ ] Add coordination heatmaps after report contracts are stable.
- [ ] Add formal automated BCF regression tests for topic IDs, element GUIDs, viewpoints, metadata, and archive validity.

## Priority 7: Architecture Documentation

- [x] Update `docs/architecture.md` to Version 2.0 covering the decoupled FastAPI + Svelte 5 SPA architecture.
- [x] Update `CLAUDE.md`, `AGENTS.md`, `DESIGN.md`, and `README.md` to reflect the pure FastAPI backend and Svelte 5 frontend conventions.
- [ ] Create `docs/adr/` and add it to `docs/README.md`.
- [ ] ADR: immutable audit pipeline versus versioned enhancement pipeline.
- [ ] ADR: IDS for property/alphanumeric checks and custom engines for geometry/topology.
- [ ] ADR: evaluator and repository dependency-injection boundaries.
- [ ] ADR: queue, worker, job-state, and SSE architecture.
- [ ] ADR: native Svelte 3D viewer component lifecycle and state management.
- [ ] ADR: environment-owned versus database-owned configuration.

## Priority 8: IFC Ingestion Correctness

- [ ] Coerce numeric strings before the `isinstance(value, (int, float))` guard in
  Module 2's unit-conversion pass. Quantities stored as `IfcLabel('1.2')` currently
  skip conversion and are compared raw, so a 1.2 m window is evaluated as 1.2 mm and
  fails every dimensional rule.
- [ ] Log a warning when a length-typed or length-named property is found but skipped
  by unit conversion, so silent misreporting is visible in the run log.
- [ ] Surface the `_get_length_unit_scale_mm` fallback-to-1.0 path as an explicit model
  warning instead of a silent default. Read from source, not reproduced — the reference
  models both declare a valid `LENGTHUNIT`.
- [ ] Investigate `ClearWidth` and `OverallWidth` resolving to 2,125 mm on `IfcDoor`
  in the same report where `Width` correctly resolves to 950 mm; 2,125 mm is the door
  height. `_GEOMETRY_PROPERTY_MAP` maps `overallwidth` to the width extractor and
  `clearwidth` to the corridor-width extractor, so the mapping alone does not explain
  it. Cause not yet identified. Reproduction: golden reference model, Doors card,
  rule folder "All folders".
- [ ] Confirm precedence between a declared property value and the geometry
  bounding-box fallback. `Pset_DoorCommon_Egress.ClearWidth` is declared as
  `IFCREAL(0.95)` on the reference model but does not appear as 950 mm in the report.
- [ ] Add `requiredheadroom` to `_LENGTH_DIRECT_ATTRS`; the list contains
  `requireheadroom`, so `Pset_StairCommon.RequiredHeadroom` only converts when it
  carries an explicit measure type.

Owner: unassigned.

## Validation Gates

- [x] Audit tests prove the source IFC hash is unchanged.
- [x] Enhancement tests prove the source and generated storage references differ.
- [x] Concurrent enhancement tests prove project versions cannot collide.
- [x] Database-driven rule workflow tests pass (`tests/test_db_rules_workflow.py`).
- [x] Svelte 5 frontend production build compiles with zero errors (`npm run build`).
- [x] Supabase security and performance advisors have no unresolved high-severity items.
- [ ] Evaluator contract tests cover every registered engine.
- [ ] IDS conformance tests cover representative property, range, enumeration, and
  applicability checks.
- [ ] Review workflow tests prove unapproved drafts cannot enter canonical rules.
- [ ] Queue tests cover retry, duplicate submission, cancellation, and worker failure.
- [ ] Playwright tests verify 3D viewer rendering and lifecycle cleanup on desktop and mobile.
- [ ] Add the golden/broken reference IFC pair as regression fixtures. The golden model
  must pass its architectural checks; the broken model must report all four planted
  faults.
- [ ] Assert unit conversion end to end: a 1.2 m window height on a metre-based model
  must evaluate as 1200 mm.
- [ ] Assert that fire separation reports a missing `FireRating` on a party wall, and
  that its absent-boundary path is reported as "not checked" rather than as a pass.

## Product Ownership and Delivery

- [ ] Leticia to manage milestones, dependencies, acceptance criteria, and delivery
  reporting as product manager.
- [x] Confirm Marc's ownership area and deliverables — architectural slice: reference
  models, architectural rule set, IFC modelling and export guidance, and validation of
  the ARCH pipeline.
- [ ] Assign an owner and target milestone to every unchecked priority item.

---

### Completion Evidence (2026-08-29)

- **FastAPI API Gateway**: Fully operational at `/api` with REST routers for `projects`, `rules`, `analyze`, `documents`, `settings`, and `dashboard`, backed by OpenAPI interactive docs (`/api/docs`).
- **Decoupled Svelte 5 SPA**: Built cleanly via Vite with 14 functional route views, persistent Dark/Light theme switching, reactive store synchronization, and full responsive design.
- **FastHTML Decommissioning**: Deleted legacy Python UI files under `app/components/`, `app/routes/`, `app/views/`, and `app/compat/`, reducing the backend codebase by over 14,500 lines.
- **Native 3D Viewer**: `IfcViewer.svelte` natively integrates `@thatopen/components` into the DOM with camera viewpoint transitions and BCF 2.1 guideline synchronization, eliminating legacy iframe embeds.
- **Database-Driven Rules**: Galvanic, crevice, and microbiological engines dynamically consume thresholds, scoring models, and velocity classes from Supabase Postgres; in-memory catalogs reload seamlessly on execution (`tests/test_db_rules_workflow.py`).
- **Real-Time Streaming**: Server-Sent Events (`/api/events/{project_id}`) stream stage transitions and duration metrics directly to `PipelineProgress.svelte`.
