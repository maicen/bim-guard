# TODO

Last reviewed: 2026-09-04

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

- [x] Replace broad evaluator `Any`/`dict` contracts with typed request and result models (`RuleEvaluationRequest`, `RuleEvaluationResult` in `app/modules/contracts.py`).
- [x] Make each physics engine implement the evaluator interface directly instead of
      relying on `CallableRuleEvaluator` adapters (`GalvanicCorrosionEngine`, `CreviceCorrosionEngine`, `MICEngine`).
- [x] Keep custom Python evaluators limited to geometry, topology, proximity, and other
      checks IDS cannot express. Documented in `docs/architecture.md`.
- [x] Provide central dependency injection for FastAPI service layer in `app/api/dependencies.py`.
- [x] Inject project, document, rule, storage, and lineage repositories into services;
      remove internal construction of Supabase adapters from business logic.
- [x] Move default engine/repository composition to an application bootstrap module (`app/bootstrap.py`).

Completion evidence (2026-08-29):

- Added strict Pydantic contracts `RuleEvaluationRequest` and `RuleEvaluationResult` to `app/modules/contracts.py` with dictionary-like mapping compatibility (`__getitem__`, `.get()`, `__contains__`, `__eq__`, `to_dict()`).
- Implemented `RuleEvaluator` protocol directly across physics engines (`GalvanicCorrosionEngine`, `CreviceCorrosionEngine`, `MICEngine`) and architectural engines (`EgressAnalysisEngine`, `SpatialDaylightEngine` in `app/engines/bimguard_arch_engine.py`).
- Seeded database-driven architectural code rules (`CODE 9.9.10.1`, `CODE 9.9.4.1`, `CODE 9.7.2.3`, `CODE 9.10.9.14.PW`) under `BUILDING-CODE-PART9`, parameterizing `ifc_egress.py` and `ifc_spatial.py` with dynamic threshold resolution.
- Updated `register_default_engines()` in `app/modules/comparator/engine_registry.py` to register all corrosion and architectural engine instances directly without `CallableRuleEvaluator` wrapping.
- Refactored `ProjectsService`, `DocumentService`, `RuleService`, `SettingsService`, `StaticDataService`, `SupabaseModelLineageRepository`, and `ObjectStorage` to accept optional injected repositories and storage instances.
- Created `ArchAnalysisService` with constructor dependency injection and wired it into `ApplicationContainer` and FastAPI dependency injection (`/api/analyze/arch`).
- Created `app/bootstrap.py` with `ApplicationContainer`, `build_default_container()`, `get_container()`, `set_container()`, and `reset_container()` for single-point composition of persistence adapters, engines, and domain services.
- Re-wired `app/api/dependencies.py` and `app/main.py` to resolve dependencies from the bootstrap container.
- Added comprehensive unit test suites in `tests/test_dependency_inversion.py` (9 tests) and `tests/test_arch_engine_di.py` (6 tests) validating contracts, direct engine evaluation, repository injection, dynamic threshold overrides, and container composition.
- All API and registry test suites passed (`tests/test_api_projects.py`, `tests/test_api_rules.py`, `tests/test_api_analyze.py`, `tests/test_api_events.py`, `tests/test_api_gateway.py`, `tests/test_rule_evaluator_contract.py`, `tests/test_rule_registry.py`).
- Frontend production bundle built cleanly with zero errors (`npm run build`).

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
- [x] Retire TF-IDF, dependency-parser, confidence-scorer, and BERT routing now that
      the single LLM extraction path (`LlamaIndexRuleGenerator`) covers the one
      capability the legacy path had and it lacked (multiple rules per clause).
      Deleted `table_rule_builder.py`, `keyword_filter.py`, `dependency_parser.py`,
      `confidence_scorer.py`, `tfidf_analyzer.py`, `bert_classifier.py`, and the
      orphaned `enhanced_orchestrator.py`; none were reachable from any live API
      route or service. `RuleExtractionService` now defaults to
      `LlamaIndexRuleGenerator` directly — `rule_extractor.py` (`LiteLLMRuleExtractor`)
      and `BIM_GUARD_RULE_EXTRACTION_PROVIDER` are removed.
