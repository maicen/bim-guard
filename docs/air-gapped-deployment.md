# Air-gapped / fully offline deployment

BIM Guard can run on a network with no route to the public internet. Two switches
do it; both default to off, so the hosted bim-guard.xyz deployment is unchanged.

| Switch | Where | What it does |
| --- | --- | --- |
| `VENDOR_VIEWER=true` | build arg / `.env` (read by `docker compose build`) | Bundles the 3D viewer's engine, WASM, worker and icons into the image instead of loading them from `esm.sh`, `unpkg.com` and `api.iconify.design` at runtime. Needs internet **at build time only**. |
| `BIMGUARD_OFFLINE=true` | runtime env (`.env`) | bSDD lookups read only the bundled DuckDB ontology (`data/reference/bsdd`, ~16k classes) plus the runtime cache, with no live buildingSMART calls. Also allows LLM provider URLs on private networks. |

## Steps

1. **On a connected machine**, build and export everything:
   ```bash
   VENDOR_VIEWER=true docker compose build
   docker compose pull            # Supabase, Neo4j, Docling, OpenCDE images
   docker save $(docker compose config --images) | gzip > bim-guard-images.tar.gz
   ```
   Pull your Ollama models here too (`ollama pull <model>`) and copy `~/.ollama/models`.
2. **Move** the archive (and the model files) to the isolated network, then `docker load`.
3. **Configure** `.env` on the isolated host: `BIMGUARD_OFFLINE=true`, no `TUNNEL_TOKEN` /
   `COMPOSE_PROFILES=tunnel`, and `OLLAMA_API_BASE` pointing at your model server.
4. `docker compose up -d` (no `--build`).

## Language models

* **Ollama**: pick *Ollama (self-hosted)* as the provider; the address comes from
  `OLLAMA_API_BASE` (default `http://host.docker.internal:11434`).
* **Any OpenAI-compatible server** (vLLM, llama.cpp, LM Studio, ...): add an *OpenAI*
  provider instance whose base URL is the server (for example `http://10.0.0.5:8000/v1`).
  The form requires a key; enter any placeholder if the server does not check one.
  Models from a custom base URL are routed with LiteLLM's `openai/` prefix automatically.
  Private addresses are accepted only when `BIMGUARD_OFFLINE=true` or
  `BIMGUARD_ALLOW_PRIVATE_LLM_HOSTS=true` is set by the operator. Link-local and cloud
  metadata addresses stay blocked either way.
* IFC compliance checks themselves never call a language model.

## What is and is not verified

Verified: a vendored viewer build loads and renders an IFC in a browser with every
request served from the app's own origin (WASM, fragments worker and icon data
included); the `vendor_viewer.mjs` build runs inside `node:22-slim`; bSDD makes no HTTP
call with `BIMGUARD_OFFLINE=true` (unit test); private-network LLM base URLs are accepted
only with the operator flag (unit test).

Not verified: a complete install behind a firewall that drops all outbound traffic. In
particular, check these on your own network:

* Google sign-in needs internet; use email/password sign-in.
* `docling-serve` model weights must already be in the image or volume you load.
* The Cloudflare Tunnel profile must stay off.
* Rule-extraction quality depends on the local model you choose.

## Updating the bSDD reference data

While connected, refresh the bundled ontology with `scripts/crawl_bsdd_ontology.py`, then
carry the updated `data/reference/bsdd/bsdd_ontology.duckdb` into the isolated network.
