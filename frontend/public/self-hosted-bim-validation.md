# Self-hosted, on-premises BIM validation with local LLMs

> Run BIM Guard on your own infrastructure with Docker Compose and point its language-model features at a local Ollama server.

BIM Guard runs as a Docker Compose stack that you host yourself: the application, its database and authentication, a graph store and the document parser all run on your own servers. IFC compliance checks are computed by deterministic Python engines, so model geometry never has to reach a language model. Where a language model is used, you can point it at a local Ollama server instead of a hosted API.

## What runs on your own infrastructure

The bundled `docker-compose.yml` starts every service the platform needs:

- **Application** - the web app and the API gateway.
- **Database, authentication and file storage** - a self-hosted Supabase stack (PostgreSQL, Auth and Storage).
- **Graph store** - a self-hosted Neo4j server for topological queries.
- **Document parsing** - a self-hosted Docling server that reads regulatory PDFs.
- **OpenCDE Documents API** - the buildingSMART document exchange service.

A Cloudflare Tunnel is an optional compose profile for publishing an instance on the internet. An internal deployment does not need it.

## IFC checks do not call a language model

Compliance engines for egress, spatial clearance, doors and stairs are plain Python. They read IFC models with IfcOpenShell and take their thresholds from rules stored in your own database. An audit of an IFC model therefore runs without any language model or external AI service.

## Local LLMs with Ollama

Language models are used for the document side of the workflow, such as extracting draft rules from regulatory PDFs. Extracted rules arrive as drafts for a reviewer to approve or edit.

- Choose **Ollama (self-hosted)** as the provider for an organisation. Available models are listed from your own Ollama server.
- The server address comes from `OLLAMA_API_BASE`. The bundled compose file defaults it to an Ollama server on the Docker host (`host.docker.internal:11434`).
- Hosted providers (Anthropic, Gemini, OpenAI, OpenRouter) remain optional per organisation. Leave them unconfigured to keep every request inside your network.

## Deploy it

- Clone the [source repository](https://github.com/maicen/bim-guard) and copy the example environment file to `.env`.
- Start the stack with `docker compose up -d --build`.
- Install Ollama on the host, pull a model, and add an Ollama provider in the application settings.
- Sign in with email and password, or configure Google sign-in.

The full operator guide is [docs/deployment_orbstack_cloudflare.md](https://github.com/maicen/bim-guard/blob/main/docs/deployment_orbstack_cloudflare.md) in the repository.

## What is not claimed

BIM Guard is not certified for, or tested in, a fully air-gapped network. By default the 3D viewer loads its libraries from public CDNs, and buildingSMART Data Dictionary lookups call the buildingSMART service (results are cached). A fully disconnected site would have to mirror or block those requests itself.

Rule-extraction quality depends on the model you run. The [published evaluation](/research) does not cover every local model, so review extracted rules before relying on them.

## Related

[All features](/features) · [Automated IFC compliance checking](/ifc-compliance-checking) · [Validation and research](/research) · [Documentation](/docs)

Canonical page: https://bim-guard.xyz/self-hosted-bim-validation
