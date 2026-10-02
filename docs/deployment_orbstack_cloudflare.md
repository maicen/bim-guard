# Serving BIM Guard at https://bim-guard.xyz via OrbStack & Cloudflare Tunnel

This guide explains how to deploy, serve, and operate **BIM Guard** in production at **`https://bim-guard.xyz`** using **OrbStack / Docker Compose** and **Cloudflare Tunnel (`cloudflared`)** with automatic SSL/TLS termination, DDoS mitigation, Supabase OAuth authentication, and SEO optimization.

---

## 1. Architectural Overview

```text
  Internet Client (Browser / Search Engine / BCF Tool)
                         │
                         │ HTTPS (https://bim-guard.xyz)
                         ▼
             Cloudflare Edge Network
   (SSL/TLS 1.3 Termination, DDoS Mitigation, DNS Routing)
                         │
                         │ Encrypted Outbound QUIC/HTTP2 Tunnel (No open router ports)
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ macOS / Server Runtime (OrbStack Docker Engine)                         │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ bim-guard-cloudflared container                                 │   │
│   │ (Proxies traffic into the internal Docker compose network)      │   │
│   └─────────────────┬───────────────────────────────┬───────────────┘   │
│                     │ HTTP (bim-guard:8000)         │ HTTP (kong:8000)  │
│                     ▼                               ▼                   │
│   ┌─────────────────────────────────┐   ┌───────────────────────────┐   │
│   │ bim-guard-app container         │   │ supabase-kong Gateway     │   │
│   │  - Svelte 5 SPA (frontend/dist) │   │  - Auth: /auth/v1         │   │
│   │  - FastAPI Gateway (port 8000)  │   │  - REST: /rest/v1         │   │
│   │  - REST APIs, SSE Events        │   │  - Storage: /storage/v1   │   │
│   └─┬──────────────┬──────────────┬─┘   └─┬──────┬──────┬──────┬────┘   │
│     │ Bolt (7687)  │ HTTP (5001)  │       │      │      │      │        │
│     ▼              ▼              ▼       ▼      ▼      ▼      ▼        │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────┐ ┌────┐ ┌─────┐ ┌──────┐   │
│ │bim-guard-│ │bim-guard-│ │bim-guard-│ │auth│ │rest│ │store│ │studio│   │
│ │neo4j     │ │docling   │ │opencde   │ └─┬──┘ └─┬──┘ └──┬──┘ └──┬───┘   │
│ └──────────┘ └──────────┘ └──────────┘   │      │       │       │       │
│                                          ▼      ▼       ▼       ▼       │
│                                       ┌─────────────────────────────┐   │
│                                       │ supabase-db (PostgreSQL 17) │   │
│                                       └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Docker Compose Stack & Services (`docker-compose.yml`)

The platform is orchestrated as a fully integrated multi-container stack:

1. **`bim-guard` (`bim-guard-app`)**:
   - Built via the multi-stage [`Dockerfile`](../Dockerfile) (Node 22 Svelte 5 builder &rarr; Python 3.12 Astral uv virtualenv &rarr; Debian Bookworm runtime with OpenCASCADE/IfcOpenShell bindings).
   - Serves the compiled Svelte 5 SPA at `/` and the FastAPI API gateway at `/api`.
   - Listens on internal port `8000` (mapped to `${PORT:-8000}`).
   - Healthcheck monitors `http://localhost:8000/api/health`.
2. **Self-Hosted Supabase Stack (`docker/supabase/docker-compose.yml`)**:
   - Included directly in the root `docker-compose.yml` via Compose `include:`.
   - **`supabase-db`**: PostgreSQL 17 database (`supabase/postgres:17.6.1.111`) with `pgcrypto`, `vector`, `uuid-ossp`, and RLS triggers. Listens on host port `54322`.
   - **`supabase-kong`**: Unified API gateway routing `/auth/v1`, `/rest/v1`, and `/storage/v1`. Listens on host port `54321` and internal port `8000`.
   - **`supabase-auth`**: GoTrue authentication server supporting symmetric HS256 JWTs, password logins, and Google OAuth SSO.
   - **`supabase-rest`**: PostgREST auto-generated REST API on internal port `3000`.
   - **`supabase-storage`**: Supabase Storage engine managing file uploads and downloads.
   - **`supabase-meta`**: Postgres introspection daemon for Studio.
   - **`supabase-studio`**: Supabase Dashboard UI for live database and storage inspection on host port `54323`.
