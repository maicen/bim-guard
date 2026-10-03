# BIM-Guard Engineering Roadmap & TODO

Last reviewed: 2026-09-29  
Status: Active Monolith (FastAPI + Decoupled Svelte 5 SPA + Pure Python Compute Engines + Self-Hosted Supabase)

---

## Priority 1: AI Opportunities & Machine Learning Roadmap

The AI subsystem operates on the periphery of the deterministic compliance engines under `app/ai/`, isolating probabilistic models from deterministic building code evaluations (`app/engines/`).

### Recommended Next Implementation (Top Priority)

- [ ] **Active Learning False-Positive Classifier & Feedback Loop**:
  - **Context & Motivation**: Deterministic geometry and spatial checks unavoidably flag edge cases (e.g. doors in recessed alcoves, custom partition wall assemblies, angled stair landings). Reviewers suffer from alert fatigue when examining repetitive, non-actionable defects.
  - **Existing Foundation**: `EvaluationService` (`capture_results`), `public.evaluation_findings` database table, `frontend/src/routes/EvaluationView.svelte`, and the evaluation scoring harness in `maicen/bim-guard-evaluation` (`eval/score_evaluation_findings.py`) are already fully operational.
  - **Implementation**:
    1. Implement concrete `FalsePositiveClassifier` under `app/ai/ml/` fulfilling `IPredictiveModel` (`predict(features: Dict[str, Any]) -> Dict[str, Any]`).
    2. Extract normalized feature vectors from `evaluation_findings.rule_snapshot`, IFC class, storey, spatial envelope, and bounding box dimensions.
    3. Train/calibrate a lightweight classifier (logistic regression / XGBoost / scikit-learn) on expert human verdicts (`PASS` vs `FAIL` ground truth) to predict `p(false_positive)`.
    4. Enrich compliance issues in `ArchAnalysisService` with a `confidence_score` and `predicted_fp_risk` badge.
    5. Add an inline "Flag False Positive" feedback action in `ArchAnalyzeView.svelte` and `AnalyzeView.svelte` that logs directly to `evaluation_findings` and triggers incremental model recalibration.

### High-Priority Follow-on AI Opportunities

- [ ] **AI-Powered Semantic bSDD Mapper**:
  - Automatically map unstandardized model property names and custom Revit family parameters to official buildingSMART Data Dictionary (bSDD) classifications (e.g. Uniclass, OmniClass, standard IFC Property Sets).
  - Builds on existing `BSDDClient` (`app/services/bsdd_client.py`), `/api/bsdd/*` endpoints, `projects.classification_standard`, and `BsddAutocomplete.svelte`.
- [ ] **Generative IDS (Information Delivery Specification) from Natural Language EIRs**:
  - Use LLMs to read unstructured Exchange Information Requirements (EIRs) or BIM Execution Plans (BEPs) and automatically generate schema-valid buildingSMART IDS 1.0 XML files.
  - Extends `LlamaIndexRuleGenerator` and `ids_exporter.py` (`ifctester.ids`) with generative requirement authoring.
- [ ] **Vision-Language Models (VLM) for BCF Snapshot Auditing**:
  - Implement concrete `IVisionModel` in `app/ai/vision/` to visually audit rendered 3D camera viewpoints and clash snapshots, automatically filtering out non-physical or acceptable conditions before human dispatch.

### Exploratory & Long-Term AI Research

- [ ] **Digital Inspector NL-to-Geometry Query Translation**: Expand the LangGraph `DigitalInspector` agent tools to convert natural language queries into dynamic `ifcopenshell` semantic spatial queries.
- [ ] **Natural Language Dashboard Assistant**: Text-to-SQL / PostgREST assistant allowing natural language queries over project compliance analytics.
- [ ] **Synthetic IFC Data Generator**: Procedurally generate IFC edge-case models with planted compliance failures to benchmark rule coverage and physics engines.
- [ ] **Graph Neural Networks (GNNs) on IFC Spatial Graphs**: Infer missing topological connectivity, room usages, or circulation paths when IFC metadata is unpopulated.
- [ ] **Predictive Cost & Schedule Impact Model**: ML forecasting in `app/ai/ml/` to predict remediation costs and schedule delays from issue features and historical resolution data.
- [ ] **Automated Generative Remediation**: Propose physical routing and clearance adjustments (e.g. via 3D A* pathfinding) for detected clearance clashes.
- [ ] **Multi-Agent Compliance Orchestration**: Multi-agent LangGraph workflow where domain agents (Architectural, Structural, MEP) negotiate clash resolution and delegate validation tasks.