- [ ] Add precision, recall, F1, and confusion-matrix evaluation for extraction.
- [x] Expose the architectural rule folder selector in `ArchAnalyzeView.svelte` UI dropdown (backend endpoint already supports `rule_folder`). Owner: Marc / Osama.
- [ ] Review and retire non-production rule folders (`door_mock`, `test`,
      `test_folder`), or exclude them from the folder picker.
- [x] Document that selecting a named rule folder excludes the built-in seeded code
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
      See Priority 9 for OAuth and RBAC, planned as a later-stage follow-on.

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
- [x] Surface ARCH compliance BCF artifacts table, live project filtering, and direct downloads in `ReportsView.svelte`.
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

- [x] Coerce numeric strings before the `isinstance(value, (int, float))` guard in
      Module 2's unit-conversion pass. Quantities stored as `IfcLabel('1.2')` currently
      skip conversion and are compared raw, so a 1.2 m window is evaluated as 1.2 mm and
      fails every dimensional rule. Fixed in `_resolve_element_property`'s Pass 8
      (`app/modules/ifc_reader/__init__.py`): a string value is coerced with
      `float()` before the numeric-type check, so a non-numeric string (e.g.
      `FireRating`) still passes through untouched. Covered by
      `tests/test_ifc_property_resolution.py::TestNumericStringUnitConversion`.
- [ ] Log a warning when a length-typed or length-named property is found but skipped
      by unit conversion, so silent misreporting is visible in the run log.
- [ ] Surface the `_get_length_unit_scale_mm` fallback-to-1.0 path as an explicit model
      warning instead of a silent default. Read from source, not reproduced — the reference
      models both declare a valid `LENGTHUNIT`.
- [x] Investigate `ClearWidth` and `OverallWidth` resolving to 2,125 mm on `IfcDoor`
      in the same report where `Width` correctly resolves to 950 mm; 2,125 mm is the door
      height. `_GEOMETRY_PROPERTY_MAP` maps `overallwidth` to the width extractor and
      `clearwidth` to the corridor-width extractor, so the mapping alone does not explain
      it. Reproduction: golden reference model, Doors card, rule folder "All folders".
      **Found and fixed one real defect**: when a door/window has neither a Pset value
      nor a populated `OverallWidth`/`OverallHeight` attribute, `ClearWidth` fell through
      to Pass 7 geometry, which mapped it to `get_corridor_width_mm()` — the *shortest*
      side of the element's own bounding footprint. That algorithm is correct for a
      room/corridor (its narrow passable dimension) but wrong for a door/window leaf,
      whose own footprint is a thin panel: the shortest side there is the frame/leaf
      *thickness*, not the openable width (confirmed against a synthetic 950×50×2125 mm
      door: `ClearWidth` came back 50 mm, the thickness, not 2,125 mm). Fixed in
      `get_geometry_value()` (`app/modules/ifc_reader/ifc_geometry.py`) to route
      `IfcDoor`/`IfcDoorStandardCase`/`IfcWindow`/`IfcWindowStandardCase` through the same
      width extractor as `OverallWidth` instead, matching the precedence already
      documented in `docs/ifc-property-mapping.md` ("ClearWidth → OverallWidth, closest
      available"). Covered by
      `tests/test_ifc_geometry_units.py::test_clear_width_on_door_uses_overall_width_not_leaf_thickness`
      (and `test_corridor_width_still_used_for_rooms` for the non-regression case).
      **Not reproduced**: the exact reported symptom — both `OverallWidth` and
      `ClearWidth` resolving to precisely the door *height* (2,125 mm), with `Width`
      correctly resolving to 950 mm in the same run — could not be reproduced against
      synthetic Pset, Qto, direct-attribute, type-vs-instance-precedence, or axis-aligned
      geometry scenarios (all resolved correctly in isolation; see session notes). This
      needs the actual golden reference model or the live rule definitions used in that
      report to pin down further — re-open if it still reproduces after this fix.
- [ ] Confirm precedence between a declared property value and the geometry
      bounding-box fallback. `Pset_DoorCommon_Egress.ClearWidth` is declared as
      `IFCREAL(0.95)` on the reference model but does not appear as 950 mm in the report.
- [x] Add `requiredheadroom` to `_LENGTH_DIRECT_ATTRS`; the list contains
      `requireheadroom`, so `Pset_StairCommon.RequiredHeadroom` only converts when it
      carries an explicit measure type. Fixed the typo in both
      `app/modules/ifc_reader/__init__.py`'s `_LENGTH_DIRECT_ATTRS` and the same
      typo in `ifc_geometry.py`'s `_GEOMETRY_PROPERTY_MAP` (the header comment on
      `_LENGTH_DIRECT_ATTRS` explicitly requires the two stay in sync). Covered by
      `tests/test_ifc_property_resolution.py::TestRequiredHeadroomTypo`.

