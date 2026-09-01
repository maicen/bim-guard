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
from app.modules.module1_doc_parser.iso_validator import ISO19650Validator
from app.services.model_lineage import SupabaseModelLineageRepository
from app.services.projects_service import ProjectsService
from app.utils import now_iso_utc


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
    ) -> None:
        self._projects = projects_service if projects_service is not None else ProjectsService()
        self._lineage = lineage_repo if lineage_repo is not None else SupabaseModelLineageRepository()

    @staticmethod
    def evaluate_transition(
        current_state: str | CDEState,
        target_state: str | CDEState,
        *,
        filename: str = "",
        critical_issues_count: int = 0,
        ids_check_passed: bool = True,
        is_approved: bool = False,
        approved_by: str = "",
    ) -> TransitionResult:
        """Evaluate whether a requested CDE state transition satisfies ISO 19650 gateway rules."""
        cur = CDEState(current_state) if isinstance(current_state, str) else current_state
        tgt = CDEState(target_state) if isinstance(target_state, str) else target_state

        if cur == tgt:
            return TransitionResult(allowed=True, reason="State unchanged", target_state=tgt)

        # WIP -> SHARED Gateway
        if cur == CDEState.WIP and tgt == CDEState.SHARED:
            if filename:
                val = ISO19650Validator.validate_filename(filename)
                if not val.is_valid:
                    return TransitionResult(
                        allowed=False,
                        reason=f"ISO 19650 container naming validation failed: {'; '.join(val.errors)}",
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

        # Update projects table
        self._projects._projects.update(updates=updates, pk_values=project_id)

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