---

## Priority 2: Architectural Evolution & Background Compute Strategy

### Asynchronous Worker Pool & Job Queue

- [ ] **Dedicated Async Compute Worker Pool (Task Queue)**:
  - Migrate long-running compliance evaluations (`ArchAnalysisService.run_analysis`), heavy IFC parsing, and geometry extraction out of FastAPI request handlers into a dedicated worker pool (Celery, ARQ, or SAQ backed by Redis).
  - Isolate CPU-bound and memory-intensive `ifcopenshell` C++ operations from the Uvicorn web gateway to eliminate worker thread starvation and Out-Of-Memory (OOM) web process crashes.
  - Implement durable, database-backed job states (`queued`, `running`, `completed`, `failed`, `cancelled`) with retry policies, timeouts, and worker recovery.
- [ ] **Distributed Pub/Sub for Pipeline Tracker & Real-Time SSE**:
  - Transition `PipelineTracker` from in-process `asyncio.Queue` to a distributed broker (Redis Pub/Sub or Supabase PostgreSQL `LISTEN`/`NOTIFY`).
  - Resolve the multi-worker reporting gap where SSE clients connected to Uvicorn Worker A do not receive progression events emitted on Worker B.
- [ ] **Streaming & Direct-to-Storage Model Ingestion**:
  - Replace in-memory buffering (`await ifc_file.read()`) in `/api/analyze/upload` and `/api/projects/{id}/models` with chunked streaming or pre-signed direct-to-storage upload URLs to Supabase Storage, mitigating memory spikes on large (300 MB+) IFC models.
- [ ] **Pre-Parsed Intermediate Model Representation (Extracted Cache Layer)**:
  - Extract and cache structured element metadata, spatial containment hierarchies, property sets, and bounding boxes into an intermediate cache layer (DuckDB, Parquet, or PostgreSQL JSONB tables) upon initial IFC upload.
  - Allow subsequent compliance re-runs and parameter variations to execute in milliseconds without re-parsing raw IFC files from disk.
- [ ] **Semantic Caching & Rate-Limiting for LLM Rule Extraction**:
  - Introduce SHA-256 clause content hashing and semantic caching for `RuleExtractionService` / `LlamaIndexRuleGenerator` to avoid redundant LLM invocations and token spend on re-analyzed standard documents.
  - Implement token budget guards and rate-limiting across document extraction routes.
- [ ] **Transactional Unit-of-Work for CDE Governance**:
  - Wrap ISO 19650 Common Data Environment (CDE) state transitions (`WIP` → `SHARED` → `PUBLISHED` → `ARCHIVED`) and audit event logging inside an explicit transactional unit-of-work to guarantee atomic state progression.

---

## Priority 3: Architectural Compliance Engine & Rules Governance

- [ ] **Cross-Element Relative Property Bounds**:
  - Extend `value_min_property` / `value_max_property` resolution in `app/modules/ifc_reader/__init__.py::extract_for_compliance` to reference properties on a DIFFERENT element than the one targeted (e.g. "exit doors shall be separated by not less than one-half of the building's maximum diagonal").
  - Requires resolving the target element's containing space/building diagonal and applying the existing scale/offset operators on top.
- [ ] **Map IDS Validation Failures to Shared Issues and BCF Topics**:
  - `IDSValidationService` executes `ifctester.ids` (`Ids.validate()`), but failed specifications are not yet converted into typed `Issue` records or BCF topics for 3D navigation.
- [ ] **Validate Imported/Exported IDS with buildingSMART Schema**:
  - Add schema validation checks to ensure exported and imported IDS XML strictly conforms to buildingSMART IDS 1.0 XSD schemas.
