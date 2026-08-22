"""Analysis and enhancement services separated by pipeline ownership.

This keeps the read-only compliance analysis lifecycle distinct from any model
enhancement workflow. The analysis service returns immutable results for the
current model, while the enhancement service plans changes against a new model
version without mutating the original IFC source.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Protocol


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
            element_id = str(
                getattr(element, "GlobalId", None)
                or getattr(element, "global_id", None)
                or getattr(element, "id", "unknown")
            )
            rows.append(
                {
                    "guid": element_id,
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


class EnhancementArtifactStorage(Protocol):
    """Storage operations required by the enhancement pipeline."""

    def materialize_local_path(self, reference: str) -> Path | None:
        """Materialize an immutable source artifact for local processing."""

    def save_upload(self, filename: str, content: bytes, subdir: str) -> str:
        """Persist a generated artifact and return its durable reference."""


class ModelLineageLedger(Protocol):
    """Persistence operations required to record model lineage."""

    def record(
        self,
        *,
        project_id: int,
        source_reference: str,
        output_reference: str,
        version: int,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        """Record one immutable source-to-output enhancement edge."""


class EnhancementService:
    """Plan and execute enhancements against a new model version."""

    def __init__(
        self,
        *,
        storage: EnhancementArtifactStorage | None = None,
        lineage_ledger: ModelLineageLedger | None = None,
        improver: Callable[[str, str], dict[str, Any]] | None = None,
    ) -> None:
        """Initialize optional execution dependencies for explicit injection."""
        self._storage = storage
        self._lineage_ledger = lineage_ledger
        self._improver = improver

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

    def execute(self, *, project_id: int, source_reference: str, version: int) -> dict[str, Any]:
        """Generate, store, and ledger a new IFC version without changing its source."""
        if version < 1:
            raise ValueError("version must be greater than zero")
        if self._storage is None or self._lineage_ledger is None or self._improver is None:
            raise RuntimeError("enhancement execution dependencies are not configured")

        source_path = self._storage.materialize_local_path(source_reference)
        if source_path is None:
            raise FileNotFoundError(f"Unable to materialize source IFC: {source_reference}")

        with TemporaryDirectory(prefix="bim-guard-enhancement-") as temp_dir:
            output_name = f"{source_path.stem}_v{version}.ifc"
            output_path = Path(temp_dir) / output_name
            summary = self._improver(str(source_path), str(output_path))
            output_reference = self._storage.save_upload(
                output_name,
                output_path.read_bytes(),
                f"enhancements/{project_id}",
            )

        lineage = self._lineage_ledger.record(
            project_id=project_id,
            source_reference=source_reference,
            output_reference=output_reference,
            version=version,
            summary=summary,
        )
        return {
            "pipeline": "enhancement",
            "project_id": project_id,
            "version": version,
            "source_reference": source_reference,
            "output_reference": output_reference,
            "summary": summary,
            "lineage": lineage,
        }


def run_compliance_analysis(elements: list[Any], *, service: AnalysisService | None = None) -> dict[str, Any]:
    """Explicit read-only Phase 1 analysis entry point."""
    analysis_service = service or AnalysisService()
    return analysis_service.run(elements)


def enhance_model(
    elements: list[Any],
    *,
    changes: dict[str, Any] | None = None,
    version: int = 1,
    service: EnhancementService | None = None,
) -> dict[str, Any]:
    """Explicit versioned enhancement entry point for Phase 1 model improvement work."""
    enhancement_service = service or EnhancementService()
    return enhancement_service.plan(elements, changes=changes, version=version)


def execute_model_enhancement(
    *,
    project_id: int,
    source_reference: str,
    version: int,
    service: EnhancementService | None = None,
) -> dict[str, Any]:
    """Execute the production enhancement pipeline with repository dependencies."""
    if service is None:
        from app.modules.module2_ifc_read.ifc_quality.improver import improve_ifc_file
        from app.services.model_lineage import SupabaseModelLineageRepository
        from app.services.object_storage import ObjectStorage

        service = EnhancementService(
            storage=ObjectStorage(),
            lineage_ledger=SupabaseModelLineageRepository(),
            improver=improve_ifc_file,
        )
    return service.execute(
        project_id=project_id,
        source_reference=source_reference,
        version=version,
    )
