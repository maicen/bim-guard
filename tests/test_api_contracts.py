"""Guardrail enforcing BIM-Guard's API standards on every registered route.

Walks the live ``app.main.app`` route table so a new endpoint that skips a
strict Pydantic ``response_model``, auth, an OpenAPI tag, or a summary fails
this test immediately -- see the "API Standards" section of
docs/CONVENTIONS.md for the policy this enforces.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.auth import get_current_user, get_current_user_flexible
from app.main import TAGS_METADATA, app

_AUTH_DEPENDENCY_CALLABLES = {get_current_user, get_current_user_flexible}

_REGISTERED_TAGS = {tag["name"] for tag in TAGS_METADATA}

# Routes that legitimately return a raw Response (file download, streamed
# export, binary image) rather than a JSON body, so FastAPI never infers a
# response_model for them. Keyed by (method, path) exactly as it appears in
# the OpenAPI path template.
RESPONSE_MODEL_EXEMPT: set[tuple[str, str]] = {
    ("GET", "/api/analyze/export"),
    ("GET", "/api/analyze/bcf/artifacts/{artifact_id}"),
    ("GET", "/api/analyze/bcf/latest/{project_id}"),
    ("GET", "/api/documents/{document_id}/file"),
    ("GET", "/api/documents/{document_id}/rules/drafts/ids-preview"),
    ("GET", "/api/projects/{project_id}/ifc"),
    ("GET", "/api/projects/{project_id}/enhancements/{lineage_id}/download"),
    ("GET", "/api/projects/{project_id}/files/{file_id}/ifc"),
    ("GET", "/api/rules/export-ids"),
    ("GET", "/api/rules/export-ids/{ruleset_id}"),
    ("GET", "/api/rules/export-json"),
    ("GET", "/api/rules/export-json/{ruleset_id}"),
    ("GET", "/api/rules/snapshots/{snapshot_id}/pdf"),
    ("GET", "/api/bcf/v2.1/projects/{project_id}/topics/{topic_guid}/viewpoints/{viewpoint_guid}/snapshot"),
    ("GET", "/api/bcf/v2.1/projects/{project_id}/topics/{topic_guid}/viewpoints/{viewpoint_guid}/bitmap"),
    ("GET", "/api/events/{project_id}"),
    ("GET", "/api/workflow/{project_id}/events"),
    ("GET", "/download/{fmt}/{project_id}"),
}

# Routes whose auth is enforced but not via a direct get_current_user*
# Depends() on the endpoint itself -- e.g. it's satisfied transitively through
# a sub-dependency this walk already follows, or the route is a framework
# fallback that never reaches application code. Empty by design: every real
# gap should be closed by adding auth or the "Public" tag, not by growing this
# list.
AUTH_EXEMPT: set[tuple[str, str]] = set()


def _iter_api_routes():
    for route in app.routes:
        if isinstance(route, APIRoute) and route.include_in_schema:
            yield route


def _has_auth_dependency(route: APIRoute) -> bool:
    """Recursively search the dependency tree for a get_current_user* Depends()."""
    seen = set()

    def _walk(dependant) -> bool:
        if dependant is None or id(dependant) in seen:
            return False
        seen.add(id(dependant))
        if dependant.call in _AUTH_DEPENDENCY_CALLABLES:
            return True
        return any(_walk(sub) for sub in dependant.dependencies)

    return _walk(route.dependant)


def _is_strict_response_model(model) -> bool:
    """Return True for a real Pydantic model/union/generic; False for a bare dict/list."""
    if model is None:
        return False
    if model in (dict, list):
        return False
    return True


def test_every_route_declares_a_strict_response_model():
    violations = []
    for route in _iter_api_routes():
        key = (next(iter(route.methods - {"HEAD"})), route.path)
        if key in RESPONSE_MODEL_EXEMPT:
            continue
        if not _is_strict_response_model(route.response_model):
            violations.append(f"{key[0]} {key[1]} ({route.endpoint.__module__}.{route.endpoint.__name__})")
    assert not violations, (
        "Routes missing a strict Pydantic response_model (add one from "
        "app.modules.contracts, or add the route to RESPONSE_MODEL_EXEMPT if "
        "it genuinely returns a raw file/stream Response):\n  "
        + "\n  ".join(violations)
    )


def test_every_route_is_authenticated_or_explicitly_public():
    violations = []
    for route in _iter_api_routes():
        key = (next(iter(route.methods - {"HEAD"})), route.path)
        if key in AUTH_EXEMPT:
            continue
        if _has_auth_dependency(route):
            continue
        if "Public" in (route.tags or []):
            continue
        violations.append(f"{key[0]} {key[1]} ({route.endpoint.__module__}.{route.endpoint.__name__})")
    assert not violations, (
        "Routes with no auth dependency and no explicit 'Public' tag -- add "
        "Depends(get_current_user) (or get_current_user_flexible), or tag the "
        "route ['Public'] if it is deliberately open:\n  " + "\n  ".join(violations)
    )


def test_every_route_tag_is_registered_in_openapi_tags_metadata():
    violations = []
    for route in _iter_api_routes():
        tags = route.tags or []
        if not tags:
            violations.append(f"(no tags) {route.path} ({route.endpoint.__module__}.{route.endpoint.__name__})")
            continue
        for tag in tags:
            if tag not in _REGISTERED_TAGS:
                violations.append(f"tag {tag!r} on {route.path} is not in app.main.TAGS_METADATA")
    assert not violations, "\n  ".join(["Untagged/undocumented routes:", *violations])


def test_every_route_has_a_summary():
    violations = [
        f"{route.methods} {route.path} ({route.endpoint.__module__}.{route.endpoint.__name__})"
        for route in _iter_api_routes()
        if not route.summary
    ]
    assert not violations, "Routes missing a summary=...:\n  " + "\n  ".join(violations)
