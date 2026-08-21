"""Analysis and enhancement services separated by pipeline ownership.

This keeps the read-only compliance analysis lifecycle distinct from any model
enhancement workflow. The analysis service returns immutable results for the
current model, while the enhancement service plans changes against a new model
version without mutating the original IFC source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisRunResult:
    """Immutable result from a read-only compliance analysis pass."""

    element_id: str
    band: str
    score: float
    mechanism: str
    details: dict[str, Any]


class AnalysisService:
    """Run-only pipeline for compliance assessment and reporting."""

    def run(self, elements: list[Any]) -> dict[str, Any]:
        """Return analysis output with the immutable result payload shape."""
        rows: list[dict[str, Any]] = []
        for element in elements:
            info = getattr(element, "get_info", lambda: {})()
            element_id = str(getattr(element, "GlobalId", None) or getattr(element, "global_id", None) or getattr(element, "id", "unknown"))
            rows.append(
                {
                    "element_id": element_id,
                    "name": getattr(element, "Name", None) or getattr(element, "name", None) or "Unknown",
                    "band": "LOW",
                    "score": 0.0,
                    "mechanism": "GC-001",
                    "details": {
                        "material": info.get("material") or getattr(element, "material", ""),
                        "environment": info.get("environment") or getattr(element, "environment", ""),
                    },
                }
            )
        return {"pipeline": "analysis", "element_count": len(rows), "results": rows}


@dataclass(frozen=True)
class EnhancementPlanItem:
    """Versioned model enhancement request for a single element."""

    element_id: str
    changes: dict[str, Any]


class EnhancementService:
    """Explicit enhancement pipeline that plans changes for a new model version."""

    def plan(self, elements: list[Any], *, changes: dict[str, Any] | None = None, version: int = 1) -> dict[str, Any]:
        """Produce a planned enhancement set without mutating the input model."""
        effective_changes = changes or {}
        items: list[dict[str, Any]] = []
        for element in elements:
            element_id = str(getattr(element, "GlobalId", None) or getattr(element, "global_id", None) or getattr(element, "id", "unknown"))
            items.append({
                "element_id": element_id,
                "changes": dict(effective_changes),
            })
        return {
            "pipeline": "enhancement",
            "version": version,
            "items": items,
        }
