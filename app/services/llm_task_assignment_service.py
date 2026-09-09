"""Service layer for an organization's per-task LLM model shortlists.

Each row names one model shortlisted for one task within one organization —
e.g. "org 3 may use claude-3.5-sonnet via provider instance 7 for
rule_extraction, and it's the default choice". This service owns
persistence and replace-the-whole-set semantics for a given
(organization_id, task_key) pair, mirroring the existing PUT
.../ruleset-grants convention in app/api/organizations.py. Task keys
themselves are owned by LLM_TASKS (app/modules/llm_providers/tasks.py), not
this service — a new task never requires editing this file.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.modules.llm_providers import LLM_TASKS, LLMTask
from app.services.db_adapters import DatabaseAdapter
from app.services.llm_provider_instances_service import LLMProviderInstancesService


class LLMTaskAssignmentService:
    """Domain service for reading/replacing an org's per-task model shortlists."""

    def __init__(
        self,
        assignments_repo: DatabaseAdapter,
        provider_instances_service: LLMProviderInstancesService,
    ):
        self._repo = assignments_repo
        self._provider_instances = provider_instances_service

    @staticmethod
    def list_tasks() -> list[LLMTask]:
        """Return every registered task a shortlist can be configured for."""
        return list(LLM_TASKS)

    def list_assignments(
        self, organization_id: int, task_key: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Retrieve an org's shortlisted rows, optionally filtered to one task."""
        rows = [
            r
            for r in self._repo.rows
            if int(r.get("organization_id") or 0) == organization_id
            and (task_key is None or r.get("task_key") == task_key)
        ]
        return sorted(rows, key=lambda r: int(r.get("id") or 0))

    def set_assignments(
        self,
        organization_id: int,
        task_key: str,
        models: list[dict[str, Any]],
        default_provider_instance_id: Optional[int] = None,
        default_model_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Replace the whole shortlist for (organization_id, task_key).

        Every `provider_instance_id` in *models* must belong to
        *organization_id* — never trusts a client-supplied instance id
        blindly, since a stray id could otherwise leak another
        organization's provider_instance_name into this org's responses.
        """
        clean_task_key = (task_key or "").strip()
        if not clean_task_key:
            raise ValueError("task_key is required.")
        if not any(t.key == clean_task_key for t in LLM_TASKS):
            valid = sorted(t.key for t in LLM_TASKS)
            raise ValueError(f"task_key must be one of {valid}.")

        seen: set[tuple[int, str]] = set()
        for model in models:
            instance_id = int(model["provider_instance_id"])
            model_id = str(model["model_id"]).strip()
            if not model_id:
                raise ValueError("Every shortlisted model needs a non-empty model_id.")
            if not self._provider_instances.get_instance(organization_id, instance_id):
                raise ValueError(
                    f"Provider instance {instance_id} does not belong to this organization."
                )
            key = (instance_id, model_id)
            if key in seen:
                raise ValueError(f"Model '{model_id}' is shortlisted more than once.")
            seen.add(key)

        default_key = None
        if default_provider_instance_id is not None and default_model_id:
            default_key = (int(default_provider_instance_id), default_model_id.strip())
            if default_key not in seen:
                raise ValueError("default model must be one of the shortlisted models.")

        # Delete-then-insert (not a diff/merge) so a shortlist that shrinks
        # to fewer models, or to zero, is expressed the same way as growing
        # one — the whole set is always exactly what this call passed.
        for row in self.list_assignments(organization_id, clean_task_key):
            self._repo.delete(row["id"])

        now = datetime.now(timezone.utc).isoformat()
        created: list[dict[str, Any]] = []
        for model in models:
            instance_id = int(model["provider_instance_id"])
            model_id = str(model["model_id"]).strip()
            payload = {
                "organization_id": organization_id,
                "task_key": clean_task_key,
                "provider_instance_id": instance_id,
                "model_id": model_id,
                "model_name": str(model.get("model_name") or model_id),
                "context_length": model.get("context_length"),
                "input_price_per_million": model.get("input_price_per_million"),
                "output_price_per_million": model.get("output_price_per_million"),
                "is_default": default_key == (instance_id, model_id),
                "created_at": now,
            }
            created.append(self._repo.insert(payload))
        return created
