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
│   └────────────────────────────────┬────────────────────────────────┘   │
│                                    │ HTTP                               │
│                                    ▼                                    │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ bim-guard-app container (Port 8000)                             │   │
│   │  - Compiled Svelte 5 Single Page Application (frontend/dist)    │   │
│   │  - 4-Worker Uvicorn ASGI FastAPI Gateway                        │   │
│   │  - REST APIs, SSE Events (/api/events/{project_id})             │   │
│   │  - Legal & SEO Endpoints (/privacy, /terms, /sitemap.xml)       │   │
│   └───────┬────────────────────────┬───────────────────────┬────────┘   │
│           │ Bolt (7687)            │ HTTP (5001)           │ HTTP (8081)│
│           ▼                        ▼                       ▼            │
│   ┌───────────────┐        ┌───────────────┐       ┌────────────────┐   │
│   │ bim-guard-    │        │ bim-guard-    │       │ bim-guard-     │   │
│   │ neo4j         │        │ docling       │       │ opencde        │   │
│   │ (Graph DB)    │        │ (REST Parser) │       │ (OpenCDE API)  │   │
│   └───────────────┘        └───────────────┘       └────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Docker Compose Stack & Services (`docker-compose.yml`)

The platform is orchestrated as a multi-container stack:

1. **`bim-guard` (`bim-guard-app`)**:
   - Built via the multi-stage [`Dockerfile`](../Dockerfile) (Node 22 Svelte 5 builder &rarr; Python 3.12 Astral uv virtualenv &rarr; Debian Bookworm runtime with OpenCASCADE/IfcOpenShell bindings).
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
6. Add the public routing rule:
   - **Subdomain**: Leave blank (for apex `bim-guard.xyz`) or specify `app` / `www`.
   - **Domain**: `bim-guard.xyz`
   - **Path**: Leave blank.
   - **Type**: `HTTP`
   - **URL**: `bim-guard:8000` *(resolves to the `bim-guard` service inside the compose bridge network)*.
7. Click **Save tunnel**. Cloudflare automatically provisions the CNAME record in [Cloudflare DNS](https://dash.cloudflare.com/a7ed8378cd620788b8f508e8b5d15975/bim-guard.xyz/dns/records).

### Step 2: Configure Environment Variables in `.env`

Ensure your root `.env` includes:

```env
# ── Cloudflare Tunnel & Domain Routing ────────────────────────────────────────
BIM_GUARD_ALLOWED_ORIGINS=https://bim-guard.xyz,https://www.bim-guard.xyz
TUNNEL_TOKEN=eyJh...your_copied_token...
COMPOSE_PROFILES=tunnel

# ── Supabase Database & Auth ──────────────────────────────────────────────────
SUPABASE_URL=https://<project-id>.supabase.co
SUPABASE_KEY=<anon_or_publishable_key>
SUPABASE_PUBLISHABLE_KEY=<anon_key>
SUPABASE_SERVICE_ROLE_KEY=<service_role_key>
SUPABASE_JWKS_URL=https://<project-id>.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_STORAGE_BUCKET=bim-guard-artifacts

# ── Inter-Container Microservices ─────────────────────────────────────────────
DOCLING_LOCAL_URL=http://docling-serve:5001
NEO4J_URI=bolt://neo4j:7687
NEO4J_AUTH=neo4j/bimguardpassword

# ── Optional S3 Storage Backend (if enabled) ──────────────────────────────────
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_ENDPOINT_URL=
S3_REGION=
```

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

---

## 4. Alternative: Host CLI-Managed Tunnel

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
