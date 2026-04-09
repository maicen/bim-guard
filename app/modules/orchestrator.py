from .module1_doc_reader import Module1_DocReader
from .module2_ifc_read import Module2_IFCRead
from .module3_rule_builder import Module3_RuleBuilder
from .module4_comparator import Module4_Comparator
from .module5_reporter import Module5_Reporter
from app.services.documents_service import DocumentService
from app.services.projects_service import ProjectsService
from app.services.rules_service import RuleService


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
        }
