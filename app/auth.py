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
from fastapi import Depends, HTTPException, Query, status
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


def get_current_user_flexible(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    token: str | None = Query(
        None,
        description="Bearer token as a query parameter, for links the frontend "
        "opens via direct browser navigation (<a href>, window.location) rather "
        "than fetch -- those can't set an Authorization header.",
    ),
) -> CurrentUser:
    """Require a valid Supabase bearer token from either the header or `?token=`.

    A handful of downloads (report exports, BCF artifacts, document files) are
    wired up in the SPA as plain `<a href>`/`window.location.href` navigations
    rather than an authenticated `fetch`, precisely so the browser handles the
    save-file flow itself -- and a browser navigation cannot carry a custom
    `Authorization` header. Those routes use this instead of
    `get_current_user` so securing them doesn't silently break the download.
    """
    raw_token = credentials.credentials if credentials else token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return _verify(raw_token)


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
