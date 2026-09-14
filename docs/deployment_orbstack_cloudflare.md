# Running BIM Guard via OrbStack and Cloudflare Tunnel (`cloudflared`)

This guide explains how to deploy and run **BIM Guard** locally or on a private server using **OrbStack** (fast, lightweight Docker containerization on macOS) and expose it securely to your custom domain through **Cloudflare Tunnel (`cloudflared`)** with automatic SSL/TLS, DDoS protection, and Supabase OAuth support.

---

## 1. Architectural Overview

```text
  Internet Client (Browser)
             │
             │ HTTPS (e.g. https://bim.yourdomain.com)
             ▼
   Cloudflare Edge Network
   (SSL Termination, DDoS Protection, DNS Routing)
             │
             │ Encrypted Outbound Tunnel (No open router ports)
             ▼
┌─────────────────────────────────────────────────────────────┐
│ macOS / Server (OrbStack Docker Runtime)                    │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ cloudflared container                               │   │
│   │ (Proxies traffic into internal Docker network)      │   │
│   └──────────────────────────┬──────────────────────────┘   │
│                              │ HTTP                         │
│                              ▼                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ bim-guard-app container (Port 8000)                 │   │
│   │  - Svelte 5 Single Page Application (SPA)           │   │
│   │  - FastAPI REST Gateway & SSE Streaming (/api)      │   │
│   └──────────────────────────┬──────────────────────────┘   │
│                              │ Bolt (7687)                  │
│                              ▼                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ neo4j container                                     │   │
│   │ (Graph database for topological queries)            │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Prerequisites

1. **OrbStack**: Installed and active. Verify with:
   ```bash
   orb status
   docker context show # Should output: orbstack
   ```
2. **Domain on Cloudflare**: Your domain's nameservers should be pointed to Cloudflare.
3. **Supabase Project**: A valid Supabase project with credentials in your `.env`.

---

## 3. Deployment Method A: All-in-One Compose (Recommended)

In this method, `cloudflared` runs as a Docker container directly inside your `docker-compose` stack in OrbStack. No local certificates or CLI login files on your Mac are needed.

### Step 1: Create a Tunnel in Cloudflare Zero Trust

1. Log into the [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/).
2. Navigate to **Networks** → **Tunnels**.
3. Click **Add a tunnel** (or **Create a tunnel**).
4. Select **Cloudflared** as the connector and click **Next**.
5. Give your tunnel a descriptive name, e.g. `bim-guard`.
6. On the **Install connector** screen:
   - Under "Choose your environment", select **Docker**.
   - Cloudflare will show a command starting with `docker run cloudflare/cloudflared:latest tunnel --no-autoupdate run --token ey...`.
   - **Copy the token string** (the text after `--token`). This is your `TUNNEL_TOKEN`.
7. Click **Next** to proceed to the **Public Hostnames** tab.
8. Add a public hostname:
   - **Subdomain**: e.g. `bim` (or whatever subdomain you want; leave blank for apex domain)
   - **Domain**: Select your domain from the dropdown (e.g. `yourdomain.com`)
   - **Path**: Leave blank
   - **Type**: `HTTP`
   - **URL**: `bim-guard:8000`
9. Click **Save tunnel**. Cloudflare automatically configures the CNAME DNS record.

### Step 2: Configure Environment Variables in `.env`

Open your `.env` file in the project root and add the following settings:

```env
# ── Cloudflare Tunnel & Domain Routing ────────────────────────────────────────
# Your public domain URL for CORS validation
BIM_GUARD_ALLOWED_ORIGINS=https://bim.yourdomain.com

# Cloudflare Zero Trust Remote Tunnel Token
TUNNEL_TOKEN=eyJh...<your_copied_token_here>

