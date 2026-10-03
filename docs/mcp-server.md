# BIM-Guard MCP Server

BIM-Guard exposes a [Model Context Protocol](https://modelcontextprotocol.io) server so agent clients (Claude, Cursor, custom agents) can run compliance checks natively. Implementation: [app/mcp_server.py](../app/mcp_server.py).

- **Endpoint**: `POST /mcp/` (streamable HTTP, stateless, JSON responses — safe behind the 4-worker production gateway).
- **Auth**: `Authorization: Bearer <Supabase access token>`, verified by the same code as the REST API (`app/auth.py`). Missing/invalid tokens get `401` + a `WWW-Authenticate: Bearer resource_metadata="…"` challenge.
- **Discovery (RFC 9728)**: `GET /.well-known/oauth-protected-resource` (also `…/mcp`) names Supabase Auth (`$PUBLIC_SUPABASE_URL/auth/v1`) as the authorization server. An OAuth-capable MCP client reads that, registers itself, and signs the user in through the browser — no pasted token.
- **Authorization**: every tool calls the app's own `/api` routes in process with the caller's token, so organization scoping, project/ruleset access checks and RLS are identical to the SPA. The MCP layer has no access logic of its own.

## Tools

| Tool | Purpose |
| --- | --- |
| `list_projects` | Projects the caller can access (optional `organization_id`) |
| `list_rulesets` | Rulesets; pass a `ruleset_id` to the analysis tool |
| `list_rules` | Rules, filter by `ruleset_id` / `keyword` (max 200) |
| `run_architecture_analysis` | Run the analysis on a project's IFC model; returns a summary |
| `get_analysis_status` | Pipeline status of the latest run |
| `get_analysis_results` | Paged findings (`limit`, `offset`, `band`, `query`) |

## Connecting a client

```json
{
  "mcpServers": {
    "bim-guard": {
      "type": "http",
      "url": "https://bim-guard.xyz/mcp/",
      "headers": { "Authorization": "Bearer ${BIM_GUARD_TOKEN}" }
    }
  }
}
```

Locally use `http://localhost:8000/mcp/`. Never commit a literal token.

With an OAuth-capable client, omit the `headers` block; the client discovers the sign-in flow itself.

## Browser sign-in setup (one-time, per Supabase project)

The app side is built (discovery + the consent screen at `/oauth/consent`, [OAuthConsentView.svelte](../frontend/src/routes/OAuthConsentView.svelte)). Supabase Auth must also act as an OAuth 2.1 server:

1. Enable the **OAuth 2.1 server** and **dynamic client registration** (Dashboard → Authentication → OAuth Server; locally `[auth.oauth_server]` in `supabase/config.toml`). Self-hosted GoTrue: follow Supabase's self-hosting docs for the equivalent settings in `docker/supabase/docker-compose.yml`.
2. Set the authorization path to `/oauth/consent` and the Auth **Site URL** to the app origin.
3. Set `BIM_GUARD_PUBLIC_URL` (app origin) and `PUBLIC_SUPABASE_URL` (public Supabase URL) for the app container — behind the Cloudflare tunnel the app cannot infer them. Both are passed through in `docker-compose.yml`.

Until step 1 is done, clients fall back to the pasted-token setup above. Dynamic registration lets any compatible client register, so review registered clients periodically.
