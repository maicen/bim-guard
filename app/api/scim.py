"""SCIM 2.0 (RFC 7644) provisioning endpoints for external IdPs (Okta, Azure AD, ...).

Mounted at ``/api/scim/v2`` -- this ``v2`` is SCIM's own protocol version
(RFC 7644), not a BIM-Guard API version, so it is exempt from
docs/CONVENTIONS.md's no-URL-versioning rule, which governs BIM-Guard's own
``/api/*`` resource surface, not a spec-mandated external protocol namespace
(the same reasoning that already carves out ``/api/bcf/v2.1``).

Every route depends on :func:`app.scim_auth.get_scim_organization`, a
per-organization bearer token distinct from Supabase-JWT human auth --
minted via the human-facing endpoints in ``app/api/organizations.py``
(``POST /api/organizations/{organization_id}/scim-token``).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.dependencies import get_scim_service
from app.modules.scim_contracts import (
    SCIM_GROUP_SCHEMA,
    SCIM_USER_SCHEMA,
    ScimEmail,
    ScimGroup,
    ScimGroupCreateRequest,
    ScimGroupMember,
    ScimListResponse,
    ScimMeta,
    ScimName,
    ScimPatchRequest,
    ScimResourceType,
    ScimSchema,
    ScimServiceProviderConfig,
    ScimUser,
    ScimUserCreateRequest,
)
from app.scim_auth import ScimPrincipal, get_scim_organization
from app.services.scim_service import ScimGroupNotFound, ScimService, ScimUserNotFound

router = APIRouter()

_ScimAuth = Annotated[ScimPrincipal, Depends(get_scim_organization)]
_ScimSvc = Annotated[ScimService, Depends(get_scim_service)]


def _base_url(request: Request) -> str:
    return f"{str(request.base_url).rstrip('/')}/api/scim/v2"


def _user_to_scim(row: dict[str, Any], base_url: str) -> ScimUser:
    return ScimUser(
        id=str(row["id"]),
        userName=row["user_name"],
        name=ScimName(formatted=row["full_name"]) if row["full_name"] else None,
        emails=[ScimEmail(value=row["user_name"])] if row["user_name"] else [],
        active=row["active"],
        meta=ScimMeta(resourceType="User", location=f"{base_url}/Users/{row['id']}"),
    )


def _group_to_scim(row: dict[str, Any], base_url: str) -> ScimGroup:
    return ScimGroup(
        id=str(row["id"]),
        displayName=row["display_name"],
        members=[ScimGroupMember(value=m["value"], display=m.get("display")) for m in row["members"]],
        meta=ScimMeta(resourceType="Group", location=f"{base_url}/Groups/{row['id']}"),
    )


def _extract_eq_filter(filter_str: str | None) -> str | None:
    """Pull the right-hand value out of `userName eq "x"` / `emails.value eq "x"`; else None.

    IdPs (Okta, Azure AD) only ever send this one filter form when searching
    for an existing user before provisioning -- full SCIM filter grammar
    (and/or, co/sw/gt, nested groupings) is deliberately not implemented.
    """
    if not filter_str or " eq " not in filter_str.lower():
        return None
    _, _, value_part = filter_str.partition(" eq ")
    return value_part.strip().strip('"')


# -- Discovery ------------------------------------------------------------------


@router.get(
    "/ServiceProviderConfig",
    response_model=ScimServiceProviderConfig,
    summary="SCIM service provider configuration",
)
def get_service_provider_config(_auth: _ScimAuth) -> ScimServiceProviderConfig:
    """Advertise which optional SCIM features this endpoint supports."""
    return ScimServiceProviderConfig()


@router.get("/ResourceTypes", response_model=list[ScimResourceType], summary="SCIM resource type discovery")
def list_resource_types(_auth: _ScimAuth) -> list[ScimResourceType]:
    """List the SCIM resource types (Users, Groups) this endpoint exposes."""
    return [
        ScimResourceType(id="User", name="User", endpoint="/Users", schema=SCIM_USER_SCHEMA, description="User provisioning"),
        ScimResourceType(id="Group", name="Group", endpoint="/Groups", schema=SCIM_GROUP_SCHEMA, description="Group provisioning"),
    ]


@router.get("/Schemas", response_model=list[ScimSchema], summary="SCIM schema discovery")
def list_schemas(_auth: _ScimAuth) -> list[ScimSchema]:
    """List the SCIM core schemas this endpoint uses."""
    return [
        ScimSchema(id=SCIM_USER_SCHEMA, name="User", description="User Account"),
        ScimSchema(id=SCIM_GROUP_SCHEMA, name="Group", description="Group"),
    ]


# -- Users ------------------------------------------------------------------------


@router.get("/Users", response_model=ScimListResponse, summary="List/search provisioned users")
def list_users(
    auth: _ScimAuth,
    scim: _ScimSvc,
    request: Request,
    filter: Annotated[str | None, Query()] = None,
    startIndex: Annotated[int, Query(ge=1)] = 1,
    count: Annotated[int, Query(ge=0, le=200)] = 100,
) -> ScimListResponse:
    """List users provisioned into this SCIM token's organization.

    Supports the one filter form IdPs actually send:
    ``userName eq "..."`` / ``emails.value eq "..."`` (case-insensitive).
    """
    user_name_filter = _extract_eq_filter(filter)
    total, rows = scim.list_users(
        auth.organization_id, user_name_filter=user_name_filter, start_index=startIndex, count=count
    )
    base_url = _base_url(request)
    return ScimListResponse(
        totalResults=total,
        startIndex=startIndex,
        itemsPerPage=len(rows),
        Resources=[_user_to_scim(r, base_url).model_dump(exclude_none=True) for r in rows],
    )


@router.get("/Users/{user_id}", response_model=ScimUser, summary="Get one provisioned user")
def get_user(user_id: str, auth: _ScimAuth, scim: _ScimSvc, request: Request) -> ScimUser:
    """Return one provisioned user by their Supabase Auth id."""
    try:
        row = scim.get_user(auth.organization_id, user_id)
    except ScimUserNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_to_scim(row, _base_url(request))


@router.post("/Users", response_model=ScimUser, status_code=status.HTTP_201_CREATED, summary="Provision a new user")
def create_user(payload: ScimUserCreateRequest, auth: _ScimAuth, scim: _ScimSvc, request: Request) -> ScimUser:
    """Provision a user (creating their Supabase Auth account if needed) into this organization."""
    full_name = payload.name.formatted if payload.name else ""
    row = scim.create_user(
        auth.organization_id, user_name=payload.userName, full_name=full_name or "", active=payload.active
    )
    return _user_to_scim(row, _base_url(request))


@router.put("/Users/{user_id}", response_model=ScimUser, summary="Replace a provisioned user")
def replace_user(
    user_id: str, payload: ScimUserCreateRequest, auth: _ScimAuth, scim: _ScimSvc, request: Request
) -> ScimUser:
    """Replace a provisioned user's profile fields and org membership state."""
    full_name = payload.name.formatted if payload.name else ""
    row = scim.replace_user(
        auth.organization_id,
        user_id,
        user_name=payload.userName,
        full_name=full_name or "",
        active=payload.active,
    )
    return _user_to_scim(row, _base_url(request))


