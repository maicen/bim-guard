import os

from .module1_doc_reader import Module1_DocReader
from .module2_ifc_read import Module2_IFCRead
from .module3_rule_builder import Module3_RuleBuilder
from .module4_comparator import Module4_Comparator
from .module5_reporter import Module5_Reporter
from .ifc_parser import parse_ifc, generate_synthetic_elements
from .compliance_runner import run_compliance_checks
from .bcf_generator import issues_from_results, generate_bcf
from .cost_model import CostModel
from .issue_tracker import IssueTracker
from app.services.documents_service import DocumentService
from app.services.projects_service import ProjectsService
from app.services.rules_service import RuleService

# Resolved at import time: app/modules/../../.. → repo root / data/
_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)


def _normalise_results(raw: list) -> list:
    """Add field aliases expected by cost_model, bcf_generator, issue_tracker, and report_generator."""
    band_map = {"LOW": "Low", "MEDIUM": "Medium", "HIGH": "High", "CRITICAL": "Critical"}
    mech_map = {"galvanic": "GC", "crevice": "CC"}
    for r in raw:
        r["risk_band"]              = band_map.get(r.get("overall_band", "LOW"), "Low")
        r["composite_score"]        = r.get("overall_score", 0.0)
        r["global_id"]              = r.get("guid", "")
        r["mechanism"]              = mech_map.get(r.get("dominant_mechanism", "galvanic"), "GC")
        r["material_label"]         = r.get("material_a", "Unknown")
        r["recommended_mitigation"] = r.get("mitigation", "")
        r["element_type"]           = r.get("ifc_type", "")
        r["system_type"]            = r.get("system", "")
    return raw


class BIMGuard_App:
    """
    Workflow Orchestrator
    Manages the overall workflow connecting frontend requests to backend modules.
    """

    def __init__(self):
        self.doc_reader = Module1_DocReader()
        self.ifc_reader = Module2_IFCRead()
        self.rule_builder = Module3_RuleBuilder()
        self.comparator = Module4_Comparator()
        self.reporter = Module5_Reporter()
        self._projects_service = ProjectsService()
        self._documents_service = DocumentService()
        self._rules_service = RuleService()

    def run_dashboard(self) -> dict:
        """Return live counts for the dashboard stats."""
        return {
            "total_projects": self._projects_service.total_projects(),
            "total_documents": len(self._documents_service.list_documents()),
            "total_rules": len(self._rules_service.list_rules()),
        }

    def orchestrate_workflow(
        self,
        project_id: int,
        document_ids: list,
        include_openings: bool = True,
        include_spaces: bool = True,
        include_type_definitions: bool = False,
    ) -> dict:
        """Orchestrate the validation workflow across modules."""
        try:
            project = self._projects_service.get_project(project_id)
        except Exception:
            project = None
        if project is None:
            return {"error": f"Project {project_id} not found."}

        # Module 2: IFC parsing
        ifc_elements = []
        ifc_error = None
        ifc_totals = {}
        ifc_path = self._projects_service.resolve_ifc_file(project_id)
        if ifc_path:
            try:
                ifc_reader = Module2_IFCRead(ifc_path)
                ifc_elements = ifc_reader.extract_geometry()
                ifc_totals = ifc_reader.extract_summary_counts(
                    include_openings=include_openings,
                    include_spaces=include_spaces,
                    include_type_definitions=include_type_definitions,
                )
            except Exception as exc:
                ifc_error = str(exc)

        ifc_type_counts = {}
        for element in ifc_elements:
            element_type = element.get("type") or "Unknown"
            ifc_type_counts[element_type] = ifc_type_counts.get(element_type, 0) + 1

        # Module 1: Document text extraction from stored text in DB
        documents = []
        for doc_id in document_ids:
            try:
                doc = self._documents_service.get_document(int(doc_id))
            except Exception:
                continue
            extracted_text = doc.get("extracted_text") or ""
            sections = self.doc_reader.extract_text_sections(extracted_text)
            documents.append(
                {
                    "filename": doc.get("filename", ""),
                    "sections": sections,
                    "section_count": len(sections),
                }
            )

        # Module 3: Rule builder (stub — returns [])
        rules = self.rule_builder.generate_regex_from_text()

        # Module 4: Comparator (stub — returns [])
        violations = self.comparator.validate_metadata()

        # Module 5: Reporter (stub — returns "")
        report = self.reporter.render_visual_report()

        # ── Corrosion Compliance Pipeline ─────────────────────────────────────
        # Uses ifc_parser → compliance_runner (GC-001 + CC-001) → BCF + cost model + issue tracker
        compliance_results = []
        bcf_path = None
        cost_impact = None
        issue_stats = {}
        compliance_error = None
        compliance_is_demo = False

        try:
            if ifc_path and not ifc_error:
                # Parse service elements from the real IFC file
                service_elements = parse_ifc(ifc_path)
            else:
                # No IFC file — run on synthetic demo elements so the UI stays useful
                service_elements = generate_synthetic_elements(25)
                compliance_is_demo = True

            if service_elements:
                raw_results = run_compliance_checks(service_elements)
                compliance_results = _normalise_results(raw_results)

                # BCF 2.1 generation (Medium and above only)
                bcf_issues = issues_from_results(compliance_results)
                if bcf_issues:
                    bcf_bytes = generate_bcf(bcf_issues)
                    os.makedirs(_DATA_DIR, exist_ok=True)
                    bcf_path = os.path.join(
                        _DATA_DIR, f"compliance_project_{project_id}.bcf"
                    )
                    with open(bcf_path, "wb") as fh:
                        fh.write(bcf_bytes)

                # Cost and schedule impact
                cost_impact = CostModel().calculate_impact(compliance_results)

                # Persist issue history across runs
                os.makedirs(_DATA_DIR, exist_ok=True)
                history_file = os.path.join(_DATA_DIR, "bimguard_issue_history.json")
                tracker = IssueTracker(history_file)
                issue_stats = tracker.record_run(compliance_results)

        except Exception as exc:
            compliance_error = str(exc)

        return {
            "project": project,
            "documents": documents,
            "ifc_element_count": len(ifc_elements),
            "ifc_type_counts": ifc_type_counts,
            "ifc_totals": ifc_totals,
            "ifc_error": ifc_error,
            "rules": rules or [],
            "violations": violations or [],
            "report": report or "",
            # Corrosion compliance
            "compliance_results": compliance_results,
            "compliance_error": compliance_error,
            "compliance_is_demo": compliance_is_demo,
            "bcf_project_id": project_id if bcf_path else None,
            "cost_impact": cost_impact,
            "issue_stats": issue_stats,
        }
