"""Analysis and enhancement services separated by pipeline ownership.

This keeps the read-only compliance analysis lifecycle distinct from any model
enhancement workflow. The analysis service returns immutable results for the
current model, while the enhancement service plans changes against a new model
version without mutating the original IFC source.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Protocol
from uuid import NAMESPACE_URL, uuid5


@dataclass(frozen=True)
class AuditIssue:
    """Immutable compliance finding emitted by the audit pipeline."""

    id: str
    element_id: str
    rule_id: str
    title: str
    band: str
    score: float
    mechanism: str
    description: str
    mitigation: str
    details: dict[str, Any]


class AnalysisService:
    """Run-only pipeline for compliance assessment and reporting."""

    def __init__(
        self,
        *,
        evaluator: Callable[[list[Any]], list[dict[str, Any]]] | None = None,
    ) -> None:
        """Initialize the read-only evaluator dependency."""
        self._evaluator = evaluator

    def run(
        self,
        elements: list[Any],
        *,
        run_id: str = "BGR-AUDIT",
        source_path: Path | None = None,
    ) -> dict[str, Any]:
        """Evaluate immutable input elements and return rows, issues, and BCF topics."""
        evaluator = self._evaluator
        if evaluator is None:
            from app.modules.module4_comparator.compliance_runner import run_compliance_checks

            evaluator = run_compliance_checks

        source_hash = self._file_sha256(source_path) if source_path is not None else None
        try:
            from app.services.corrosion_rule_catalog import reload_all_catalogs

            reload_all_catalogs()
        except Exception:
            pass
        rows = evaluator(elements)
        if source_path is not None and self._file_sha256(source_path) != source_hash:
            raise RuntimeError("Audit pipeline modified the source IFC file")
        issues = self._build_issues(rows, run_id=run_id)
        return {
            "pipeline": "audit",
            "element_count": len(rows),
            "results": rows,
            "issues": [asdict(issue) for issue in issues],
            "bcf_topics": [self._to_bcf_topic(issue) for issue in issues],
            "source_sha256": source_hash,
        }

    @staticmethod
    def _file_sha256(path: Path) -> str:
        """Return the SHA-256 digest of an audit source file."""
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _build_issues(rows: list[dict[str, Any]], *, run_id: str) -> tuple[AuditIssue, ...]:
        """Convert evaluator rows into immutable per-mechanism audit findings."""
        from app.modules.module4_comparator.issue_adapter import (
            IssueIdAllocator,
            issues_from_path_a,
        )

        mutable_issues = issues_from_path_a(
            rows,
            id_allocator=IssueIdAllocator(run_id),
            include_low=False,
        )
        return tuple(
            AuditIssue(
                id=issue.id,
                element_id=issue.element_id,
                rule_id=issue.rule_id,
                title=issue.title,
                band=issue.band.value,
                score=issue.score,
                mechanism=issue.mechanism,
                description=issue.description or "",
                mitigation=issue.mitigation,
                details=dict(issue.metadata),
            )
            for issue in mutable_issues
        )

    @staticmethod
    def _to_bcf_topic(issue: AuditIssue) -> dict[str, Any]:
        """Return a deterministic BCF-compatible topic payload for one finding."""
        description = f"{issue.description}\n\nElementGUID: {issue.element_id}"
        return {
            "guid": str(uuid5(NAMESPACE_URL, f"bim-guard:{issue.id}:{issue.element_id}")),
            "title": issue.title,
            "description": description,
            "type": "Error" if issue.band in {"critical", "high"} else "Warning",
            "status": "Open",
            "priority": issue.band,
            "element_guid": issue.element_id,
            "rule_id": issue.rule_id,
            "position_mm": issue.details.get("position_mm"),
        }

    def include_rule_results(
        self,
        audit_result: dict[str, Any],
        rule_results: list[dict[str, Any]],
        *,
        run_id: str,
    ) -> dict[str, Any]:
        """Return a new audit result containing DB-backed property-rule failures."""
        rule_issues: list[AuditIssue] = []
        issue_number = 0
        for rule in rule_results:
            if rule.get("status") != "FAIL":
                continue
            for failure in rule.get("failures", []):
                issue_number += 1
                severity = str(rule.get("severity") or "recommended").lower()
                band = "high" if severity == "mandatory" else "medium"
                rule_id = str(rule.get("rule_ref") or "DB-RULE")
                element_id = str(failure.get("guid") or "unknown")
                rule_issues.append(
                    AuditIssue(
                        id=f"RULE-{issue_number:04d}",
                        element_id=element_id,
                        rule_id=rule_id,
                        title=f"[{rule_id}] {str(rule.get('rule_desc') or '')[:80]}",
                        band=band,
                        score=1.0,
                        mechanism="IDS property validation",
                        description=str(failure.get("reason") or "Property rule failed"),
                        mitigation="Correct the IFC property and re-run the audit.",
                        details={
                            "run_id": run_id,
                            "property_name": rule.get("property_name"),
                            "target": rule.get("target"),
                            "severity": severity,
                            "position_mm": failure.get("position_mm"),
                        },
                    )
                )

        existing_issues = list(audit_result.get("issues") or [])
        existing_topics = list(audit_result.get("bcf_topics") or [])
        return {
            **audit_result,
            "issues": existing_issues + [asdict(issue) for issue in rule_issues],
            "bcf_topics": existing_topics + [self._to_bcf_topic(issue) for issue in rule_issues],
        }


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

    def find_by_source_sha256(
        self, project_id: int, source_sha256: str
    ) -> dict[str, Any] | None:
        """Return the persisted enhancement for identical source content."""

    def allocate_next_version(self, project_id: int) -> int:
        """Atomically reserve and return the next project model version."""

    def record(
        self,
        *,
        project_id: int,
        source_reference: str,
        source_sha256: str,
        source_version: int,
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

    def plan(
        self, elements: list[Any], *, changes: dict[str, Any] | None = None, version: int = 1
    ) -> dict[str, Any]:
        """Produce a planned enhancement set without mutating the input model."""
        effective_changes = changes or {}
        items: list[dict[str, Any]] = []
        for element in elements:
            element_id = str(
                getattr(element, "GlobalId", None)
                or getattr(element, "global_id", None)
                or getattr(element, "id", "unknown")
            )
            items.append({
                "element_id": element_id,
                "changes": dict(effective_changes),
            })
        return {
            "pipeline": "enhancement",
            "version": version,
            "items": items,
        }

    def execute(self, *, project_id: int, source_reference: str) -> dict[str, Any]:
        """Generate, store, and ledger a new IFC version without changing its source."""
        if self._storage is None or self._lineage_ledger is None or self._improver is None:
            raise RuntimeError("enhancement execution dependencies are not configured")

        source_path = self._storage.materialize_local_path(source_reference)
        if source_path is None:
            raise FileNotFoundError(f"Unable to materialize source IFC: {source_reference}")

        source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        existing = self._lineage_ledger.find_by_source_sha256(project_id, source_sha256)
        if existing is not None:
            return {
                "pipeline": "enhancement",
                "project_id": project_id,
                "version": int(existing.get("version") or 0),
                "source_reference": str(existing.get("source_reference") or source_reference),
                "source_sha256": source_sha256,
                "output_reference": str(existing.get("output_reference") or ""),
                "summary": dict(existing.get("summary") or {}),
                "lineage": existing,
                "reused": True,
            }

        version = self._lineage_ledger.allocate_next_version(project_id)
        with TemporaryDirectory(prefix="bim-guard-enhancement-") as temp_dir:
            output_name = f"{source_path.stem}_v{version}.ifc"
            output_path = Path(temp_dir) / output_name
            summary = self._sanitize_summary(
                self._improver(str(source_path), str(output_path)),
                output_name=output_name,
            )
            output_reference = self._storage.save_upload(
                output_name,
                output_path.read_bytes(),
                f"enhancements/{project_id}",
            )

        lineage = self._lineage_ledger.record(
            project_id=project_id,
            source_reference=source_reference,
            source_sha256=source_sha256,
            source_version=0,
            output_reference=output_reference,
            version=version,
            summary=summary,
        )
        return {
            "pipeline": "enhancement",
            "project_id": project_id,
            "version": version,
            "source_reference": source_reference,
            "source_sha256": source_sha256,
            "output_reference": output_reference,
            "summary": summary,
            "lineage": lineage,
            "reused": False,
        }

    @staticmethod
    def _sanitize_summary(summary: dict[str, Any], *, output_name: str) -> dict[str, Any]:
        """Remove ephemeral local paths before persisting enhancement metadata."""
        sanitized = dict(summary)
        improvements = sanitized.get("improvements")
        if isinstance(improvements, list):
            sanitized["improvements"] = [
                str(item)
                for item in improvements
                if not str(item).startswith("Improved file saved:")
            ]
        sanitized["generated_filename"] = output_name
        return sanitized


class PipelineOrchestratorService:
    """Service facade wrapping workflow execution for UI routes."""

    @staticmethod
    def orchestrate_workflow(
        project_id: int = 1,
        doc_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute complete application workflow and return summary payload."""
        from app.modules.orchestrator import BIMGuard_App

        workflow = BIMGuard_App()
        return workflow.orchestrate_workflow(
            project_id=project_id, doc_ids=doc_ids or [], **kwargs
        )

    @staticmethod
    def get_dashboard_stats() -> dict[str, Any]:
        """Return system-wide dashboard counts and compliance metrics."""
        from app.modules.orchestrator import BIMGuard_App

        workflow = BIMGuard_App()
        return workflow.run_dashboard()

    @staticmethod
    def export_bcf(report_data: dict[str, Any], output_path: str | Path) -> str:
        """Export BCF file from report payload via service boundary."""
        from app.modules.module5_reporter import Module5_Reporter

        reporter = Module5_Reporter()
        return reporter.generate_bcf(report_data, output_path=output_path)

    @staticmethod
    def export_csv(report_data: dict[str, Any], output_path: str | Path) -> str:
        """Export CSV file from report payload via service boundary."""
        from app.modules.module5_reporter import Module5_Reporter

        reporter = Module5_Reporter()
        return reporter.generate_csv(report_data, output_path=output_path)

    @staticmethod
    def iter_csv_summary(results: list[dict[str, Any]]):
        """Stream CSV compliance summary rows."""
        from app.modules.module5_reporter import Module5_Reporter

        return Module5_Reporter().iter_csv_summary(results)

    @staticmethod
    def generate_bcf_zip(results: list[dict[str, Any]]) -> bytes:
        """Generate BCF zip file bytes from compliance results."""
        from app.modules.module5_reporter import Module5_Reporter

        return Module5_Reporter().generate_bcf_zip(results)

    @staticmethod
    def get_ifc_graph(
        ifc_file_path: str | Path, violations: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Generate element hierarchy graph payload."""
        from app.modules.module2_ifc_read.ifc_graph import render_ifc_graph

        return render_ifc_graph(ifc_file_path, violations=violations)

    @staticmethod
    def run_comparator_check(elements: list[Any], rules: list[Any]) -> list[dict[str, Any]]:
        """Run comparator rule evaluation against element properties."""
        from app.modules.module4_comparator import Module4_Comparator

        comparator = Module4_Comparator()
        return comparator.check_compliance(elements, rules)

    @staticmethod
    def validate_metadata(extraction: dict[str, Any]) -> list[dict[str, Any]]:
        """Validate metadata extraction payload via comparator."""
        from app.modules.module4_comparator import Module4_Comparator

        return Module4_Comparator().validate_metadata(extraction)

    @staticmethod
    def render_visual_report(compliance: list[dict[str, Any]]) -> dict[str, Any]:
        """Render visual report summary via reporter module."""
        from app.modules.module5_reporter import Module5_Reporter

        return Module5_Reporter().render_visual_report(compliance)

    @staticmethod
    def export_phase6(
        summary_payload: dict[str, Any], fmt: str, source_reference: str = ""
    ) -> tuple[bytes, str, str]:
        """Export Phase 6 summary data into requested file format."""
        from app.modules.phase_6.phase_6e_export import export

        return export(summary_payload, fmt, source_reference=source_reference)


def run_compliance_analysis(
    elements: list[Any],
    *,
    run_id: str = "BGR-AUDIT",
    source_path: Path | None = None,
    service: AnalysisService | None = None,
) -> dict[str, Any]:
    """Explicit read-only Phase 1 analysis entry point."""
    analysis_service = service or AnalysisService()
    return analysis_service.run(elements, run_id=run_id, source_path=source_path)


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
    )