- [ ] **Retire Non-Production Rule Folders**:
  - Review and archive non-production rule folders (`door_mock`, `test`, `test_folder`) or exclude them from the folder picker in `ArchAnalyzeView.svelte`.
- [ ] **Unit Conversion Edge-Case Warnings**:
  - Log an explicit warning when a length-typed or length-named property is found but skipped by unit conversion.
  - Surface `_get_length_unit_scale_mm` fallback-to-1.0 as a visible model warning rather than a silent default.
- [ ] **Property vs. Geometry Precedence Resolution**:
  - Clarify and test precedence between declared property values and bounding-box geometry fallbacks (e.g. `Pset_DoorCommon_Egress.ClearWidth` vs. calculated geometry).

---

## Priority 4: Graph Database Integration (Neo4j)

- [ ] **Wire `GraphService` into `LlamaIndexRuleGenerator` for GraphRAG**:
  - Connect `Neo4jDatabaseProvider` into the document extraction pipeline, mapping hierarchical building codes (Section → Clause) to the IFC ontology (Building → Storey → Space) to eliminate LLM hallucinations.
- [ ] **Execute Complex Topological Rules via Native Cypher**:
  - Implement a Proof of Concept evaluating multi-element spatial relationships via native Cypher queries (e.g., `MATCH (p:IfcSpace)-[:ADJACENT_TO]->(c:IfcSpace) WHERE ...`) rather than ad-hoc Python loops.

---

## Priority 5: ISO 19650-5 Security & Enterprise Governance

- [ ] **Attribute-Based Access Control (ABAC)**:
  - Implement per-entity security clearance and classification models across projects, models, and compliance reports.
- [ ] **Security Classification Taxonomy**:
  - Implement security labeling (Public / Commercial Sensitive / Infrastructure Restricted / High Security Restricted) at container, IFC element, and zone granularity.
- [ ] **Dynamic IFC Redaction by Clearance**:
  - Redact sensitive IFC elements, property sets (e.g. `Pset_SecurityProperties`), and geometry on download or 3D viewing based on the requesting user's clearance.
- [ ] **Hash-Chained Audit Ledger**:
  - Deploy a tamper-evident audit ledger where each mutation records a SHA-256 hash chained to the preceding record's hash.
- [ ] **PostgreSQL Row Level Security (RLS) Policies**:
  - Replace `service_role`-only locks with real Postgres RLS policies enforcing tenant isolation directly at the database tier for authenticated user roles.

---

## Priority 6: Enterprise UX & 3D Coordination

- [ ] **Customizable "My Home" Dashboard**:
  - Grid layout with configurable widgets: Clearance Violations by Severity, Live BCF Issue Feed, Recent IFC Models, and Pending CDE Transitions.
  - Implement backend aggregation endpoints to power dashboard metrics.
- [ ] **Split-Screen Model Coordination View**:
  - 3D ThatOpen viewer + Issue Register side-by-side with a resizable split divider and bidirectional selection synchronization (`IfcViewer.svelte` + `IssueTable`).
- [ ] **Slide-Out Inspector Drawer**:
  - Replace blocking modal overlays with a slide-out drawer anchored to the right of the 3D viewport for detailed compliance inspection.
- [ ] **Floating Contextual Action Menu**:
  - Contextual action menu anchored to the active selection (3D element, table row, card).
- [ ] **3D Viewer Automated Playwright E2E & Performance**:
  - Automated tests for nonblank WebGL canvas rendering, framing, camera viewpoints, and memory lifecycle cleanup.
  - Profile and optimize WebGL memory usage for multi-model sessions.
- [ ] **Automated BCF Regression Testing**:
  - Automated test suite validating topic IDs, element GUIDs, camera viewpoints, and BCF 2.1 zip structure integrity.

---

## Priority 7: Agent-Callable Infrastructure & MCP Server

Turn BIM-Guard into an agent-callable infrastructure platform for external AI agents:

- [x] **Model Context Protocol (MCP) Server** (see [docs/mcp-server.md](docs/mcp-server.md)):
  - Wrap BIM-Guard's compliance analysis, rule extraction, and document APIs as a dedicated MCP server so agent clients (Claude, Cursor, external tools) can execute checks natively.
