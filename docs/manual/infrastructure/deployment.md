# Deployment

BIM-Guard can be run two ways, depending on who's doing it and why.

## Running the stack locally (contributors)

To try the full stack — app, Supabase, Neo4j, Docling — on your own machine, with no
external accounts or domain needed, follow the
[Contributor Quickstart](https://github.com/maicen/bim-guard#contributor-quickstart-local-docker-no-external-accounts-needed)
in the README. See [Installing Docker](docker-installation.md) first if you don't
already have it.

## Production deployment

BIM-Guard's production instance is served at `https://bim-guard.xyz` using
**OrbStack/Docker Compose** with a **Cloudflare Tunnel** (`cloudflared`) — no inbound
ports are opened on the host. This is an internal deployment: it requires Cloudflare
Zero Trust tunnel credentials and the `bim-guard.xyz` domain, which external
contributors don't have and don't need for local development.

The full setup — tunnel configuration, Google OAuth branding, environment variables,
and troubleshooting — is documented in
[`docs/deployment_orbstack_cloudflare.md`](https://github.com/maicen/bim-guard/blob/main/docs/deployment_orbstack_cloudflare.md)
in the repository, and in `CLAUDE.md`'s "Production Serving" section. Releases are cut
by pushing to `main`, which the self-hosted GitHub Actions runner (`~/actions-runner`)
picks up to redeploy (`.github/workflows/deploy.yml`); database migrations are applied
separately via `scripts/migrate_production.py --apply` (`.github/workflows/migrate_production.yml`
can also trigger this).

A third option, `render.yaml` at the repository root, documents deploying on
[Render](https://render.com) instead of self-hosted Docker — kept for reference but not
the platform in active use.