Owner: unassigned.

## Priority 9: OAuth and RBAC (Later Stage)

Deferred until core pipeline, rules, and background-processing priorities stabilize.
Builds on the base Supabase Auth / JWT work in Priority 4.1.

- [ ] Add OAuth login (e.g. Supabase Auth third-party providers) for FastAPI endpoints
      and the Svelte 5 SPA.
- [ ] Define roles (e.g. admin, reviewer, viewer) and map permissions to project,
      rule, analysis, enhancement, and reporting endpoints.
- [ ] Enforce Role-Based Access Control (RBAC) via FastAPI dependency injection
      (`app/api/dependencies.py`) and Supabase Row Level Security policies.
- [ ] Reflect role-gated actions and views in the Svelte client (e.g. hide/disable
      enhancement, rule editing, and admin views for unauthorized roles).
- [ ] Add tests proving unauthorized roles cannot invoke restricted API operations.

Owner: unassigned.

## Priority 10: AI Framework Integration: LlamaIndex & LangGraph Architecture

### Module 1 & 1b: Document Ingestion & NLP Annotation (LlamaIndex Core)

- [x] Integrate LlamaIndex as the primary ingestion engine for BEP PDFs, ISO 19650
      guidelines, and regulatory codes (e.g., DIN 4149, NZ Seismic). Layered on top
      of the existing `UnstructuredExtractor`/`LightExtractor`, gated behind
      `BIM_GUARD_USE_LLAMAINDEX_INGESTION`.
- [x] Implement table- and layout-aware document chunking to prevent fragmentation
      of complex engineering tables, schedules, and nested matrices
      (`LlamaIndexIngestor`, `app/modules/document_parsing/llamaindex_ingestor.py`).
- [x] Attach granular clause metadata (clause ID, page numbers, parent section
      headers) to all extracted nodes to maintain traceability in generated BCF
      issue reports (`ClauseMetadata`, `DocumentNodeContract`; `document_nodes` table).
- [x] Implement deontic entity extraction via LlamaIndex Pydantic extractors to
      isolate normative requirements ("shall", "must", "should") into typed
      intermediate schemas (`DeonticStatement`, `llamaindex_program.py`).

### Module 3: Deterministic Rule Generation & IDS Export (LlamaIndex)

- [x] Use LlamaIndex structured data extraction to translate unstructured clause
      chunks into machine-readable rule definitions (`LlamaIndexRuleGenerator`,
      implements the existing `RuleExtractionProvider` protocol as a drop-in
      alternative to `LiteLLMRuleExtractor`). Extracted rules persist as
      `pending_review` drafts (`rule_extraction_drafts` table, `RuleDraftService`)
      with an approve/reject/edit workflow before promotion into `public.rules`.
