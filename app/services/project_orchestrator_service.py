"""Thin service layer extracted from ``app/api/projects.py``.

Owns the logic that used to live as private router-module helpers:

* :func:`owned_project_ids` — filters a list of project IDs to those the
  current caller may act on, respecting superadmin bypass.
* :func:`primary_organization_id` — returns the organization a new project
  should belong to (the caller's first membership).
* :func:`link_project_inputs` — non-fatally links documents and standards to
  a newly created project.

The router remains as a thin dispatcher; this module contains the
framework-agnostic logic that can be unit-tested without a running FastAPI app.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.membership_service import MembershipService
    from app.services.projects_service import ProjectsService

logger = logging.getLogger(__name__)


class ProjectOrchestratorService:
    """Static helpers for project orchestration logic."""

    @staticmethod
    def owned_project_ids(
        project_ids: list[int],
        user_id: str,
        is_superadmin: bool,
        service: "ProjectsService",
        memberships: "MembershipService",
        can_access_fn: object,
    ) -> list[int]:
        """Filter *project_ids* to ones the caller may act on.

        A superadmin may act on all of them; everyone else only those they can
        reach via the ``can_access_project`` predicate.

        Args:
            project_ids: Candidate project primary keys.
            user_id: The requesting user's UUID.
            is_superadmin: Whether the user has platform-wide admin rights.
            service: The projects persistence service.
            memberships: The membership persistence service.
            can_access_fn: Callable ``(row, user_id, memberships) -> bool`` —
                the same predicate the access dependency uses.

        Returns:
            The subset of *project_ids* the caller is allowed to act on.
        """
        if is_superadmin:
            return project_ids
        owned = []
        for pid in project_ids:
            row = service.get_project(pid)
            if row and can_access_fn(row, user_id, memberships):
                owned.append(pid)
        return owned

    @staticmethod
    def primary_organization_id(
        user_id: str,
        memberships: "MembershipService",
    ) -> int:
        """Return the organization a newly created project should belong to.

        Raises:
            fastapi.HTTPException: 400 if the caller has no organization.
        """
        from fastapi import HTTPException, status

        org_ids = memberships.org_ids_for_user(user_id)
        if not org_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account is not a member of any organization.",
            )
        return next(iter(org_ids))

    @staticmethod
    def link_project_inputs(
        service: "ProjectsService",
        project_id: int,
        *,
        document_ids: list[int],
        standards_codes: list[str],
    ) -> None:
        """Link the wizard's chosen documents and standards to a new project.

        Deliberately non-fatal.  The project row already exists by the time
        this runs, and handing the caller a 500 would leave them with a created
        project and an error page.  A failure to link is logged and the project
        is returned successfully.
        """
        if document_ids:
            try:
                service.link_library_documents(project_id, document_ids)
            except Exception:
                logger.exception("Could not link documents project_id=%d", project_id)

        if standards_codes:
            try:
                service.set_standards_for_project(project_id, standards_codes)
            except Exception:
                logger.exception("Could not link standards project_id=%d", project_id)
