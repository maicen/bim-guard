"""Supabase-issued JWT verification for authenticated API requests.

Frontend sessions are established directly against Supabase Auth (Google
OAuth) via ``supabase-js`` in the browser; the backend never sees credentials,
only the resulting access token on each request's ``Authorization`` header.
This module verifies that token against Supabase's published JWKS
(``SUPABASE_JWKS_URL``) so routes can trust the caller's identity via
``Depends(get_current_user)``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated caller, decoded from a verified Supabase JWT."""

    id: str
    email: str | None
    claims: dict[str, Any]


_jwks_client: PyJWKClient | None = None


def _jwks() -> PyJWKClient:
    """Return the process-wide JWKS client, constructing it on first use."""
    global _jwks_client
    if _jwks_client is None:
        jwks_url = os.getenv("SUPABASE_JWKS_URL", "").strip()
        if not jwks_url:
            raise RuntimeError("SUPABASE_JWKS_URL is not configured")
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def _verify(token: str) -> CurrentUser:
    """Verify a bearer token's signature/expiry and decode it into a CurrentUser."""
    try:
        signing_key = _jwks().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[signing_key.algorithm_name],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc
    return CurrentUser(id=claims["sub"], email=claims.get("email"), claims=claims)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """Require a valid Supabase bearer token and return the caller's identity."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return _verify(credentials.credentials)


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser | None:
    """Return the caller's identity when a valid token is present, else None."""
    if credentials is None:
        return None
    try:
        return _verify(credentials.credentials)
    except HTTPException:
        return None
