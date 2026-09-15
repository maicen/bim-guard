"""Append-only audit trail for sensitive mutations.

Records who did what, to what, and when -- the queryable record SOC 2 and
ISO 27001 both expect for access-control changes and destructive actions.
Callers record events at the API route layer (where the authenticated actor
and organization scope are already resolved) rather than inside domain
services, so a service method doesn't need to know whether it was invoked in
an auditable context. ``record`` never raises: a logging failure must not
block the mutation it's describing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.logging_config import get_logger
from app.services.db_adapters import DatabaseAdapter

logger = get_logger(__name__)


class AuditLogService:
    """Domain service for writing and reading the audit_log table."""

    def __init__(self, audit_log_repo: DatabaseAdapter):
        self._repo = audit_log_repo

    def record(
        self,
        *,
        actor_id: str,
        action: str,
        resource_type: str,
        actor_email: str | None = None,
        organization_id: int | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Append one audit entry. Never raises -- logs and swallows on failure."""
        try:
            self._repo.insert(
                {
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "actor_id": actor_id,
                    "actor_email": actor_email,
                    "organization_id": organization_id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": str(resource_id) if resource_id is not None else None,
                    "metadata": metadata or {},
                }
            )
        except Exception:
            logger.warning(
                "Failed to write audit log entry (action=%s resource_type=%s)",
                action,
                resource_type,
                exc_info=True,
            )

    def list_entries(
        self,
        *,
        organization_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return the most recent entries, optionally scoped to an organization."""
        rows = list(self._repo.rows)
        if organization_id is not None:
            rows = [r for r in rows if r.get("organization_id") == organization_id]
        rows.sort(key=lambda r: r.get("occurred_at") or "", reverse=True)
        return rows[:limit]
