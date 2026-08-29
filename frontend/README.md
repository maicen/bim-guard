# BIM Guard — Svelte Frontend Client

Decoupled Single-Page Application (SPA) client for BIM Guard, built with **Svelte 5**, Vite, TypeScript, and Tailwind CSS.

## Architecture

This frontend communicates directly with the FastAPI Gateway running at `http://127.0.0.1:8000/api` (proxied automatically in development via Vite).

- **REST API Integration**: `src/lib/api.ts` provides typed wrappers for Project CRUD, Document ingestion, Rule library management, and Analysis execution.
- **Server-Sent Events (SSE)**: `src/lib/sse.ts` connects to `/api/events/{project_id}` for real-time stage transitions (Validation → IFC Parsing → Engine Execution → Risk Scoring → Report Assembly → Export) and live metrics without polling.
- **OpenBIM 3D Viewport**: `src/lib/components/IfcViewer.svelte` renders IFC models and BCF clash viewpoints using ThatOpenCompany / Web-IFC.
- **Pydantic Contract Parity**: All TypeScript interfaces in `src/lib/types.ts` mirror the Pydantic schemas in `app/modules/contracts.py`.

## Directory Structure

```text
frontend/
├── src/
│   ├── lib/
│   │   ├── api.ts              # Typed REST client calling /api endpoints
│   │   ├── sse.ts              # EventSource client for real-time progress streaming
│   │   ├── types.ts            # TypeScript interfaces matching backend Pydantic models
│   │   └── components/         # Reusable Svelte 5 components (IfcViewer, modals, charts)
│   ├── routes/                 # Single-page client route views
│   │   ├── DashboardView.svelte      # System overview, stats, recent activities
│   │   ├── ProjectsView.svelte       # Project management, file uploads, IFC metadata
│   │   ├── DocumentsView.svelte      # Document ingestion, PDF parsing, text extraction
│   │   ├── RulesView.svelte          # Rule library, folder management, rule authoring
│   │   ├── RuleExtractionView.svelte # LLM rule extraction workflow
│   │   ├── AnalyzeView.svelte        # Multi-engine compliance & corrosion analysis
│   │   ├── ArchAnalyzeView.svelte    # Architectural code compliance analysis
│   │   ├── ViewerView.svelte         # Fullscreen OpenBIM 3D viewer & clash inspection
│   │   ├── ReportsView.svelte        # BCF reports, PDF/Excel export downloads
│   │   ├── SettingsView.svelte       # System preferences & engine configurations
│   │   ├── WorkflowView.svelte       # End-to-end pipeline visualization
│   │   ├── UserManualView.svelte     # Embedded user guide
│   │   └── ModelingManualView.svelte # OpenBIM modeling standards guide
│   ├── App.svelte              # Main application shell & router
│   ├── app.css                 # Tailwind CSS & design tokens
│   └── main.ts                 # Svelte 5 bootstrap
├── package.json
└── vite.config.ts              # Vite dev server with /api proxy to FastAPI
```

## Working with Svelte 5

- **Runes**: Use modern Svelte 5 runes (`$state`, `$derived`, `$props`, `$effect`). Avoid legacy Svelte 3/4 stores or `export let`.
- **API calls**: Always use functions from `src/lib/api.ts`. Do not write raw `fetch()` calls in components.
- **Real-Time Progress**: Use `subscribeToEvents(projectId, onEvent, onError)` from `src/lib/sse.ts` to stream pipeline updates.

## Getting Started

```bash
# 1. Install frontend dependencies
npm install

# 2. Start the development server (runs on http://localhost:5173 with proxy to backend)
npm run dev

# 3. Typecheck and build for production
npm run build
```
