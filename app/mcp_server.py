"""Model Context Protocol (MCP) server exposing BIM-Guard to external agents.

Mounted at ``/mcp`` (streamable HTTP) on the main ASGI app by :func:`mount_mcp`,
so Claude, Cursor and other MCP clients can list projects and rulesets, run
the architectural compliance analysis and read its findings natively.

Design: every tool forwards to the app's own ``/api`` routes through an
in-process ASGI transport, carrying the caller's own bearer token. Auth,
organization scoping, project/ruleset access checks, RLS and request
validation therefore run exactly as they do for the SPA -- the MCP layer
holds no authorization logic of its own to drift out of sync, and cannot
reach anything the caller's token could not.

Transport: stateless streamable HTTP with JSON responses. Production runs
several uvicorn workers with no session affinity, so no server-side MCP
session may be kept between requests.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Mapping
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.auth import _verify
from app.logging_config import get_logger

logger = get_logger(__name__)

MCP_MOUNT_PATH = "/mcp"

#: Cap on rows returned by list tools, so one call cannot flood an agent's context.
_MAX_ROWS = 200

_INSTRUCTIONS = (
    "BIM-Guard architectural IFC compliance. Typical flow: list_projects -> "
    "list_rulesets -> run_architecture_analysis -> get_analysis_results. "
    "Access follows the signed-in user's organization membership."
)


class McpApiError(ToolError):
    """A BIM-Guard API call made on the caller's behalf was rejected.

    A ``ToolError`` so its message reaches the agent; the SDK masks any other
    exception raised in a tool as a generic failure.
    """


def _bearer_token(headers: Mapping[str, str] | None) -> str:
    """Return the caller's bearer token from request *headers*."""
    value = (headers or {}).get("authorization", "")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise McpApiError("Missing bearer token")
    return token.strip()


class _BearerAuth:
    """ASGI guard: only requests with a valid Supabase JWT reach the MCP app.

    Rejecting here (rather than per tool) keeps ``initialize``/``tools/list``
    private too. A 401 carries ``WWW-Authenticate`` so clients know to retry
    with credentials.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap *app*."""
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Verify the bearer token for HTTP requests, then delegate."""
        if scope["type"] == "http" and scope["method"] != "OPTIONS":
            headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
            try:
                _verify(_bearer_token(headers))
            except (McpApiError, HTTPException) as exc:
                detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
                response = JSONResponse(
                    {"detail": detail},
                    status_code=401,
                    headers={"WWW-Authenticate": 'Bearer realm="bim-guard"'},
                )
                await response(scope, receive, send)
                return
        await self._app(scope, receive, send)


def _compact(rows: list[Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Project *rows* down to *keys*, capped at ``_MAX_ROWS``."""
    return [{k: r.get(k) for k in keys} for r in rows[:_MAX_ROWS]]


