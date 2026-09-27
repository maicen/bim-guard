"""Thin service layer extracted from ``app/api/rules.py``.

Currently owns:

* :func:`rule_response` — maps a raw ``rules`` table row to the
  ``RuleResponse`` contract.  The persistence layer stores the human-readable
  rule identifier under ``"reference"`` but the public contract exposes it as
  ``"rule_id"``, so bridging is needed; keeping that bridging in a dedicated
  service means it is testable without a running FastAPI app.

More helpers from the router may be migrated here in future iterations.
"""

from __future__ import annotations


class RuleFormatterService:
    """Static helpers for rule-response formatting."""

    @staticmethod
    def rule_response(row: dict) -> object:
        """Build a ``RuleResponse`` from a raw ``rules``-table row.

        The persistence layer stores the human-readable rule identifier under
        the ``"reference"`` column (see ``RuleService._rules`` schema);
        ``RuleResponse`` exposes it as ``"rule_id"`` for a clearer public
        contract, so it needs bridging here rather than relying on Pydantic to
        find a same-named key.

        Args:
            row: Raw mapping returned by ``RuleService`` or a Supabase query.

        Returns:
            A validated :class:`app.modules.contracts.RuleResponse` instance.
        """
        from app.modules.contracts import RuleResponse

        if not row.get("rule_id"):
            row = {**row, "rule_id": row.get("reference")}
        return RuleResponse(**row)
