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
3. **Compute Kernels & Pipelines**: Framework-agnostic Python physics engines (GC-001 galvanic, CC-001 crevice, MC-001 microbiological) and compliance orchestrator (`app/engines/`, `app/modules/`, `app/services/`) driven dynamically by database-stored rules.
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
│ - Phase 6 Orchestrator       ││   (models, reports, BCF)    │
│ - Blue Halo Material Graph   ││ - SQLite / Fastlite Cache   │
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
| **Compute Engines** | **Pure Python** | `bimguard_corrosion_engine`, `bimguard_crevice_engine`, `bimguard_mic_engine`, `orchestrator` |
| **Rule System** | **Database-Driven Catalog** | Rules, thresholds, scoring weights, and mitigations loaded dynamically via `RuleService` |

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
│   ├── engines/         # Corrosion physics engines (GC-001, CC-001, MC-001)
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
