"""SCIM 2.0 (RFC 7643/7644) wire-format contracts for IdP-driven provisioning.

Kept separate from app.modules.contracts: SCIM's wire shape (a `schemas` URN
array, `meta`, multi-valued `emails`/`members`, and PATCH `Operations`) is a
different contract family from BIM-Guard's native REST responses and must
match the SCIM spec's field names exactly (camelCase, not this repo's usual
snake_case), not this repo's own naming conventions.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
SCIM_LIST_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:ListResponse"
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"
SCIM_PATCHOP_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
SCIM_SERVICE_PROVIDER_CONFIG_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"
SCIM_RESOURCE_TYPE_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:ResourceType"


class ScimMeta(BaseModel):
    """Read-only resource metadata attached to every SCIM User/Group."""

    resourceType: str
    created: Optional[str] = None
    lastModified: Optional[str] = None
    location: Optional[str] = None


class ScimEmail(BaseModel):
    """One email address on a SCIM User -- BIM-Guard has exactly one, the sign-in email."""

    value: str
    primary: bool = True
    type: str = "work"


class ScimName(BaseModel):
    """A SCIM User's name; only the single formatted display name is tracked."""

    formatted: Optional[str] = None


class ScimUser(BaseModel):
    """A provisioned user, scoped to the requesting SCIM token's organization."""

    schemas: list[str] = Field(default_factory=lambda: [SCIM_USER_SCHEMA])
    id: str
    userName: str
    name: Optional[ScimName] = None
    emails: list[ScimEmail] = Field(default_factory=list)
    active: bool = True
    meta: Optional[ScimMeta] = None


class ScimUserCreateRequest(BaseModel):
    """Payload for POST/PUT /Users -- userName is the user's sign-in email."""

    schemas: list[str] = Field(default_factory=lambda: [SCIM_USER_SCHEMA])
    userName: str
    name: Optional[ScimName] = None
    emails: list[ScimEmail] = Field(default_factory=list)
    active: bool = True


class ScimGroupMember(BaseModel):
    """One member reference within a SCIM Group."""

    value: str
    display: Optional[str] = None


class ScimGroup(BaseModel):
    """An organization's RBAC group, exposed as a SCIM Group.

    See app.services.scim_service.ScimService's module docstring for why an
    RBAC group is the natural SCIM Group mapping.
    """

    schemas: list[str] = Field(default_factory=lambda: [SCIM_GROUP_SCHEMA])
    id: str
    displayName: str
    members: list[ScimGroupMember] = Field(default_factory=list)
    meta: Optional[ScimMeta] = None


class ScimGroupCreateRequest(BaseModel):
    """Payload for POST/PUT /Groups."""

    schemas: list[str] = Field(default_factory=lambda: [SCIM_GROUP_SCHEMA])
    displayName: str
    members: list[ScimGroupMember] = Field(default_factory=list)


class ScimPatchOperation(BaseModel):
    """One operation within a SCIM PATCH request body."""

    op: Literal["add", "remove", "replace"]
    path: Optional[str] = None
    value: Any = None


class ScimPatchRequest(BaseModel):
    """Payload for PATCH /Users/{id} and PATCH /Groups/{id}."""

    schemas: list[str] = Field(default_factory=lambda: [SCIM_PATCHOP_SCHEMA])
    Operations: list[ScimPatchOperation]


class ScimListResponse(BaseModel):
    """Envelope for GET /Users and GET /Groups list results."""

    schemas: list[str] = Field(default_factory=lambda: [SCIM_LIST_SCHEMA])
    totalResults: int
    startIndex: int = 1
    itemsPerPage: int
    Resources: list[dict[str, Any]] = Field(default_factory=list)


class ScimError(BaseModel):
    """SCIM-shaped error body, for handlers that want a spec-compliant error payload."""

    schemas: list[str] = Field(default_factory=lambda: [SCIM_ERROR_SCHEMA])
    detail: str
    status: str


class ScimServiceProviderConfig(BaseModel):
    """GET /ServiceProviderConfig -- advertises which optional SCIM features are supported."""

    schemas: list[str] = Field(default_factory=lambda: [SCIM_SERVICE_PROVIDER_CONFIG_SCHEMA])
    patch: dict[str, bool] = Field(default_factory=lambda: {"supported": True})
    bulk: dict[str, Any] = Field(
        default_factory=lambda: {"supported": False, "maxOperations": 0, "maxPayloadSize": 0}
    )
    filter: dict[str, Any] = Field(default_factory=lambda: {"supported": True, "maxResults": 200})
    changePassword: dict[str, bool] = Field(default_factory=lambda: {"supported": False})
    sort: dict[str, bool] = Field(default_factory=lambda: {"supported": False})
    etag: dict[str, bool] = Field(default_factory=lambda: {"supported": False})
    authenticationSchemes: list[dict[str, Any]] = Field(
        default_factory=lambda: [
            {
                "type": "oauthbearertoken",
                "name": "OAuth Bearer Token",
                "description": "Per-organization bearer token minted from BIM-Guard organization settings",
            }
        ]
    )


class ScimResourceType(BaseModel):
    """One entry of GET /ResourceTypes."""

    schemas: list[str] = Field(default_factory=lambda: [SCIM_RESOURCE_TYPE_SCHEMA])
    id: str
    name: str
    endpoint: str
    schema_: str = Field(alias="schema", serialization_alias="schema")
    description: str = ""

    model_config = {"populate_by_name": True}


class ScimSchema(BaseModel):
    """One entry of GET /Schemas."""

    id: str
    name: str
    description: str = ""
    attributes: list[dict[str, Any]] = Field(default_factory=list)
