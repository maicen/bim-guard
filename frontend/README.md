# BIM Guard — Svelte Frontend Client

Decoupled Single-Page Application (SPA) client for BIM Guard, built with Svelte 5, Vite, TypeScript, and Tailwind CSS.

## Architecture

This frontend communicates with the FastAPI Gateway running at `http://127.0.0.1:8000/api` (proxied automatically in development via Vite).

- **REST API Integration**: `src/lib/api.ts` provides typed wrappers for Project CRUD, Rule management, and Analysis runners.
- **Server-Sent Events (SSE)**: `src/lib/sse.ts` connects to `/api/events/{project_id}` for real-time stage transitions (Validation -> IFC Parsing -> Engine Execution -> Risk Scoring -> Report Assembly -> Export) and live metrics without polling.
- **OpenBIM 3D Viewport**: `src/lib/components/IfcViewer.svelte` renders IFC models and BCF clash viewpoints.

## Getting Started

```bash
# 1. Install frontend dependencies
npm install

# 2. Start the development server (runs on http://localhost:5173 with proxy to backend)
npm run dev

# 3. Build for production
npm run build
```
