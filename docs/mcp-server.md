# BIM-Guard MCP Server

BIM-Guard exposes a [Model Context Protocol](https://modelcontextprotocol.io) server so agent clients (Claude, Cursor, custom agents) can run compliance checks natively. Implementation: [app/mcp_server.py](../app/mcp_server.py).

- **Endpoint**: `POST /mcp/` (streamable HTTP, stateless, JSON responses — safe behind the 4-worker production gateway).
- **Auth**: `Authorization: Bearer <Supabase access token>`, verified by the same code as the REST API (`app/auth.py`). Missing/invalid tokens get `401` + `WWW-Authenticate`.
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

OAuth discovery for MCP clients (RFC 9728 protected-resource metadata) is not implemented yet; see TODO.md Priority 7.
