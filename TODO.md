# TODO

Last reviewed: 2026-08-22

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
- [ ] Inject project, document, rule, storage, and lineage repositories into services;
  remove internal construction of Supabase adapters from business logic.
- [ ] Move default engine/repository composition to an application bootstrap module.

## Priority 3: Rules and IDS

- [ ] Replace handwritten LLM rule normalization with strict Pydantic schemas.
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

Owner: Osama.

## Priority 4: Background Processing and Progress

- [ ] Select and document the queue architecture (Celery, Supabase Queues/pgmq, or
  external n8n orchestration).
- [ ] Add a persistent job repository with queued, running, completed, failed, and
  cancelled states.
- [ ] Move IFC parsing, geometry extraction, compliance analysis, enhancement, and
  report generation out of request handlers.
- [ ] Add retry, idempotency, timeout, cancellation, and worker recovery behavior.
- [ ] Add authenticated Server-Sent Events endpoints for job progress.
- [ ] Replace long-running HTMX requests with job submission and streamed progress UI.

## Priority 5: Viewer Island

- [ ] Wrap the That Open viewer in a custom `HTMLElement` with `connectedCallback()`
  and `disconnectedCallback()` lifecycle management.
- [ ] Define attributes/properties for project ID, IFC URL, selection, visibility, and
  viewer state.
- [ ] Communicate with FastHTML through documented custom events.
- [ ] Preserve WebGL state across unrelated HTMX swaps and dispose workers, observers,
  object URLs, renderers, and models when disconnected.
- [ ] Remove the route-level inline initialization script after the island owns startup.
- [ ] Add desktop/mobile Playwright checks for nonblank rendering, framing, loading,
  interaction, and overlap.

## Priority 6: Analysis and Reporting UX

- [ ] Rename "Simple Analysis" to "Architectural Analysis". Owner: Malak.
- [ ] Rename "Model Vs Rules Analysis" to "MEP Analysis". Owner: Shane.
- [ ] Move reporting responsibilities out of Analysis and standardize report generation
  across architectural and MEP workflows.
- [ ] Consolidate the existing BCF generators/exporters behind one reporting service.
- [ ] Add BCF regression tests for topic IDs, element GUIDs, viewpoints, metadata, and
  archive validity.
- [ ] Add coordination heatmaps after report contracts are stable.
- [ ] Add a color-coded severity column to `/library/rules` if the current rule-library
  presentation does not already expose equivalent severity information.

## Priority 7: Architecture Documentation

- [ ] Create `docs/adr/` and add it to `docs/README.md`.
- [ ] ADR: immutable audit pipeline versus versioned enhancement pipeline.
- [ ] ADR: IDS for property/alphanumeric checks and custom engines for geometry/topology.
- [ ] ADR: evaluator and repository dependency-injection boundaries.
- [ ] ADR: queue, worker, job-state, and SSE architecture.
- [ ] ADR: viewer-island lifecycle and custom-event contract.
- [ ] ADR: environment-owned versus database-owned configuration.
- [ ] Reduce `CLAUDE.md`, `.github/copilot-instructions.md`, and other instruction files
  to concise entry points linking to the canonical documentation; retain agent skills
  only for reusable operational guidance.

## Validation Gates

- [x] Audit tests prove the source IFC hash is unchanged.
- [x] Enhancement tests prove the source and generated storage references differ.
- [x] Concurrent enhancement tests prove project versions cannot collide.
- [ ] Evaluator contract tests cover every registered engine.
- [ ] IDS conformance tests cover representative property, range, enumeration, and
  applicability checks.
- [ ] Review workflow tests prove unapproved drafts cannot enter canonical rules.
- [ ] Queue tests cover retry, duplicate submission, cancellation, and worker failure.
- [ ] Viewer tests verify rendering and lifecycle cleanup on desktop and mobile.
- [x] Supabase security and performance advisors have no unresolved high-severity items.

## Product Ownership and Delivery

- [ ] Leticia to manage milestones, dependencies, acceptance criteria, and delivery
  reporting as product manager.
- [ ] Confirm Marc's ownership area and deliverables.
- [ ] Assign an owner and target milestone to every unchecked priority item.