- [x] Build an automated translation pipeline from extracted rule schemas into
      buildingSMART IDS (Information Delivery Specification) XML schemas.
      `ids_exporter.py`'s export path now builds through `ifctester.ids`
      (buildingSMART's own IDS 1.0 implementation) instead of hand-built
      `ElementTree`, so exported IDS is schema-correct; import tries the same
      strict parser first and falls back to the original lenient parser for
      XML this module produced before the refactor.
- [x] Connect project scope terminology directly to the central buildingSMART
      Data Dictionary (bSDD) API so standardized terms and codes are available
      throughout the project. `app/api/bsdd.py` exposes `BSDDClient`
      (dictionaries, class search, class lookup, property search) at
      `/api/bsdd/*`; the client's live-network paths were corrected against
      buildingSMART/bSDD's own OpenAPI spec (Dictionary v1 response is
      `{"dictionaries": [...]}` not a bare array; Class v1 takes a full `Uri`,
      not `dictionaryUri`+`code`; TextSearch is v2, not v1) so real bSDD
      calls parse correctly instead of always silently falling back offline.
- [x] Let users select a project classification standard, such as Uniclass or
      CCI, directly from project settings. `projects.classification_standard`
      (migration `20260902160000_add_classification_standard_to_projects.sql`)
      stores a bSDD dictionary code, editable from `ProjectEditModal.svelte`
      and the wizard's Scope step, both populated from `GET /api/bsdd/dictionaries`.
- [x] Add bSDD-powered autocomplete suggestions in the scope module for
      correctly coded element and property names as users type.
      `BsddAutocomplete.svelte` backs the rule builder's new Target IFC Class
      field and Property Name field (`RuleForm.svelte`), debounced against
      `/api/bsdd/classes/search` and `/api/bsdd/properties/search`; picking a
      property suggestion also fills its property set and unit.
      `target_ifc_class` is now a first-class field on the rule create/update
      API and response contracts (it already existed on the `rules` table and
      in `RuleService`, but was not reachable from the REST layer or UI).
- [x] Translate human-readable information requirements into machine-readable
      IDS XML files that software can test and verify. Already covered by the
      `ids_exporter.py` work above (`build_ids_document` / `import_ids_ruleset`,
      wired to `POST /api/rules/import-ids`, `GET /api/rules/export-ids`, and
      the drafts `ids-preview` endpoint).

### Agent & CDE Orchestration (`app/agent`, Module 4 & Services) (LangGraph)

- [x] Implement a LangGraph state machine for the Digital Inspector agent
      to coordinate cyclical multi-tool execution (querying IFC
      models, checking database cache, dispatching bSDD lookups, running
      validation engines). New `app/digital_inspector/` package (separate from
      the generic `app/agent/` OpenRouter coding assistant), built on LangGraph's
      `create_react_agent`, exposed via `POST /api/projects/{id}/inspect`.
- [x] Expose LlamaIndex retrieval and rule-extraction modules as callable tools
      inside the LangGraph supervisor agent (`extract_rules_from_document` tool
      wraps `RuleExtractionService.extract_rule_drafts`).
- [x] Model ISO 19650 Common Data Environment (CDE) state transitions
      (`WIP` → `Shared` → `Published` → `Archived`) as a LangGraph state graph
      with automated compliance gates. `app/digital_inspector/cde_graph.py` is a
      thin wrapper whose nodes call the existing, already-tested
      `CDEStateMachine.evaluate_transition()` for every gate decision — the real
      transactional `transition_project()` write path is untouched; exposed as
      the `check_cde_transition` agent tool.
- [ ] Implement LangChain-compatible webhook handlers for asynchronous
      notifications to external issue-tracking platforms (e.g., ACC, BIM Track).
      Deferred: no existing integration point, credentials, or chosen platform
      (ACC vs BIM Track) exists yet; needs its own scoping conversation.

Owner: unassigned.

Completion evidence (2026-09-02):

