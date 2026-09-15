"""Bearer-token authentication for external IdP-driven SCIM 2.0 requests.

A materially different scheme from app.auth's Supabase-JWT human sessions:
an IdP (Okta, Azure AD, ...) presents a static, per-organization token
minted via ``POST /api/organizations/{organization_id}/scim-token``
(app/api/organizations.py), verified here against ``public.scim_tokens``
(app.services.scim_token_service.ScimTokenService). Kept out of app/auth.py,
which is pure Supabase-JWT/JWKS verification with zero service-layer
dependencies -- this module needs the DI container, so folding it in would
invert that layering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies import get_scim_token_service
from app.services.scim_token_service import ScimTokenService

_scim_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class ScimPrincipal:
    """The organization an authenticated SCIM request is scoped to."""

    organization_id: int


def get_scim_organization(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_scim_bearer_scheme)],
    tokens: Annotated[ScimTokenService, Depends(get_scim_token_service)],
) -> ScimPrincipal:
    """Require a valid, unrevoked SCIM bearer token and return its organization."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    organization_id = tokens.authenticate(credentials.credentials)
    if organization_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked SCIM token")
    return ScimPrincipal(organization_id=organization_id)