3. **`neo4j` (`bim-guard-neo4j`)**:
   - Neo4j 5.26 Community Edition graph database.
   - Listens on `7474` (HTTP / Neo4j Browser) and `7687` (Bolt binary protocol).
   - Starts by default; healthy dependency for `bim-guard`.
4. **`docling-serve` (`bim-guard-docling`)**:
   - Self-hosted CPU Docling REST parsing engine (`quay.io/docling-project/docling-serve-cpu:latest`).
   - Listens on port `5001`.
   - Starts by default; healthy dependency for `bim-guard`.
5. **`opencde` (`bim-guard-opencde`)**:
   - buildingSMART OpenCDE Documents API on port `8081`.
   - Verifies caller bearer tokens against BIM Guard's own Supabase JWKS for seamless single sign-on.
6. **`cloudflared` (`bim-guard-cloudflared`)**:
   - Official Cloudflare connector (`cloudflare/cloudflared:latest`) running under compose profile `tunnel`.
   - Establishes persistent outbound tunnels to Cloudflare Edge using `TUNNEL_TOKEN`. Python 3.12 Astral uv virtualenv &rarr; Debian Bookworm runtime with OpenCASCADE/IfcOpenShell bindings).
   - Serves the compiled Svelte 5 SPA at `/` and the FastAPI API gateway at `/api`.
   - Listens on internal port `8000` (mapped to `${PORT:-8000}`).
   - Healthcheck monitors `http://localhost:8000/api/health`.
2. **`neo4j` (`bim-guard-neo4j`)**:
   - Neo4j 5.26 Community Edition graph database.
   - Listens on `7474` (HTTP / Neo4j Browser) and `7687` (Bolt binary protocol).
   - Starts by default; healthy dependency for `bim-guard`.
3. **`docling-serve` (`bim-guard-docling`)**:
   - Self-hosted CPU Docling REST parsing engine (`quay.io/docling-project/docling-serve-cpu:latest`).
   - Listens on port `5001`.
   - Starts by default; healthy dependency for `bim-guard`.
4. **`opencde` (`bim-guard-opencde`)**:
   - buildingSMART OpenCDE Documents API on port `8081`.
   - Verifies caller bearer tokens against BIM Guard's own Supabase JWKS for seamless single sign-on.
5. **`cloudflared` (`bim-guard-cloudflared`)**:
   - Official Cloudflare connector (`cloudflare/cloudflared:latest`) running under compose profile `tunnel`.
   - Establishes persistent outbound tunnels to Cloudflare Edge using `TUNNEL_TOKEN`.

---

## 3. Deployment Setup: All-in-One Compose (Recommended)

In this setup, `cloudflared` runs as a container inside OrbStack. No host-level certificates or CLI logins on macOS are required.

### Step 1: Create Tunnel in Cloudflare Zero Trust

