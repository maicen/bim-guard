<<<<<<< HEAD
"""
Compliance orchestrator: coordinates corrosion engines and Path B (MM/XM) via feature flags.

Entry point: orchestrate_workflow(elements, run_id)
- Runs Path A (GC/CC/MC) always
- Runs MM-001 if FEATURE_PATH_B_MM is enabled
- Runs XM-001 if FEATURE_PATH_B_XM is enabled
- Projects findings onto per-element dicts for UI
"""

import os
from typing import Any

from app.modules.module4_comparator.compliance_runner import run_compliance_checks
from app.modules.module4_comparator.issue_adapter import (
    issues_from_path_a,
    path_a_view,
    IssueIdAllocator,
)
from app.modules.module4_comparator.material_media import load_rule_pack as load_mm_pack, compare as compare_mm
from app.modules.module4_comparator.cross_material import load_rule_pack as load_xm_pack, compare as compare_xm


def orchestrate_workflow(elements: list[Any], run_id: str = "BGR-2026") -> list[dict]:
    """
    Run the full compliance pipeline: Path A + conditional MM-001/XM-001.
    
    Args:
        elements: IFC elements to check (ifcopenshell.entity_instance objects).
        run_id: Run identifier for issue numbering (default "BGR-2026").
    
    Returns:
        List of dicts, one per element, with Path A results and optional Path B findings.
    """
    # Read feature flags from environment (read at call time to avoid config DB dependency)
    feature_mm = os.environ.get("FEATURE_PATH_B_MM", "0") == "1"
    feature_xm = os.environ.get("FEATURE_PATH_B_XM", "0") == "1"
    
    # ========== PATH A: Galvanic / Crevice / MIC ==========
    path_a_results = run_compliance_checks(elements)
    
    # ========== PATH B SETUP ==========
    id_allocator = IssueIdAllocator(run_id)
    path_b_issues = []
    
    # ========== MM-001: Material-Media Compatibility ==========
    if feature_mm:
        try:
            mm_pack = load_mm_pack()
            for element in elements:
                mm_issues = compare_mm(element, rule_pack=mm_pack, id_allocator=id_allocator)
                path_b_issues.extend(mm_issues)
        except Exception as e:
            # Log but don't crash; MM-001 offline fallback
            print(f"MM-001 error: {e}")
    
    # ========== XM-001: Cross-Material Galvanic ==========
    if feature_xm:
        try:
            xm_pack = load_xm_pack()
            for element in elements:
                xm_issues = compare_xm(element, rule_pack=xm_pack, id_allocator=id_allocator)
                path_b_issues.extend(xm_issues)
        except Exception as e:
            # Log but don't crash; XM-001 requires DB
            print(f"XM-001 error: {e}")
    
    # ========== PROJECT: Path A + Path B onto UI dicts ==========
    # Convert Path A results to Issues, then project back with Path B findings merged
    path_a_issues = issues_from_path_a(path_a_results, id_allocator=id_allocator, include_low=False)
    all_issues = path_a_issues + path_b_issues
    
    # Project onto the per-element spine
    output = path_a_view(all_issues, path_a_results)
    
    return output
