# Environment Setup

BIM-Guard is a two-part stack: a **FastAPI backend** and a **Svelte frontend**, backed by **Supabase** (Postgres + Auth).

There are two ways to run it locally — pick whichever fits:

- **Docker Compose** (recommended for first-time contributors): one stack, including
  a local Supabase, Neo4j, and Docling, no external accounts needed. See the
  [Contributor Quickstart](https://github.com/maicen/bim-guard#contributor-quickstart-local-docker-no-external-accounts-needed)
  in the README, and [Installing Docker](docker-installation.md) if you don't have it yet.
- **Native (`uv` + `npm`)**: faster iteration (hot reload, no rebuild step), described below.

## Prerequisites (native path)

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- Node.js and `npm`
- A Supabase project (URL + anon key) — either the self-hosted Docker stack's
  local instance, or a project of your own (see `example.env`)

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

Schema changes are applied via SQL files in `supabase/migrations/`. See `CLAUDE.md` for the full migration workflow — this is a developer/admin operation, not something end users perform. If you're running the self-hosted Docker stack on a fresh database, you must apply them once with `uv run python scripts/migrate_production.py --apply` (unlike `supabase start`, the Docker stack doesn't apply migrations automatically).

## Optional: local LLM models via Ollama

If you have [Ollama](https://ollama.com) installed, BIM-Guard can use its locally-hosted
models for rule extraction and the agent, in addition to OpenRouter/OpenAI/Gemini/Anthropic.
This is entirely optional — if Ollama isn't installed, nothing else is affected.

- **Native path** (`uv run uvicorn` on your own machine): the default `OLLAMA_API_BASE=http://localhost:11434`
  in `example.env` already reaches Ollama running on the same machine.
- **Docker path** (`docker compose up`, locally or in production): leave `OLLAMA_API_BASE`
  unset — the container already defaults to `http://host.docker.internal:11434`, which reaches
  Ollama running on whichever machine hosts the Docker stack.
