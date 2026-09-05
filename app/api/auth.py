"""FastAPI router for the authenticated caller's own identity."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_membership_service
from app.auth import CurrentUser, get_current_user
from app.modules.contracts import CurrentUserResponse, OrganizationMembership
from app.services.membership_service import MembershipService

router = APIRouter()


@router.get("/me", response_model=CurrentUserResponse, summary="Get the authenticated caller's identity")
def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
) -> CurrentUserResponse:
    """Return the caller's identity and organization memberships.

    A first-time sign-in has no membership row yet, so this joins the caller
    into the default organization before listing memberships — see
    ``MembershipService.ensure_default_membership``.
    """
    orgs = memberships.ensure_default_membership(current_user.id)
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
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