=======
"""Compliance Orchestrator - wires runner, tracker, and BCF exporter."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from app.logging_config import get_logger
from app.modules.module4_comparator.compliance_runner import run_compliance
from app.modules.module4_comparator.issue_schema import Issue, RiskBand
from app.modules.module4_comparator.issue_tracker import IssueTracker
from app.services.bcf_exporter import BCFExporter

logger = get_logger(__name__)


class ComplianceOrchestrator:
    """Orchestrates complete compliance pipeline."""

    def __init__(self):
        self._tracker = IssueTracker()
        self._exporter = BCFExporter()
        self._last_run_issues = []

    def run_and_log_compliance(self, elements, run_name="Compliance Run", export_bcf_path=None):
        """Execute full pipeline: run -> convert -> log -> export."""
        logger.info("Starting compliance run name=%s elements=%d", run_name, len(elements))
        try:
            raw_results = run_compliance(elements)
        except Exception:
            logger.exception("Compliance runner failed name=%s", run_name)
            raise
        issues = self._results_to_issues(raw_results, run_name)
        self._log_issues_to_tracker(issues)
        bcf_path = None
        if export_bcf_path:
            bcf_path = self._export_to_bcf(issues, export_bcf_path)
        self._last_run_issues = issues
        summary = self._summarize_issues(issues)
        logger.info(
            "Compliance run complete name=%s raw_results=%d issues=%d bcf_exported=%s",
            run_name,
            len(raw_results),
            len(issues),
            bcf_path is not None,
        )
        return {
            "issues": issues,
            "run_name": run_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "bcf_path": bcf_path,
        }

    def _results_to_issues(self, raw_results, run_name):
        """Convert raw compliance results to Issue objects."""
        issues = []
        for i, result in enumerate(raw_results, start=1):
            issue_id = f"BGR-{i:04d}"
            overall_band_str = result.get("overall_band", "LOW")
            overall_score = float(result.get("overall_score", 0.0))
            band_map = {
                "CRITICAL": RiskBand.CRITICAL,
                "HIGH": RiskBand.HIGH,
                "MEDIUM": RiskBand.MEDIUM,
                "LOW": RiskBand.LOW,
            }
            band = band_map.get(overall_band_str, RiskBand.LOW)
            dominant_mechanism = result.get("dominant_mechanism", "Unknown")
            if dominant_mechanism == "Galvanic":
                mechanism_id = "GC-001"
            elif dominant_mechanism == "Crevice":
                mechanism_id = "CC-001"
            elif dominant_mechanism == "MIC":
                mechanism_id = "MC-001"
            else:
                mechanism_id = "UNKNOWN"
            rule_id = f"{mechanism_id}.01"
            metadata = {
                "galvanic_score": result.get("galvanic_score", 0.0),
                "crevice_score": result.get("crevice_score", 0.0),
                "mic_score": result.get("mic_score", 0.0),
            }
            citations = []
            if dominant_mechanism == "Galvanic":
                citations.append({"standard": "NACE SP0169-2013", "clause": "Table 1"})
            elif dominant_mechanism == "Crevice":
                citations.append({"standard": "NACE SP0169-2013", "clause": "Section 5.2"})
            elif dominant_mechanism == "MIC":
                citations.append({"standard": "ISO 14225:2016", "clause": "Section 4"})
            issue = Issue(
                id=issue_id,
                element_id=result.get("guid", f"elem-{i}"),
                rule_id=rule_id,
                title=f"{mechanism_id} on {result.get('name', 'Unknown')}",
                description=result.get("description", ""),
                band=band,
                score=overall_score,
                mechanism=f"{mechanism_id} {dominant_mechanism.lower()}",
                mitigation=result.get("mitigation", ""),
                assignee_role=self._infer_assignee_role(mechanism_id),
                status="open",
                created_at=datetime.now(timezone.utc).isoformat() + "Z",
                updated_at=datetime.now(timezone.utc).isoformat() + "Z",
                metadata=metadata,
                citations=citations,
            )
            issues.append(issue)
        return issues

    def _infer_assignee_role(self, mechanism_id):
        """Infer which engineer should review this issue."""
        if mechanism_id == "GC-001":
            return "Materials Engineer"
        elif mechanism_id == "CC-001":
            return "Mechanical Engineer"
        elif mechanism_id == "MC-001":
            return "Process Engineer"
        else:
            return "Lead Engineer"

    def _log_issues_to_tracker(self, issues):
        """Log issues to database."""
        results = []
        for issue in issues:
            result = {
                "global_id": issue.element_id,
                "element_type": issue.rule_id.split(".")[0],
                "system_type": "MEP System",
                "material": issue.metadata.get("environment", "Unknown"),
                "risk_band": issue.band.value.upper(),
                "composite_score": issue.score,
            }
            results.append(result)
        summary = self._tracker.record_run(
            results=results,
            author="BIMGUARD-AI",
            run_comment="Compliance run via ComplianceOrchestrator",
        )
        self._tracker._save()
        logger.debug("Compliance issues recorded issues=%d", len(issues))

    def _export_to_bcf(self, issues, output_path):
        """Export issues to BCF format."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        markup_xml = self._exporter.generate_bcf_markup_xml(issues)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markup_xml)
        logger.info("BCF export complete path=%s issues=%d", output_path, len(issues))
        return output_path

    def _summarize_issues(self, issues):
        """Generate summary statistics."""
        return {
            "total": len(issues),
            "critical": sum(1 for i in issues if i.band == RiskBand.CRITICAL),
            "high": sum(1 for i in issues if i.band == RiskBand.HIGH),
            "medium": sum(1 for i in issues if i.band == RiskBand.MEDIUM),
            "low": sum(1 for i in issues if i.band == RiskBand.LOW),
        }

    def get_last_run_issues(self):
        """Retrieve issues from last compliance run."""
        return self._last_run_issues
>>>>>>> b682e7f622e1e2ce2c17b794a989d5f0829a433d