# Automatically include the cloudflared container when running `docker compose up`
COMPOSE_PROFILES=tunnel
```

> [!NOTE]
> `docker-compose.yml` automatically forwards `SUPABASE_URL` and `SUPABASE_KEY` / `SUPABASE_PUBLISHABLE_KEY` from your `.env` into the Docker build arguments (`VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`), ensuring the Svelte 5 frontend bundle compiles with working Supabase client configuration.

### Step 3: Build and Launch with OrbStack

Run:
```bash
docker compose --profile tunnel up -d --build
```
*(If you set `COMPOSE_PROFILES=tunnel` in `.env`, `docker compose up -d --build` works as well).*

To check that all services are healthy:
```bash
docker compose ps
```
You should see:
- `bim-guard-app` (healthy, port 8000)
- `bim-guard-neo4j` (healthy, ports 7474, 7687)
- `bim-guard-cloudflared` (running)

---

## 4. Deployment Method B: Host CLI-Managed Tunnel

If you prefer running `cloudflared` directly on macOS using the installed Homebrew binary (`/opt/homebrew/bin/cloudflared`):

### Step 1: Login to Cloudflare via CLI
```bash
cloudflared tunnel login
```
This opens a browser window to authorize your Cloudflare domain and downloads an origin certificate to `~/.cloudflared/cert.pem`.

### Step 2: Create Tunnel
```bash
cloudflared tunnel create bim-guard
```
Note the Tunnel UUID output (e.g. `12345678-abcd-1234-abcd-1234567890ab`).

### Step 3: Route DNS
```bash
cloudflared tunnel route dns bim-guard bim.yourdomain.com
```

### Step 4: Create Tunnel Configuration File
Create `~/.cloudflared/config.yml`:
```yaml
tunnel: 12345678-abcd-1234-abcd-1234567890ab
credentials-file: /Users/sam/.cloudflared/12345678-abcd-1234-abcd-1234567890ab.json

ingress:
  - hostname: bim.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

### Step 5: Start Stack and Run Tunnel
Start BIM Guard in OrbStack:
```bash
docker compose up -d --build
```
Start the tunnel on your Mac:
```bash
cloudflared tunnel run bim-guard
```
*(Optionally run as a persistent macOS service using `sudo cloudflared service install`).*

---

## 5. Supabase Auth Configuration (Required)

Because authentication in BIM Guard is handled via Supabase (Google OAuth and email accounts), Supabase must recognize your custom domain as an authorized callback target.

1. Open the [Supabase Dashboard](https://supabase.com/dashboard).
2. Select your project and navigate to **Project Settings** → **Authentication** → **URL Configuration**.
3. **Site URL**:
   - Set to: `https://bim.yourdomain.com` (or keep your primary domain).
4. **Redirect URLs**:
   - Add: `https://bim.yourdomain.com/**`
   - Add: `https://bim.yourdomain.com/`
   - Keep existing `http://localhost:5173/**` and `http://localhost:8000/**` so local development still functions.
5. Click **Save**.

---

## 6. Real-Time Streaming (SSE) over Cloudflare

BIM Guard uses Server-Sent Events (`/api/events/{project_id}`) to stream real-time analysis progress from the compliance engines to the Svelte 5 frontend.

The backend automatically sends:
- `Cache-Control: no-cache, no-transform`
- `X-Accel-Buffering: no`

In the Cloudflare Dashboard for your domain:
1. Navigate to **Network**.
2. Ensure **WebSockets** is toggled **ON** (enabled by default).
3. Ensure **gRPC** is toggled **ON** if you use gRPC microservices.

---

## 7. Verification & Troubleshooting

### Check Container Logs
```bash
# Backend & SPA logs
docker compose logs -f bim-guard

# Cloudflared tunnel connection logs
docker compose logs -f cloudflared
```

### Common Issues & Fixes

1. **"CORS request did not succeed" / Network Error in Browser**:
   - Check that `BIM_GUARD_ALLOWED_ORIGINS` in your `.env` contains `https://bim.yourdomain.com` (exact protocol and domain, no trailing slash).
   - Restart the stack: `docker compose restart bim-guard`.

2. **"Sign-in is disabled" or "placeholder.supabase.co" in browser console**:
   - Rebuild the container so the frontend picks up the build arguments:
     ```bash
     docker compose build --no-cache bim-guard
     docker compose up -d bim-guard
     ```

3. **Cloudflared connection error 502 Bad Gateway**:
   - In Method A: Ensure the Cloudflare Zero Trust public hostname URL points to `http://bim-guard:8000` (internal Docker hostname), NOT `localhost:8000`.
   - In Method B: Ensure it points to `http://localhost:8000`.

