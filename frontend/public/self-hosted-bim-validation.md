# Air-gapped and self-hosted BIM validation with local LLMs

> Run BIM Guard on your own servers or an air-gapped network: local Ollama or OpenAI-compatible models, offline bSDD, a bundled 3D viewer.

BIM Guard runs as a Docker Compose stack that you host yourself, including on a network with no route to the internet. The application, its database and authentication, a graph store and the document parser all run on your own servers. IFC compliance checks are computed by deterministic Python engines, so model geometry never has to reach a language model, and where a model is used it can be a local Ollama or OpenAI-compatible server instead of a hosted API.

## What runs on your own infrastructure

The bundled `docker-compose.yml` starts every service the platform needs:

- **Application** - the web app and the API gateway.
- **Database, authentication and file storage** - a self-hosted Supabase stack (PostgreSQL, Auth and Storage).
- **Graph store** - a self-hosted Neo4j server for topological queries.
- **Document parsing** - a self-hosted Docling server that reads regulatory PDFs.
- **OpenCDE Documents API** - the buildingSMART document exchange service.

A Cloudflare Tunnel is an optional compose profile for publishing an instance on the internet. An internal or air-gapped deployment leaves it off.

## IFC checks do not call a language model

Compliance engines for egress, spatial clearance, doors and stairs are plain Python. They read IFC models with IfcOpenShell and take their thresholds from rules stored in your own database. An audit of an IFC model therefore runs without any language model or external AI service.

## Local LLMs: Ollama or any OpenAI-compatible server

Language models are used for the document side of the workflow, such as extracting draft rules from regulatory PDFs. Extracted rules arrive as drafts for a reviewer to approve or edit. You choose where the model runs:

- **Ollama (self-hosted)** - pick it as the provider for an organisation. Available models are listed from your own server, whose address comes from `OLLAMA_API_BASE` (the bundled compose file defaults it to an Ollama server on the Docker host).
- **OpenAI-compatible servers** - vLLM, llama.cpp, LM Studio or any server that speaks the OpenAI API, addressed by its base URL on your network. The operator opts in to private-network addresses with an environment setting (`BIMGUARD_ALLOW_PRIVATE_LLM_HOSTS`, or `BIMGUARD_OFFLINE`); cloud-metadata and link-local addresses stay blocked.
- Hosted providers (Anthropic, Gemini, OpenAI, OpenRouter) remain optional per organisation. Leave them unconfigured to keep every request inside your network.

## Air-gapped mode

Two switches remove the remaining dependencies on public services. Both are off by default.

- `BIMGUARD_OFFLINE=true` - buildingSMART Data Dictionary lookups are answered from the bundled local ontology (over 16,000 classes) and the runtime cache, with no live requests to buildingSMART.
- `VENDOR_VIEWER=true` at image build time - the 3D viewer's engine, IFC WASM, worker and icons are bundled into the image instead of being fetched from public CDNs. Building needs internet once; the running container does not.
- Images and local models are pulled on a connected machine and carried across with `docker save` and `docker load`.

## Deploy it

- Clone the [source repository](https://github.com/maicen/bim-guard) and copy the example environment file to `.env`.
- Start the stack with `docker compose up -d --build`.
- Install Ollama (or another OpenAI-compatible server), pull a model, and add the provider in the application settings.
- Sign in with email and password.

The operator guides are [docs/air-gapped-deployment.md](https://github.com/maicen/bim-guard/blob/main/docs/air-gapped-deployment.md) and [docs/deployment_orbstack_cloudflare.md](https://github.com/maicen/bim-guard/blob/main/docs/deployment_orbstack_cloudflare.md) in the repository.

## What is not claimed

BIM Guard is not certified for air-gapped use. The viewer build was checked in a browser loading an IFC with every request served by the application itself, but a complete installation behind a firewall that drops all outbound traffic has not been audited end to end. Google sign-in needs the internet, so an isolated network uses email and password sign-in.

Rule-extraction quality depends on the model you run. The [published evaluation](/research) does not cover every local model, so review extracted rules before relying on them.

## Related

[All features](/features) · [Automated IFC compliance checking](/ifc-compliance-checking) · [Validation and research](/research) · [Documentation](/docs)

Canonical page: https://bim-guard.xyz/self-hosted-bim-validation
