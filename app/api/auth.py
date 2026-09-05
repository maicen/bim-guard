"""FastAPI router for the authenticated caller's own identity and profile."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_membership_service, get_profile_service
from app.auth import CurrentUser, get_current_user
from app.modules.contracts import (
    CurrentUserResponse,
    OrganizationMembership,
    ProfileUpdateRequest,
    UserProfile,
)
from app.services.membership_service import MembershipService
from app.services.profile_service import ProfileService

router = APIRouter()


def _google_claims(current_user: CurrentUser) -> tuple[str, str]:
    """Pull a display name and avatar out of Google's own OAuth claims.

    Supabase forwards whatever Google returned as ``user_metadata`` on the
    JWT; there's no guarantee every key is present, hence the fallbacks.
    """
    metadata: dict[str, Any] = current_user.claims.get("user_metadata") or {}
    full_name = metadata.get("full_name") or metadata.get("name") or ""
    avatar_url = metadata.get("avatar_url") or metadata.get("picture") or ""
    return full_name, avatar_url


@router.get("/me", response_model=CurrentUserResponse, summary="Get the authenticated caller's identity")
def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> CurrentUserResponse:
    """Return the caller's identity, profile, and organization memberships.

    A first-time sign-in has neither a profile nor a membership row yet, so
    both are provisioned here — the profile from Google's own claims, the
    membership into the default organization (see
    ``MembershipService.ensure_default_membership``).
    """
    orgs = memberships.ensure_default_membership(current_user.id)
    full_name, avatar_url = _google_claims(current_user)
    profile = profiles.ensure_profile(current_user.id, full_name=full_name, avatar_url=avatar_url)
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        profile=UserProfile(**profile),
        organizations=[
            OrganizationMembership(
                organization_id=org["organization_id"],
                name=org["name"],
                slug=org["slug"],
                role=org["role"],
            )
            for org in orgs
        ],
    )


@router.patch("/profile", response_model=UserProfile, summary="Update the authenticated caller's profile")
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> UserProfile:
    """Merge the given fields into the caller's own profile."""
    updates = payload.model_dump(exclude_unset=True)
    updated = profiles.update(current_user.id, updates)
    return UserProfile(**updated)
