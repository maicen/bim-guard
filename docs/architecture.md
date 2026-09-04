# BIMGUARD AI — System Architecture

| | |
| --- | --- |
| **Document** | `docs/architecture.md` |
| **Version** | 2.0 (Decoupled Production Architecture) |
| **Status** | Active — FastAPI Gateway & Svelte 5 SPA |
| **Scope** | FastAPI API Gateway, Svelte 5 SPA, Pydantic contracts, SSE streaming, compute engines, database-driven rules |
| **Owner** | Group 5 — Masters in BIM Management, Zigurat Global Institute of Technology |

> Note: BIM-Guard operates on a modern, decoupled architecture: a **FastAPI API Gateway** (`app/api/`) providing strict Pydantic REST contracts and real-time Server-Sent Events (SSE) tracking, and a **standalone Vite + Svelte 5 Single-Page Application (SPA)** client (`frontend/`).

---

## 1. Purpose and Scope

This document describes how the BIMGUARD AI application is architected across its decoupled layers:
1. **Backend API Gateway (FastAPI)**: Serves typed REST endpoints and real-time Server-Sent Events (SSE) from `/api` with strict Pydantic request/response validation (`app/modules/contracts.py`).
2. **Frontend Client (Svelte 5 SPA)**: Reactive client under `frontend/` powered by Vite, TypeScript, and Tailwind CSS, communicating exclusively with `/api`.
3. **Compute Kernels & Pipelines**: Framework-agnostic Python compliance and physics engines (corrosion GC-001/CC-001/MC-001, architectural egress & spatial daylighting) and orchestrator (`app/engines/`, `app/modules/`, `app/services/`) driven dynamically by database-stored rules.
4. **Data & Storage Layer**: Supabase Postgres for relational state and Supabase Object Storage for IFC models, extracted documents, and generated BCF issue archives.