- [ ] **Agent-to-Agent (A2A) Agent Card**:
  - Expose BIM-Guard's inspector agent via `/.well-known/agent-card.json`.
- [x] **OAuth Discovery & Protected Resource Metadata** (MCP endpoint done, see [docs/mcp-server.md](docs/mcp-server.md); `/api/*`-wide metadata still open):
  - Publish RFC 8414 OAuth authorization metadata and RFC 9728 `.well-known/oauth-protected-resource` describing `/api/*` resource scopes.
- [ ] **Skills Index**:
  - Publish machine-readable catalog of BIM-Guard capabilities (analysis, rule drafting, BCF export).
- [ ] **LangChain / Webhook Integrations**:
  - External issue-tracking platform notification webhooks (Autodesk Construction Cloud / ACC, BIM Track).

---

## Priority 8: SOC 2 & ISO 27001 Compliance Roadmap

- [ ] **Fill Legal Placeholders in Compliance Docs**:
  - Complete placeholders in `docs/compliance/gdpr-privacy-policy.md` and `docs/compliance/data-processing-agreement.md` and obtain legal review.
- [ ] **ISO 27001 ISMS Skeleton**:
  - Establish asset inventory, risk register, and access review cadences via compliance automation (e.g. Vanta/Drata).
- [ ] **SOC 2 Type II Observation Window**:
  - Select SOC 2 auditor and initiate 3–12 month observation window.
- [ ] **AuditLogService Expansion**:
  - Extend `AuditLogService.record(...)` to document access grants, ruleset bindings, and LLM credential mutations.
- [ ] **Audit Log Retention Policy**:
  - Define bounded retention and purge policies for `public.audit_log`.

---

## Priority 9: Validation Gates & Logging Improvements

- [ ] **Validation Gates**:
  - Evaluator contract tests covering every registered engine.
  - Review workflow tests proving unapproved drafts cannot enter canonical rules.
  - Automated queue tests covering retries, timeouts, and worker recovery.
  - Golden/broken reference IFC pair fixtures verifying architectural pass/fail counts.
- [ ] **Logging Improvements**:
  - Implement Request IDs (Correlation IDs) using `contextvars` to trace requests across the gateway and background tasks.
  - Transition from plain text logging to structured JSON logging for production log aggregators.
  - Elevate `RequestLoggingMiddleware` API request logs to `INFO` level.

---

## Appendix: Historical Milestone Archive

Key milestones completed in previous development cycles:

* **FastAPI API Gateway & Pure Svelte 5 SPA**: Migrated from FastHTML/MonsterUI to a pure FastAPI API Gateway (`app/api/`) and decoupled Vite + Svelte 5 SPA (`frontend/`), removing 14,500+ lines of legacy code.
* **Production Pipeline Separation**: Clean boundary between read-only audit analysis (`ArchAnalysisService`) and transactional model enhancement lineage (`SupabaseModelLineageRepository`).
* **Dependency Inversion**: Strict Pydantic contracts (`app/modules/contracts.py`), direct engine evaluator protocol implementation, and central container injection (`app/bootstrap.py`).
* **Dynamic Database-Driven Rules**: Architectural code rules (Part 9 Building Code) stored in Supabase PostgreSQL with runtime catalog reloading and relative property bounds.
* **LlamaIndex NLP & Document Parsing**: Table-aware layout chunking, clause metadata tagging, and structured rule extraction drafts (`rule_extraction_drafts`) with human review workflow before canonical promotion.
* **buildingSMART openBIM Standards**: Native `ifctester.ids` 1.0 XML export/import, live bSDD API client integration (`/api/bsdd/*`), and autocomplete components.
* **Digital Inspector Agent**: LangGraph state machine with 9 specialized tools for model querying, geometry extraction, compliance verification, and ISO 19650 CDE transitions.
* **Enterprise RBAC**: Multi-tenant organizations, groups, superadmin ruleset/project/document grant matrices, and Google OAuth integration.
* **DocLang Multimodal Pipeline**: Chunked storage offload, `.dclx` archive streaming, and multimodal image extraction.
* **Graph Database**: `GraphDatabaseProvider` and `Neo4jDatabaseProvider` integrated via application container.
