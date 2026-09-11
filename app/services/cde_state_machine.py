"""
CDE State Machine Enforcement Engine.

Controls transitions across standard ISO 19650 CDE workflow states:
- WIP -> SHARED: Requires 100% ISO container naming pass, 0 critical compliance/clash violations, and 100% IDS check pass.
- SHARED -> PUBLISHED: Requires explicit lead appointed party approval.
- PUBLISHED -> ARCHIVED: Standard archival lifecycle.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from app.modules.contracts import CDEState
from app.modules.document_parsing.iso_validator import ISO19650Validator
from app.services.model_lineage import SupabaseModelLineageRepository
from app.services.naming_config_service import NamingConfigService
from app.services.projects_service import ProjectsService
from app.utils import invalidate_cache, now_iso_utc


def _validate_container_filename(filename: str, *, project_id: int | None, naming_config: NamingConfigService) -> tuple[bool, list[str]]:
    """Validate a container filename, preferring a project's configured naming convention.

    Falls back to the default ISO 19650 7-field regex (`ISO19650Validator`)
    when the project has no saved `project_naming_config` row, or when
    `project_id` is unknown -- e.g. a bare filename check with no project
    context. This is what actually makes a project's naming-config-API
    choice the one Gate 1 enforces, instead of Gate 1 always enforcing the
    default scheme regardless of what a project configured.
    """
    if project_id is not None:
        config = naming_config.get_for_project(project_id)
        if config.get("is_configured"):
            is_valid, _fields, errors = naming_config.validate_name(config, filename)
            return is_valid, errors

    result = ISO19650Validator.validate_filename(filename)
    return result.is_valid, result.errors


class TransitionResult(NamedTuple):
    allowed: bool
    reason: str
    target_state: CDEState


class CDEStateMachine:
    """Enforces ISO 19650 CDE state transition rules and audit logging."""

    def __init__(
        self,
        *,
        projects_service: ProjectsService | None = None,
        lineage_repo: SupabaseModelLineageRepository | None = None,
        naming_config_service: NamingConfigService | None = None,
    ) -> None:
        self._projects = projects_service if projects_service is not None else ProjectsService()
        self._lineage = lineage_repo if lineage_repo is not None else SupabaseModelLineageRepository()
        self._naming_config = naming_config_service if naming_config_service is not None else NamingConfigService()

    @staticmethod
    def evaluate_transition(
        current_state: str | CDEState,
        target_state: str | CDEState,
        *,
        filename: str = "",
        project_id: int | None = None,
        naming_config_service: NamingConfigService | None = None,
        critical_issues_count: int = 0,
        ids_check_passed: bool = True,
        is_approved: bool = False,
        approved_by: str = "",
    ) -> TransitionResult:
        """Evaluate whether a requested CDE state transition satisfies ISO 19650 gateway rules.

        `project_id` lets the WIP -> SHARED filename check enforce a
        project's own configured naming convention (`project_naming_config`)
        when one has been set up, instead of always enforcing the default
        7-field scheme regardless of what the project chose.
        """
        cur = CDEState(current_state) if isinstance(current_state, str) else current_state
        tgt = CDEState(target_state) if isinstance(target_state, str) else target_state

        if cur == tgt:
            return TransitionResult(allowed=True, reason="State unchanged", target_state=tgt)

        # WIP -> SHARED Gateway
        if cur == CDEState.WIP and tgt == CDEState.SHARED:
            if filename:
                is_valid, errors = _validate_container_filename(
                    filename,
                    project_id=project_id,
                    naming_config=naming_config_service or NamingConfigService(),
                )
                if not is_valid:
                    return TransitionResult(
                        allowed=False,
                        reason=f"ISO 19650 container naming validation failed: {'; '.join(errors)}",
                        target_state=tgt,
                    )
            if critical_issues_count > 0:
                return TransitionResult(
                    allowed=False,
                    reason=f"Cannot transition to SHARED: {critical_issues_count} critical compliance issues unresolved.",
                    target_state=tgt,
                )
            if not ids_check_passed:
                return TransitionResult(
                    allowed=False,
                    reason="Cannot transition to SHARED: buildingSMART IDS / LOIN verification failed.",
                    target_state=tgt,
                )
            return TransitionResult(allowed=True, reason="WIP to SHARED requirements satisfied.", target_state=tgt)

        # SHARED -> PUBLISHED Gateway
        if cur == CDEState.SHARED and tgt == CDEState.PUBLISHED:
            if not is_approved and not approved_by.strip():
                return TransitionResult(
                    allowed=False,
                    reason="Cannot transition to PUBLISHED: Explicit Lead Appointed Party approval is required.",
                    target_state=tgt,
                )
            return TransitionResult(allowed=True, reason="Lead Appointed Party approval granted for PUBLISHED.", target_state=tgt)

        # SHARED/PUBLISHED -> ARCHIVED Gateway
        if tgt == CDEState.ARCHIVED:
            return TransitionResult(allowed=True, reason="Transition to ARCHIVED permitted.", target_state=tgt)

        # Allow rollback to WIP from SHARED if needed for remediation
        if cur == CDEState.SHARED and tgt == CDEState.WIP:
            return TransitionResult(allowed=True, reason="Returned to WIP for revision/remediation.", target_state=tgt)

        return TransitionResult(
            allowed=False,
            reason=f"Invalid state transition requested from {cur.value} to {tgt.value}",
            target_state=tgt,
        )

    def transition_project(
        self,
        project_id: int,
        target_state: str | CDEState,
        *,
        actor: str = "Lead Appointed Party",
        filename: str = "",
        critical_issues_count: int = 0,
        ids_check_passed: bool = True,
        approved_by: str = "",
    ) -> dict[str, Any]:
        """Execute a CDE state transition for a project record, recording immutable lineage."""
        project = self._projects.get_project(project_id)
        if not project:
            raise ValueError(f"Project with ID {project_id} not found")

        current_state = project.get("cde_state") or CDEState.WIP
        if not filename and project.get("ifc_file_path"):
            filename = project["ifc_file_path"]

        res = self.evaluate_transition(
            current_state,
            target_state,
            filename=filename,
            project_id=project_id,
            naming_config_service=self._naming_config,
            critical_issues_count=critical_issues_count,
            ids_check_passed=ids_check_passed,
            approved_by=approved_by or project.get("cde_approved_by", ""),
            is_approved=bool(approved_by or project.get("cde_approved_by")),
        )

        if not res.allowed:
            raise ValueError(res.reason)

        tgt = res.target_state.value
        updates: dict[str, Any] = {"cde_state": tgt, "updated_at": now_iso_utc()}
        if approved_by:
            updates["cde_approved_by"] = approved_by
            updates["cde_approved_at"] = now_iso_utc()

        # Update projects table. This writes through the raw adapter rather
        # than ProjectsService.update_project(), so it must invalidate the
        # service-level @cache_db_query cache on get_project() itself --
        # the adapter-level cache invalidation .update() already does is a
        # separate cache keyed differently (bimguard:projects:item:... vs
        # adapter:projects:get:...) and does not cover it. Without this, the
        # get_project() call below can return the pre-transition row.
        self._projects._projects.update(updates=updates, pk_values=project_id)
        invalidate_cache(f"bimguard:projects:item:project_id={project_id}")
        invalidate_cache("bimguard:projects:list")

        # Audit Log CDE State Transition
        self._lineage.record_cde_transition(
            project_id=project_id,
            from_state=str(current_state),
            to_state=tgt,
            actor=actor,
            metrics={
                "critical_issues_count": critical_issues_count,
                "ids_check_passed": ids_check_passed,
                "approved_by": approved_by,
                "reason": res.reason,
            },
        )

        return self._projects.get_project(project_id) or {}