1. Navigate to the [Cloudflare Zero Trust Tunnels Dashboard](https://one.dash.cloudflare.com/a7ed8378cd620788b8f508e8b5d15975/networks/tunnels).
2. Click **Add a tunnel** &rarr; select **Cloudflared** connector &rarr; click **Next**.
3. Name your tunnel: `bim-guard`.
4. On the **Install connector** screen:
   - Select **Docker**.
   - Copy the token string following `--token` (e.g. `eyJh...`). This is your `TUNNEL_TOKEN`.
5. Click **Next** to access the **Public Hostnames** tab.
6. Add the public routing rules:
   - **Primary App Route**:
     - **Subdomain**: Leave blank (for apex `bim-guard.xyz`) or specify `app` / `www`.
     - **Domain**: `bim-guard.xyz`
     - **Type**: `HTTP`
     - **URL**: `bim-guard:8000` *(resolves to the `bim-guard` service inside the compose bridge network)*.
   - **Supabase API Gateway Route**:
     - **Subdomain**: `supabase`
     - **Domain**: `bim-guard.xyz`
     - **Type**: `HTTP`
     - **URL**: `kong:8000` *(resolves to the `supabase-kong` gateway inside the compose bridge network)*.
7. Click **Save tunnel**. Cloudflare automatically provisions the CNAME records in [Cloudflare DNS](https://dash.cloudflare.com/a7ed8378cd620788b8f508e8b5d15975/bim-guard.xyz/dns/records).

### Step 2: Configure Environment Variables in `.env`

Ensure your root `.env` includes:

```env
# ── Cloudflare Tunnel & Domain Routing ────────────────────────────────────────
BIM_GUARD_ALLOWED_ORIGINS=https://bim-guard.xyz,https://www.bim-guard.xyz,https://supabase.bim-guard.xyz
TUNNEL_TOKEN=eyJh...your_copied_token...
COMPOSE_PROFILES=tunnel

# ── Self-Hosted Supabase Production Stack ─────────────────────────────────────
# Dual-network access pattern:
# - On macOS Host (dev/tests): http://localhost:54321
# - Inside Docker Containers (bim-guard-app/opencde): http://kong:8000
SUPABASE_URL=http://localhost:54321
SUPABASE_INTERNAL_URL=http://kong:8000
SUPABASE_KEY=<anon_jwt_token>
SUPABASE_PUBLISHABLE_KEY=<anon_jwt_token>
SUPABASE_SERVICE_ROLE_KEY=<service_role_jwt_token>
SUPABASE_JWKS_URL=http://localhost:54321/auth/v1/.well-known/jwks.json
SUPABASE_INTERNAL_JWKS_URL=http://kong:8000/auth/v1/.well-known/jwks.json
JWT_SECRET=<jwt_secret_hex>
SUPABASE_STORAGE_BUCKET=bim-guard-artifacts
SUPABASE_STORAGE_PREFIX=

# Public client envs (Browser SPA builds)
PUBLIC_SUPABASE_URL=https://supabase.bim-guard.xyz
PUBLIC_SUPABASE_PUBLISHABLE_KEY=<anon_jwt_token>
VITE_SUPABASE_URL=https://supabase.bim-guard.xyz
VITE_SUPABASE_ANON_KEY=<anon_jwt_token>

# ── Inter-Container Microservices ─────────────────────────────────────────────
# Host-side dev runs reach docling-serve on the published port; the app container
# gets DOCLING_INTERNAL_URL instead (docker-compose.yml), defaulting to docling-serve.
DOCLING_LOCAL_URL=http://localhost:5001
DOCLING_INTERNAL_URL=http://docling-serve:5001
NEO4J_URI=bolt://neo4j:7687
NEO4J_AUTH=neo4j/bimguardpassword
```

> [!TIP]
> **Dev-Only Hosted Supabase Fallback**: The remote hosted Supabase project is preserved in `.env.hosted_dev`. If you need to test against the hosted instance in development without affecting the local production containers, copy or load `.env.hosted_dev` into your local environment.

> [!NOTE]
> `docker-compose.yml` automatically passes `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` as build arguments into Stage 1 of the Docker build, baking your live Supabase endpoint into the compiled Svelte 5 bundle.

### Step 3: Build and Launch with OrbStack

```bash
# Build the production image and start all services including cloudflared
docker compose --profile tunnel up -d --build
```
*(If `COMPOSE_PROFILES=tunnel` is defined in your `.env`, standard `docker compose up -d --build` automatically includes the tunnel).*

To verify container health:
```bash
docker compose ps
```
Expected output:
- `bim-guard-app` (Up, healthy on port `8000`)
- `bim-guard-neo4j` (Up, healthy on ports `7474`, `7687`)
- `bim-guard-docling` (Up, healthy on port `5001`)
- `bim-guard-opencde` (Up on port `8081`)
- `bim-guard-cloudflared` (Up, running tunnel connection)

### Step 3b: Fast Iterative Redeployment of App Code

When pushing frontend UI enhancements, API endpoint updates, or bug fixes, you do **not** need to rebuild or restart the entire stack. Instead, rebuild and recreate only the `bim-guard` application container:

```bash
# Rebuild Svelte 5 SPA + FastAPI gateway and restart only bim-guard-app
docker compose --profile tunnel up -d --build bim-guard
```

**Why this is recommended for code iterations:**
- **Zero Database Downtime**: The `neo4j` graph database remains online and connected.
- **Zero Parser Restart**: The `docling-serve` container remains warm and ready.
- **Zero Tunnel Interruption**: Cloudflare Tunnel (`bim-guard-cloudflared`) maintains its persistent outbound edge connection; traffic seamlessly routes to the recreated container as soon as it passes its healthcheck.
- **Fast Build Time**: Multi-stage Docker caching rebuilds and redeploys in ~1–2 minutes.

**Verify Live Bundle Updates:**
```bash
# 1. Inspect the updated asset hash served on the homepage:
curl -s https://bim-guard.xyz/ | grep -o 'assets/index-[^"]*'

# 2. Check health endpoint:
curl -sI https://bim-guard.xyz/health

# 3. Stream live gateway logs:
docker compose logs -f bim-guard
```

### Step 3c: Remote Deployment Trigger via GitHub Actions

A self-hosted GitHub Actions runner is configured on the host machine (`~/actions-runner`) as a persistent macOS `launchd` background service (`actions.runner.maicen-bim-guard.Sam-Mac-Studio`).

#### How it works:
- **Outbound Polling**: The runner polls GitHub securely via outbound HTTPS long-polling. No inbound open ports or external webhooks are required.
- **Automated Deploy on Push**: Pushes to `main` automatically trigger the `.github/workflows/deploy.yml` workflow, synchronizing the repo and running `docker compose --profile tunnel up -d --build bim-guard`.
- **Manual Remote Trigger**:
  1. Open the repository on **GitHub** (Web or Mobile app) &rarr; **Actions** &rarr; **Deploy Production (bim-guard.xyz)**.
  2. Click **Run workflow**.
  3. Select the target (`bim-guard` for fast app update, or `full-stack` for all microservices) and click **Run**.
- **Managing the Host Runner Service**:
  ```bash
  cd ~/actions-runner
  ./svc.sh status   # Check status
  ./svc.sh stop     # Stop runner service
  ./svc.sh start    # Start runner service
  ```

### Step 3d: Production Database Migrations & Multi-User Workflow

The production PostgreSQL database runs self-hosted in the `supabase-db` Docker container behind the Cloudflare Tunnel. Database port 54322 is not exposed to the public internet.

To allow team members and CI/CD pipelines to apply migrations safely without exposing database ports or requiring host access, a dedicated migration runner and GitHub Actions workflows are provided:

#### 1. Automatic Migration on Push / PR Merge (Hands-Off)
Whenever any developer merges a pull request or pushes new migration files (`supabase/migrations/*.sql`) to `main`, the `.github/workflows/deploy.yml` workflow automatically runs:
```bash
uv run python scripts/migrate_production.py --apply
```
This executes any pending migrations against `supabase-db`, records the migration version in `supabase_migrations.schema_migrations`, reloads the PostgREST schema cache via `NOTIFY pgrst, 'reload schema'`, and then restarts `bim-guard`.

#### 2. On-Demand Remote Migration via GitHub Actions UI
Any developer with repository access can trigger migrations on-demand without redeploying the app:
1. Navigate to **GitHub &rarr; Actions &rarr; Migrate Production Database (Self-Hosted)**.
2. Click **Run workflow**.
3. Select the desired action:
   - **`apply`** (default): Apply pending migrations and reload PostgREST.
   - **`dry-run`**: Preview which migrations would be executed without modifying the database.
   - **`status`**: Compare local migration files with remote applied versions.
4. Optionally specify a feature branch to pull migrations from before they are merged to `main`.
5. Click **Run workflow** and view real-time logs in GitHub Actions.

#### 3. Remote Migration via GitHub CLI (`gh`)
Developers can also trigger and monitor migrations directly from their local terminal:
```bash
# Check migration status
gh workflow run migrate_production.yml -f action=status

# Dry-run pending migrations
gh workflow run migrate_production.yml -f action=dry-run

# Apply migrations and reload PostgREST
gh workflow run migrate_production.yml -f action=apply

# Watch the execution in real-time
gh run watch
```

#### 4. Local Host Execution
When working directly on the host machine:
```bash
uv run python scripts/migrate_production.py --status
uv run python scripts/migrate_production.py --dry-run
uv run python scripts/migrate_production.py --apply
```

#### Branching Strategy & Best Practices: Does Deployment Need a Separate Branch?

**Recommendation: No separate branch is needed.** BIM Guard follows **Trunk-Based Development** / **Continuous Delivery** from `main`:

1. **Why Deploying from `main` is Industry Standard**:
   - `main` represents production-ready code.
   - Eliminates "merge hell", cherry-picking overhead, and branch drift (which frequently causes silent deployment bugs when a `production` branch drifts behind `main`).
   - Ensures immediate feedback loops when verified fixes and features land.

2. **When Would a Separate Branch or Tag Be Used?**:
   - **Git Tags / Releases (`v1.2.0`)**: Best for formal periodic releases where specific versions are milestone-tagged.
   - **Dedicated `production` branch**: Primarily useful in multi-team organizations with long staging QA cycles before rolling to production.

3. **Safeguards for `main`**:
   - **Selective Dispatch**: To avoid automatic deployment on every small commit, deployment can be triggered manually via GitHub Actions **Run workflow** (`workflow_dispatch`).
   - **Path Filters**: To prevent documentation and scratch updates from triggering container rebuilds, `.github/workflows/deploy.yml` can ignore paths (e.g. `paths-ignore: ['docs/**', '*.md']`).
   - **PR Protection**: Use GitHub Branch Protection on `main` to require automated linting/tests (`ruff`, `pytest -m 'not slow'`) before merging to `main`.

---

## 4. Cross-Device Development Access (Remote PCs / Internet)

When developing from a machine on a different network, use Cloudflare Tunnel to expose your local Vite dev server over HTTPS.

`cloudflared` is already installed on your Mac and the production `TUNNEL_TOKEN` is in your `.env`, so the same tunnel can serve a dev subdomain alongside `bim-guard.xyz`.

### Option A — Named Dev Tunnel (Permanent URL, Recommended)

Add a second public hostname to the existing tunnel in the Zero Trust dashboard, then run the dev tunnel script.

#### Step 1 — Add `dev.bim-guard.xyz` in the Zero Trust Dashboard

1. Open [Cloudflare Zero Trust → Networks → Tunnels](https://one.dash.cloudflare.com/a7ed8378cd620788b8f508e8b5d15975/networks/tunnels).
2. Click the `bim-guard` tunnel → **Edit** → **Public Hostnames** tab.
3. Click **Add a public hostname**:
   - **Subdomain**: `dev`
   - **Domain**: `bim-guard.xyz`
   - **Type**: `HTTP`
   - **URL**: `localhost:5173`
4. Click **Save**.

Cloudflare provisions the DNS record automatically. `https://dev.bim-guard.xyz` will route to the Vite dev server on your Mac.

#### Step 2 — Set env vars

Add to your `.env`:

```env
# Allow Vite to serve any external hostname (tunnel hostnames are arbitrary)
BIMGUARD_ALLOWED_HOSTS=*

# Allow the backend to accept API requests from the dev tunnel origin
BIM_GUARD_ALLOWED_ORIGINS=https://bim-guard.xyz,https://www.bim-guard.xyz,https://dev.bim-guard.xyz
```

#### Step 3 — Start the dev stack and the tunnel

**Terminal 1** — Normal dev servers:
```bash
./run_server.sh
```

**Terminal 2** — Named tunnel (reads `TUNNEL_TOKEN` from `.env`):
```bash
./scripts/dev_tunnel.sh
```

`https://dev.bim-guard.xyz` is now live and accessible from any machine with an internet connection.

> [!NOTE]
> Google OAuth works at `dev.bim-guard.xyz` because it's a proper domain. Add `https://dev.bim-guard.xyz/**` to your Supabase **Redirect URLs** in Authentication → URL Configuration if you want Google login on the dev tunnel too.

---

### Option B — Quick Anonymous Tunnel (Temporary, No Dashboard Config)

If you just need a one-off URL to share quickly, use the TryCloudflare quick tunnel — no account or config required:

```bash
./scripts/dev_tunnel.sh --quick
```

This prints a random `https://xxxx.trycloudflare.com` URL. Share it with your colleague. Because the hostname changes every restart, you cannot pre-register it as a CORS origin — use `*` temporarily:

```bash
# Terminal 1 — backend with wildcard CORS (dev only)
BIM_GUARD_ALLOWED_ORIGINS=* uv run uvicorn main:app --reload

# Terminal 2 — Vite frontend (host-check disabled)
BIMGUARD_ALLOWED_HOSTS=* cd frontend && npm run dev

# Terminal 3 — quick tunnel
./scripts/dev_tunnel.sh --quick
```

> [!CAUTION]
> Never commit `BIM_GUARD_ALLOWED_ORIGINS=*` to `.env`. It's wildcard CORS — only pass it inline on the command line for quick one-off sessions.

---

## 5. Alternative: Host CLI-Managed Named Tunnel (Production)

If you prefer running `cloudflared` directly on your Mac using Homebrew (`brew install cloudflared`):

1. Authenticate the CLI:
   ```bash
   cloudflared tunnel login
   ```
2. Create the tunnel:
   ```bash
   cloudflared tunnel create bim-guard
   ```
3. Route the DNS:
   ```bash
   cloudflared tunnel route dns bim-guard bim-guard.xyz
   ```
4. Create `~/.cloudflared/config.yml`:
   ```yaml
   tunnel: <TUNNEL_UUID>
   credentials-file: /Users/sam/.cloudflared/<TUNNEL_UUID>.json

   ingress:
     - hostname: bim-guard.xyz
       service: http://localhost:8000
     - service: http_status:404
   ```
5. Start Docker stack and tunnel:
   ```bash
   docker compose up -d --build
   cloudflared tunnel run bim-guard
   ```

---

## 5. Supabase Auth & Google OAuth Branding Setup

Because BIM Guard uses Google OAuth and Supabase Auth, you must authorize your custom domain in both Supabase and Google Cloud Console.

### 1. Supabase Dashboard URL Configuration

1. Open your project in the [Supabase Dashboard](https://supabase.com/dashboard/project/pmisdhiigakpjfuyxgfb/auth/url-configuration).
2. Go to **Authentication** &rarr; **URL Configuration**:
   - **Site URL**: `https://bim-guard.xyz`
   - **Redirect URLs**:
     - `https://bim-guard.xyz/**`
     - `https://bim-guard.xyz/`
     - Keep `http://localhost:5173/**` and `http://localhost:8000/**` for local development.
3. Click **Save**.

### 2. Google Cloud Console OAuth Consent Screen Branding

In the [Google Cloud Console](https://console.cloud.google.com/apis/credentials/consent):

| Form Field | Exact Value to Enter |
|---|---|
| **Application home page** | `https://bim-guard.xyz` |
| **Application privacy policy link** | `https://bim-guard.xyz/privacy` |
| **Application terms of service link** | `https://bim-guard.xyz/terms` |
| **Authorized domain 1** | `bim-guard.xyz` |
| **Authorized domain 2** | `supabase.co` |

> [!IMPORTANT]
> **Why `supabase.co` is required:**
> The Google OAuth client redirect URI is `https://pmisdhiigakpjfuyxgfb.supabase.co/auth/v1/callback`. Google Cloud Console verifies that the redirect URI matches one of your pre-registered Authorized Domains. Adding `supabase.co` authorizes Supabase's hosted callback handler.

### 3. Google Search Console Verification

If Google prompts you to verify ownership of `bim-guard.xyz`:
1. Go to [Google Search Console](https://search.google.com/search-console/about) &rarr; **Add property** &rarr; **Domain** &rarr; enter `bim-guard.xyz`.
2. Copy the DNS `TXT` verification token (`google-site-verification=...`).
3. In [Cloudflare DNS Settings](https://dash.cloudflare.com/a7ed8378cd620788b8f508e8b5d15975/bim-guard.xyz/dns/records), add a `TXT` record with name `@` and the token value.
4. Click **Verify** in Search Console (instant verification).

---

## 6. Public Compliance, Legal & SEO Endpoints

The FastAPI gateway exposes public static endpoints that return `HTTP 200 OK` directly without requiring client-side JavaScript execution:

| Endpoint | Content Type | Purpose |
|---|---|---|
| `https://bim-guard.xyz/privacy` | `text/html` | Standalone Privacy Policy adhering to Google API Limited Use policy. |
| `https://bim-guard.xyz/terms` | `text/html` | Terms of Service including OpenBIM engineering disclaimers. |
| `https://bim-guard.xyz/sitemap.xml` | `application/xml` | Standard search engine sitemap registering index, privacy, and terms. |
| `https://bim-guard.xyz/robots.txt` | `text/plain` | Crawler directives referencing `Sitemap: https://bim-guard.xyz/sitemap.xml`. |
| `https://bim-guard.xyz/og-image.png` | `image/png` | 1200×630px social card for LinkedIn, X/Twitter, Slack, and Discord. |

---

## 7. Real-Time Streaming (SSE) over Cloudflare

BIM Guard uses Server-Sent Events (`/api/events/{project_id}`) to stream real-time analysis progress from the compliance engines to the Svelte 5 frontend without polling.

The backend sends streaming headers:
- `Cache-Control: no-cache, no-transform`
- `X-Accel-Buffering: no`

In the Cloudflare Dashboard for `bim-guard.xyz`:
1. Navigate to **Network**.
2. Verify **WebSockets** is toggled **ON** (enabled by default).
3. Verify **gRPC** is toggled **ON** if gRPC modules are enabled.

---

## 8. Verification & Troubleshooting

### Check Live Endpoints

```bash
# Verify public HTTPS endpoints
curl -sI https://bim-guard.xyz/api/health
curl -sI https://bim-guard.xyz/privacy
curl -sI https://bim-guard.xyz/terms
curl -sI https://bim-guard.xyz/sitemap.xml
curl -sI https://bim-guard.xyz/robots.txt
curl -sI https://bim-guard.xyz/og-image.png
```

### Inspect Container Logs

```bash
# Gateway and SPA logs
docker compose logs -f bim-guard

# Cloudflared tunnel connection logs
docker compose logs -f cloudflared

# Docling parsing logs
docker compose logs -f docling-serve

# Neo4j logs
docker compose logs -f neo4j
```

### Common Issues & Solutions

1. **502 Bad Gateway from Cloudflare**:
   - Check the Zero Trust Tunnel public hostname configuration: ensure the service URL is set to `http://bim-guard:8000` (the compose service name), **not** `http://localhost:8000`.
   - Verify `docker compose ps` shows `bim-guard-app` as `Up (healthy)`. During initial startup, the gateway prewarms cached rules and models for ~10–15 seconds before reporting healthy.
2. **CORS Error on /api Endpoints**:
   - Ensure `BIM_GUARD_ALLOWED_ORIGINS` in `.env` includes `https://bim-guard.xyz,https://www.bim-guard.xyz` without trailing slashes.
   - Restart the gateway: `docker compose restart bim-guard`.
3. **"401 Invalid API Key" / Supabase Placeholder Errors**:
   - Ensure `SUPABASE_URL` and `SUPABASE_KEY` / `SUPABASE_PUBLISHABLE_KEY` are present in root `.env` before building.
   - Force rebuild the frontend bundle:
     ```bash
     docker compose build --no-cache bim-guard
     docker compose up -d bim-guard
     ```
4. **JWKS Token Validation Errors on /api/auth/me**:
   - Ensure `SUPABASE_JWKS_URL` is set in `.env` (e.g. `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`).