def _patch_active_value(payload: ScimPatchRequest) -> bool | None:
    active: bool | None = None
    for op in payload.Operations:
        path = (op.path or "").strip().lower()
        if path == "active":
            active = bool(op.value)
        elif path == "" and isinstance(op.value, dict) and "active" in op.value:
            active = bool(op.value["active"])
    return active


@router.patch(
    "/Users/{user_id}",
    response_model=ScimUser,
    summary="Partially update a provisioned user (activate/deactivate)",
)
def patch_user(
    user_id: str, payload: ScimPatchRequest, auth: _ScimAuth, scim: _ScimSvc, request: Request
) -> ScimUser:
    """Apply PATCH operations -- in practice, IdPs use this exclusively to toggle `active`."""
    active = _patch_active_value(payload)
    try:
        row = (
            scim.patch_user_active(auth.organization_id, user_id, active)
            if active is not None
            else scim.get_user(auth.organization_id, user_id)
        )
    except ScimUserNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_to_scim(row, _base_url(request))


@router.delete("/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deprovision a user")
def delete_user(user_id: str, auth: _ScimAuth, scim: _ScimSvc) -> Response:
    """Remove a user's membership in this organization (their Supabase Auth identity is untouched)."""
    scim.delete_user(auth.organization_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- Groups -----------------------------------------------------------------------


@router.get("/Groups", response_model=ScimListResponse, summary="List RBAC groups as SCIM groups")
def list_groups(auth: _ScimAuth, scim: _ScimSvc, request: Request) -> ScimListResponse:
    """List every RBAC group in this SCIM token's organization."""
    rows = scim.list_groups(auth.organization_id)
    base_url = _base_url(request)
    return ScimListResponse(
        totalResults=len(rows),
        startIndex=1,
        itemsPerPage=len(rows),
        Resources=[_group_to_scim(r, base_url).model_dump(exclude_none=True) for r in rows],
    )


@router.get("/Groups/{group_id}", response_model=ScimGroup, summary="Get one group")
def get_group(group_id: int, auth: _ScimAuth, scim: _ScimSvc, request: Request) -> ScimGroup:
    """Return one RBAC group by id."""
    try:
        row = scim.get_group(auth.organization_id, group_id)
    except ScimGroupNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return _group_to_scim(row, _base_url(request))


@router.post("/Groups", response_model=ScimGroup, status_code=status.HTTP_201_CREATED, summary="Create a group")
def create_group(payload: ScimGroupCreateRequest, auth: _ScimAuth, scim: _ScimSvc, request: Request) -> ScimGroup:
    """Create a new RBAC group with the given initial members."""
    row = scim.create_group(
        auth.organization_id,
        display_name=payload.displayName,
        member_ids=[m.value for m in payload.members],
    )
    return _group_to_scim(row, _base_url(request))


@router.put("/Groups/{group_id}", response_model=ScimGroup, summary="Replace a group's members")
def replace_group(
    group_id: int, payload: ScimGroupCreateRequest, auth: _ScimAuth, scim: _ScimSvc, request: Request
) -> ScimGroup:
    """Replace a group's entire member list."""
    try:
        row = scim.replace_group(
            auth.organization_id,
            group_id,
            display_name=payload.displayName,
            member_ids=[m.value for m in payload.members],
        )
    except ScimGroupNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return _group_to_scim(row, _base_url(request))


@router.patch("/Groups/{group_id}", response_model=ScimGroup, summary="Add/remove a group's members")
def patch_group(
    group_id: int, payload: ScimPatchRequest, auth: _ScimAuth, scim: _ScimSvc, request: Request
) -> ScimGroup:
    """Apply add/remove member operations against the group's member list."""
    try:
        current = scim.get_group(auth.organization_id, group_id)
    except ScimGroupNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    member_ids = {m["value"] for m in current["members"]}
    for op in payload.Operations:
        path = (op.path or "").strip().lower()
        if not path.startswith("members"):
            continue
        values = op.value if isinstance(op.value, list) else ([op.value] if op.value else [])
        ids = [v.get("value") if isinstance(v, dict) else v for v in values]
        if op.op == "add":
            member_ids.update(i for i in ids if i)
        elif op.op == "remove":
            member_ids.difference_update(i for i in ids if i)

    try:
        row = scim.replace_group(
            auth.organization_id, group_id, display_name=current["display_name"], member_ids=list(member_ids)
        )
    except ScimGroupNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return _group_to_scim(row, _base_url(request))


@router.delete("/Groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a group")
def delete_group(group_id: int, auth: _ScimAuth, scim: _ScimSvc) -> Response:
    """Permanently delete an RBAC group."""
    try:
        scim.delete_group(auth.organization_id, group_id)
    except ScimGroupNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
