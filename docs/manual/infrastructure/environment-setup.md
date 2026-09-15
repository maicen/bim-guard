# Environment Setup

BIM-Guard is a two-part stack: a **FastAPI backend** and a **Svelte frontend**, backed by **Supabase** (Postgres + Auth).

## Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- Node.js and `npm`
- A Supabase project (URL + anon key)

## Backend

```bash
uv sync
uv run uvicorn main:app --reload
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Copy `frontend/.env.example` to `frontend/.env` and fill in:

- `VITE_SUPABASE_URL` — your Supabase project URL
- `VITE_SUPABASE_ANON_KEY` — your Supabase anon/publishable key

## Running both at once

```bash
./run_server.sh      # macOS/Linux
run_server.bat        # Windows
```

## Production stack

```bash
./run_production_server.sh   # macOS/Linux
run_production_server.bat    # Windows
```

This builds the Svelte SPA and serves it from FastAPI with a multi-worker `uvicorn` process.

## Database migrations

Schema changes are applied via SQL files in `supabase/migrations/`. See `CLAUDE.md` for the full migration workflow — this is a developer/admin operation, not something end users perform.