## 2. Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│               Frontend Client (frontend/)                  │
│       Vite + Svelte 5 SPA, TypeScript, Tailwind CSS         │
│                                                             │
│  - ProjectsView & Wizard Modal    - Analyze & Arch Views    │
│  - 3D OpenBIM Viewer (Web-IFC)    - Rule Extraction View    │
│  - Live SSE Progress Widget       - Revit Direct Sync View  │
└──────────────────────────────┬──────────────────────────────┘
                               │
               HTTP REST & SSE │ (/api/*)
                               │
┌──────────────────────────────▼──────────────────────────────┐
│             FastAPI API Gateway (app/api/)                  │
│                                                             │
│  - /api/projects    - /api/rules        - /api/analyze      │
│  - /api/documents   - /api/settings     - /api/events       │
│  - /api/dashboard   - /api/health       - /api/docs (OpenAPI)│
│  - /api/cde         - /api/bcf/v2.1     - /api/bsdd         │
│  - /api/projects/{id}/inspect (Digital Inspector agent)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
       Typed Contracts & Data  │ (app/modules/contracts.py)
                               │
┌──────────────────────────────▼──────────────────────────────┐
│               Domain Services (app/services/)               │
│                                                             │
│  - ProjectsService          - DocumentService               │
│  - RuleService & Seeder     - ObjectStorage (Supabase)      │
│  - CorrosionRuleCatalog     - PipelineTracker (SSE events)  │
│  - ModelLineageRepository   - AnalysisRunner                │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐┌─────────────────────────────┐
│  Compute Engines & Modules   ││  Database & Object Storage  │
│                              ││                             │
│ - GC-001 Galvanic Engine     ││ - Supabase Postgres         │
│ - CC-001 Crevice Engine      ││   (projects, rules, audit)  │
│ - MC-001 Microbiological     ││ - Supabase Storage          │
│ - ARCH-EGRESS-001 Egress     ││   (models, reports, BCF)    │
│ - ARCH-SPATIAL-001 Daylight  ││ - SQLite / Fastlite Cache   │
│ - Phase 6 Orchestrator       ││                             │
│ - Blue Halo Material Graph   ││                             │
└──────────────────────────────┘└─────────────────────────────┘
```

## 3. Runtime Stack

| Layer | Technology | Role |
| --- | --- | --- |
| **Backend API Gateway** | **FastAPI** (Python 3.12) | REST endpoints at `/api`, OpenAPI docs at `/api/docs`, Pydantic validation, dependency injection |
| **Real-Time Streaming** | **Server-Sent Events (SSE)** | Live pipeline tracking (`/api/events/{project_id}`) via `PipelineTracker` |
| **Data Contracts** | **Pydantic v2** | Strict schemas in `app/modules/contracts.py` mirrored in `frontend/src/lib/types.ts` |
| **Frontend SPA Client** | **Svelte 5** + **Vite** + **TypeScript** | Decoupled client under `frontend/`, modern runes syntax (`$state`, `$derived`, `$props`) |
| **Frontend Styling** | **Tailwind CSS** | Design tokens, responsive components, dark theme |
| **3D Viewport** | **ThatOpenCompany / Web-IFC** | Client-side IFC geometry parsing and 3D rendering |
| **Database & Storage** | **Supabase (Postgres & Storage)** | Primary persistence for projects, documents, and rules; S3-compatible object storage |
| **Compute Engines** | **Pure Python** | `bimguard_galvanic_engine`, `bimguard_crevice_engine`, `bimguard_mic_engine`, `bimguard_arch_engine`, `orchestrator` |
| **Rule System** | **Database-Driven Catalog** | Rules, thresholds, scoring weights, and mitigations loaded dynamically via `RuleService`; zero rule content is hardcoded in Python |
| **Rule Extraction** | **LlamaIndex (LLM-only)** | `LlamaIndexRuleGenerator` — typed Pydantic program producing schema-validated rule drafts from any ingested document, gated by an approve/reject review workflow |
| **Agentic Orchestration** | **LangGraph** | `app/digital_inspector/` — a ReAct-style agent coordinating IFC queries, bSDD lookups, and validation engines; separate from the general-purpose `app/agent/` coding assistant |

### 3.1 Essential Development Commands

```bash
# Backend dependencies and server
uv sync
uv run uvicorn main:app --reload

# Backend linting and testing
uv run ruff check .
uv run pytest tests/

# Frontend dependencies and dev server
cd frontend && npm install
npm run dev

# Frontend production build
npm run build

# Single-command dev stack
./run_server.sh         # macOS/Linux
run_server.bat          # Windows
```

## 4. Repository Layout

```text
bim-guard/
├── app/
│   ├── api/             # FastAPI routers (/projects, /rules, /analyze, /events, etc.)
│   ├── main.py          # App bootstrap, FastAPI API Gateway, and SPA static mount
│   ├── services/        # Persistence, runner, tracker, and extraction services
│   ├── modules/         # Compliance pipeline stages & Pydantic data contracts
│   ├── engines/         # Corrosion & architectural physics engines (GC-001, CC-001, MC-001, ARCH)
│   ├── digital_inspector/ # LangGraph Digital Inspector agent (IFC/bSDD/validation tool calls)
│   ├── agent/           # General-purpose OpenRouter coding assistant (separate from the above)
│   ├── environment.py   # Environment variable loader
│   ├── logging_config.py# Structured logging setup
│   └── utils.py         # Utility helpers (UTC timestamps, file hashing)
├── frontend/            # Standalone Vite + Svelte 5 Single-Page App (SPA)
│   ├── src/
│   │   ├── lib/         # Typed API client, SSE subscriber, Svelte 5 components
│   │   │   ├── api.ts   # Typed client communicating with /api
│   │   │   ├── sse.ts   # EventSource subscriber for /api/events/{project_id}
│   │   │   ├── types.ts # TypeScript interfaces mirroring Pydantic contracts
│   │   │   └── components/ # IfcViewer, modals, tables, stats, progress widgets
│   │   └── routes/      # Svelte 5 views (Dashboard, Projects, Analyze, Rules, etc.)
│   ├── package.json     # Frontend dependencies (Svelte 5, Tailwind CSS)
│   └── vite.config.ts   # Dev server with /api proxy to FastAPI
├── data/                # Local runtime data, cache, and seed rule sets
├── docs/                # Architectural docs, validation reports, and planning
├── scripts/             # Evaluation, build, benchmark, and utility scripts
├── tests/               # Pytest test suites for the backend
└── static/              # CSS, JS, and viewer assets
```

## 5. Request & Event Lifecycle

### 5.1 REST Request Lifecycle
1. The Svelte SPA issues a typed request via `frontend/src/lib/api.ts`.
2. In development, Vite proxies `/api` calls to `http://127.0.0.1:8000`. In production, FastAPI directly routes `/api` calls to the relevant router in `app/api/`.
3. The FastAPI router validates payloads against Pydantic models in `app/modules/contracts.py`.
4. The router uses dependency injection (`Depends(...)`) to invoke domain services (`app/services/`).
5. Domain services execute pure Python physics engines and persist state via `PersistenceService` or `ObjectStorage`.
6. Responses are returned as typed JSON matching the contract schema.

### 5.2 Server-Sent Events (SSE) Streaming Lifecycle
1. When an analysis starts, the client connects to `/api/events/{project_id}` via `subscribeToEvents()` in `frontend/src/lib/sse.ts`.
2. The orchestrator emits stage progression events (`init`, `parsing`, `engine_run`, `scoring`, `reporting`, `complete`).
3. `PipelineTracker` broadcasts each event to active SSE subscriber queues in real time.
4. The Svelte UI updates state reactively (progress meters, status chips, stage indicators) without polling loops.

## 6. Evaluator Contracts & Dependency Inversion

BIM-Guard enforces strict Dependency Inversion across engines, repositories, and services for both MEP/corrosion and architectural domains:

### 6.1 Direct RuleEvaluator Protocol Implementation
- Both MEP physics engines (`GalvanicCorrosionEngine`, `CreviceCorrosionEngine`, `MICEngine`) and architectural engines (`EgressAnalysisEngine`, `SpatialDaylightEngine`) implement the `RuleEvaluator` protocol directly rather than relying on legacy `CallableRuleEvaluator` wrappers.
- Evaluators consume typed `RuleEvaluationRequest` (or coerced elements) and return structured `RuleEvaluationResult` models defined in `app/modules/contracts.py`.
- Results support dictionary-style mapping semantics for full backwards compatibility while providing strictly typed attribute access (`band`, `score`, `details`, `element_id`, `status`).

### 6.2 Evaluator Scope Boundary: Custom Python vs. buildingSMART IDS
- **Custom Python Evaluators**: Strictly limited to evaluations that declarative buildingSMART Information Delivery Specification (IDS) cannot express:
  - Multiphysics calculations (galvanic voltage gaps, anodic/cathodic area ratios, PREN adequacy).
  - Joint crevice geometries and critical crevice temperatures (CCT).
  - Microbiological growth kinetics, flow velocity classes, and topological dead-leg length-to-diameter ratios.
  - NetworkX topological space-connectivity graph traversal (habitable space to exterior exit shortest paths via `IfcRelSpaceBoundary`).
  - Spatial boundary daylight calculations (window glazing area vs. room floor area).
  - Spatial, topological, and geometric proximity calculations.
- **Database Rules & IDS Validation**: Standard alphanumeric assertions, property set existence, data types, unit checks, and scalar property thresholds are executed via database-driven rules and IDS schemas.
- **Database-Driven Rule Thresholds**: Engineering cutoffs are never hardcoded in Python engines. Egress travel limits (`CODE 9.9.10.1`), exit counts (`CODE 9.9.4.1`), daylight ratios (`CODE 9.7.2.3`), and fire separation ratings (`CODE 9.10.9.14`) are dynamically read from `RuleService` (`BUILDING-CODE-PART9`).

### 6.3 Centralized Application Bootstrap Container
- All repository construction, object storage adapters, and service wiring are consolidated in `app/bootstrap.py` via `ApplicationContainer`.
- Domain services (`ProjectsService`, `DocumentService`, `RuleService`, `SettingsService`, `AnalysisService`, `ArchAnalysisService`) receive their persistence and storage dependencies via constructor injection, eliminating hardcoded internal construction of Supabase adapters and enabling seamless in-memory and mock testing.
- FastAPI dependency providers in `app/api/dependencies.py` resolve singleton services directly from the container.

## 7. Rule Extraction & Agentic Layer

Rule content — for any building code, standard, or client-supplied specification —
never lives in Python. It is either seeded as database static assets or produced
by an LLM extraction pipeline from an uploaded document; the compliance engines
in §6 only ever read rules through `RuleService`.

### 7.1 LLM-Only Rule Extraction (`app/services/rule_extraction_service.py`)
- A single extraction path: `LlamaIndexIngestor` ingests an uploaded document into
  table/layout-aware, clause-scoped nodes (`DocumentNodeContract`, with clause ID,
  page number, and parent section metadata for traceability into generated BCF
  issues), then `LlamaIndexRuleGenerator` runs a typed LlamaIndex Pydantic program
  per node to produce zero or more schema-validated rule drafts.
- A malformed LLM response fails Pydantic validation rather than being silently
  coerced. Drafts persist as `pending_review` rows (`rule_extraction_drafts`
  table) with an approve/reject/edit workflow (`RuleDraftService`) before
  promotion into the canonical `public.rules` table — nothing an LLM extracts is
  trusted into the audit path unreviewed.
- Callers (API routes, the Digital Inspector agent) depend on the
  `RuleExtractionProvider` protocol, not on `LlamaIndexRuleGenerator` directly, so
  the extraction algorithm can change without touching callers.

### 7.2 Digital Inspector Agent (`app/digital_inspector/`)
- A LangGraph state machine (`create_react_agent`) coordinating cyclical
  multi-tool execution: querying IFC models, checking the database cache,
  dispatching buildingSMART Data Dictionary (bSDD) lookups, extracting rules from
  documents, and checking ISO 19650 CDE state transitions — exposed via
  `POST /api/projects/{id}/inspect`.
- `app/digital_inspector/cde_graph.py` wraps the existing, already-tested
  `CDEStateMachine.evaluate_transition()` as an agent tool
  (`check_cde_transition`); the real transactional `transition_project()` write
  path is untouched by the agent.
- Separate from the general-purpose `app/agent/` OpenRouter coding assistant,
  which is a developer tool, not part of the compliance audit path.

### 7.3 buildingSMART Data Dictionary (bSDD) Integration
- `app/api/bsdd.py` exposes `BSDDClient` (dictionaries, class search, class
  lookup, property search) at `/api/bsdd/*`, standardizing terminology and
  classification codes (Uniclass, CCI, etc.) referenced by projects and rules.
- `projects.classification_standard` stores a project's chosen bSDD dictionary
  code; `BsddAutocomplete.svelte` backs Target IFC Class and Property Name
  fields in the rule editor with live bSDD-sourced suggestions.