- Added `llama-index-core`, `llama-index-llms-litellm`, `langgraph`,
  `langchain-core`, `langchain-litellm`, and `ifctester` as required
  dependencies (`pyproject.toml`).
- New migrations: `20260902120000_create_document_nodes.sql`,
  `20260902130000_create_rule_extraction_drafts.sql`.
- New contracts in `app/modules/contracts.py`: `ClauseMetadata`,
  `DeonticStatement`, `DocumentNodeContract`, `DocumentIngestResponse`,
  `RuleDraftStatus`, `RuleExtractionDraft`, `RuleExtractionDraftListResponse`,
  `RuleDraftReviewRequest`, `InspectorQueryRequest`, `InspectorToolCallContract`,
  `InspectorResponse`.
- New endpoints: `POST /api/documents/{id}/ingest`,
  `POST /api/documents/{id}/rules/extract-drafts`,
  `GET /api/documents/{id}/rules/drafts`,
  `GET /api/documents/{id}/rules/drafts/ids-preview`,
  `PATCH /api/rules/drafts/{draft_id}`, `POST /api/rules/drafts/{draft_id}/promote`,
  `POST /api/projects/{id}/inspect`. Existing `POST /api/rules/extract` and
  `POST /api/rules/bulk` are unchanged.
- LlamaIndex ingestion is flag-gated (`BIM_GUARD_USE_LLAMAINDEX_INGESTION`).
  Rule extraction itself has since been consolidated onto a single path,
  `LlamaIndexRuleGenerator` (2026-09-04) — see Priority 3 above;
  `LiteLLMRuleExtractor` and `BIM_GUARD_RULE_EXTRACTION_PROVIDER` no longer exist.
- 984 tests pass (+26 new: `test_llamaindex_ingestion.py`,
  `test_rule_draft_workflow.py`, `test_ids_export.py`, `test_digital_inspector.py`,
  `test_cde_graph.py`; 2 pre-existing IDS tests and 1 settings test updated for
  the corrected schema-valid XML shape and the two new settings keys).

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
- **ARCH Audit Ruleset Scoping & Manual Trigger**: Added dynamic ruleset folder selection loaded via `rulesApi.folders()` in `ArchAnalyzeView.svelte`, replaced auto-runs on mount and project change with intentional manual execution, and added real-time BCF save status indicators with direct download and 3D ThatOpen viewer transitions.
- **ARCH Compliance BCF Reports**: Expanded `ReportsView.svelte` with a dedicated, filterable ARCH BCF artifacts table sourced from `GET /api/analyze/bcf/list`, showing issue counts, file sizes, timestamps, and one-click 3D viewer and `.bcfzip` download actions.
- **Typed BCF Contracts**: Added `BcfArtifact` schema to `frontend/src/lib/types.ts` and typed `analyzeApi.listBcfArtifacts()` in `frontend/src/lib/api.ts`.

---

# Verification Plan

- [ ] Navigate to http://localhost:5173
- [ ] Inspect Sidebar under "Analysis":
  - Verify types: "Architectural", "Piping", "Seismic"
- [ ] Click "Architectural":
  - Verify it opens Architectural Compliance view
  - Verify "Category: Arch"
  - Verify only architectural rulesets
- [ ] Click "Piping":
  - Verify it opens Piping System Corrosion Audit
  - Verify "Category: Piping"
  - Verify Piping rulesets (BIMGUARD-GC-001, CC-001, MC-001)
- [ ] Click "Seismic":
  - Verify it opens Seismic Buffer & Bracing Audit
  - Verify "Category: seismic"
  - Verify Seismic rulesets (BIMGUARD-SB-001)
- [ ] Click "Rules Catalog" in Library:
  - Verify category selector pills (All Categories, Arch, Piping, seismic)
  - Verify table contains Category column
- [ ] Take screenshots for each step

## Status

Verification blocked: The open_browser_url tool failed multiple times because the Playwright environment driver could not be installed (HTTP 404 from playwright.azureedge.net).