def create_mcp_server(api: FastAPI) -> MCPServer:
    """Build the MCP server whose tools call *api*'s routes in process."""
    mcp = MCPServer("BIM-Guard", instructions=_INSTRUCTIONS)
    transport = httpx.ASGITransport(app=api)

    async def call(
        ctx: Context,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        organization_id: int | None = None,
    ) -> Any:
        """Call ``/api{path}`` as the MCP caller and return the decoded JSON body."""
        headers = {"Authorization": f"Bearer {_bearer_token(ctx.headers)}"}
        if organization_id is not None:
            headers["X-Organization-Id"] = str(organization_id)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://bim-guard.internal", timeout=None
        ) as client:
            response = await client.request(
                method, f"/api{path}", params=params, data=data, headers=headers
            )
        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise McpApiError(f"{method} {path} failed ({response.status_code}): {detail}")
        return response.json()

    @mcp.tool(annotations={"readOnlyHint": True})
    async def list_projects(ctx: Context, organization_id: int | None = None) -> str:
        """List projects the caller can access (id, name, project_code).

        Pass organization_id to limit to one organization.
        """
        body = await call(ctx, "GET", "/projects", organization_id=organization_id)
        return json.dumps(_compact(body.get("projects", []), ("id", "name", "project_code")))

    @mcp.tool(annotations={"readOnlyHint": True})
    async def list_rulesets(ctx: Context, organization_id: int | None = None) -> str:
        """List available rulesets. Pass a returned ruleset_id to run_architecture_analysis."""
        folders = await call(ctx, "GET", "/rules/folders", organization_id=organization_id)
        return json.dumps(
            [
                {
                    "ruleset_id": f["ruleset_id"],
                    "display_name": f["display_name"],
                    "description": f.get("description", ""),
                    "rule_count": len(f.get("rules", [])),
                }
                for f in folders[:_MAX_ROWS]
            ]
        )

    @mcp.tool(annotations={"readOnlyHint": True})
    async def list_rules(
        ctx: Context,
        ruleset_id: str | None = None,
        keyword: str | None = None,
        organization_id: int | None = None,
    ) -> str:
        """List compliance rules, optionally for one ruleset or matching a keyword.

        Returns at most 200 rules; narrow with ruleset_id or keyword.
        """
        params = {"ruleset_id": ruleset_id, "keyword": keyword}
        rules = await call(
            ctx,
            "GET",
            "/rules",
            params={k: v for k, v in params.items() if v},
            organization_id=organization_id,
        )
        return json.dumps(
            {
                "total": len(rules),
                "rules": _compact(
                    rules, ("id", "rule_id", "ruleset_id", "description", "property_name")
                ),
            }
        )

    @mcp.tool(annotations={"readOnlyHint": False, "idempotentHint": True})
    async def run_architecture_analysis(
        ctx: Context, project_id: int, rule_folders: list[str] | None = None
    ) -> str:
        """Run the architectural compliance analysis on a project's IFC model.

        rule_folders are ruleset_id values from list_rulesets (all rulesets when
        omitted). Blocks until done and returns a summary; page the findings
        with get_analysis_results.
        """
        body = await call(
            ctx,
            "POST",
            "/analyze/arch",
            data={"project_id": project_id, "rule_folders": rule_folders or []},
        )
        return json.dumps(
            {
                key: body.get(key)
                for key in (
                    "project_id",
                    "project_name",
                    "total_issues",
                    "summary",
                    "rule_folders",
                    "bcf_artifact_id",
                    "ifc_element_count",
                )
            }
        )

    @mcp.tool(annotations={"readOnlyHint": True})
    async def get_analysis_status(ctx: Context, project_id: int) -> str:
        """Get the pipeline status of a project's latest compliance analysis run."""
        return json.dumps(await call(ctx, "GET", f"/analyze/status/{project_id}"))

    @mcp.tool(annotations={"readOnlyHint": True})
    async def get_analysis_results(
        ctx: Context,
        project_id: int,
        limit: int = 25,
        offset: int = 0,
        band: list[str] | None = None,
        query: str | None = None,
    ) -> str:
        """Page through a project's compliance findings, most severe first.

        issue_stats always describes the whole run. band filters by risk band,
        query is a case-insensitive substring match over title, rule and element ids.
        """
        params: dict[str, Any] = {"limit": max(1, min(limit, 200)), "offset": max(0, offset)}
        if band:
            params["band"] = band
        if query:
            params["q"] = query
        return json.dumps(
            await call(ctx, "GET", f"/analyze/results/{project_id}/architecture", params=params)
        )

    return mcp


def mount_mcp(app: FastAPI) -> MCPServer:
    """Mount the authenticated MCP endpoint at ``/mcp`` on *app*.

    Must run after every ``/api`` router is registered and before the SPA
    catch-all. Wraps the app lifespan so the MCP session manager runs for the
    life of the worker.
    """
    mcp = create_mcp_server(app)
    # Auth is a bearer token, never an ambient cookie, so DNS-rebinding Host
    # checks add nothing; they would only reject the real production hostnames.
    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    app.mount(MCP_MOUNT_PATH, _BearerAuth(mcp_app), name="mcp")

    host_lifespan = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(a: FastAPI):
        async with mcp.session_manager.run(), host_lifespan(a) as state:
            yield state

    app.router.lifespan_context = lifespan
    logger.info("MCP server mounted at %s", MCP_MOUNT_PATH)
    return mcp
