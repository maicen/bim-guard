"""
orchestrator.py
----------------
Runs the full BIMGuard Module 1 + Module 3 pipeline end to end.
This is the single entry point — call run_pipeline() with a PDF path.

Pipeline flow:
    PDF file
        ↓  Module 1 — Step 1
    Document Extractor        → prose text + table DataFrames
                                 (Unstructured hosted API, or LightExtractor
                                 fallback — see module1_doc_parser/document_extractor.py)
        ↓  Module 1 — Step 2
    TableRuleBuilder          → tables → rules.db directly (no LLM)
        ↓  Module 1 — Step 3
    SectionChunker            → structured section chunks
        ↓  Module 1 — Step 4
    KeywordFilter             → scored + confidence-labelled paragraphs
        ↓  Handoff M1 → M3
    RuleConverter             → Regex (default) or GPT-4o → structured rule dicts
        ↓  Module 3
    RuleGenerator             → validate + enrich entity types
        ↓
    RuleStore                 → save to rules.db
        ↓
    Return summary dict       → back to caller (CLI or future API)

SWITCHING BETWEEN REGEX AND GPT-4o:
    Set USE_GPT4O = False  → uses regex (free, no API key needed)
    Set USE_GPT4O = True   → uses GPT-4o (accurate, costs per call)

Usage:
    # Run from project root
    python orchestrator.py data/input_docs/building_code.pdf

    # Or import and call:
    from orchestrator import run_pipeline
    result = run_pipeline("data/input_docs/building_code.pdf")
"""

import re
import sys
import time
from pathlib import Path

from app.logging_config import get_logger
from app.modules.config import OPENAI_API_KEY
from app.services.pipeline_dependencies import (
    describe_rule_store,
    warm_optional_rule_pipeline_dependencies,
)

logger = get_logger(__name__)

# The pipeline's progress logging uses box-drawing/unicode symbols, which
# crash with UnicodeEncodeError on Windows consoles/servers defaulting to
# cp1252 stdout. Force UTF-8 so run_pipeline() is safe to call from a web
# request, not just an interactive UTF-8 terminal.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ── SWITCH HERE ───────────────────────────────────────────────────────────────
# False = regex (free, no API key, works offline)
# True  = GPT-4o (more accurate, costs per API call)
USE_GPT4O = False
# ─────────────────────────────────────────────────────────────────────────────

try:
    from .module1_doc_parser import Module1_DocReader
    from .module1_doc_parser.document_extractor import extract_document_text
    from .module1_doc_parser.keyword_filter import KeywordFilter
    from .module1_doc_parser.section_chunker import SectionChunker
    from .module1_doc_parser.table_rule_builder import TableRuleBuilder
    from .module3_rule_builder.code_seed_rules import seed_rules
    from .module3_rule_builder.rule_generator import RuleGenerator
    from .module3_rule_builder.rule_store import RuleStore

    if USE_GPT4O:
        from .module3_rule_builder.rule_converter import RuleConverter
    else:
        from .module3_rule_builder.regex_rule_converter import RegexRuleConverter as RuleConverter
    _PIPELINE_AVAILABLE = True
except ImportError:
    _PIPELINE_AVAILABLE = False


def run_pipeline(
    pdf_path: str | Path,
    run_sections: str | list = "all",
    seed_db_first: bool = False,
    ruleset_id: str = "",
) -> dict:
    """
    Run the full Module 1 → Module 3 pipeline on a building-code PDF.

    Args:
        pdf_path      (str | Path): path to the building-code PDF file
        run_sections  (str | list): "all" or list e.g. ["4", "6"]
                                    Use a single section to test first.
        seed_db_first (bool):       seed baseline rules before processing
        ruleset_id    (str):        folder/group name tagged onto rules newly
                                     extracted by this run (table + prose rules).

    Returns:
        dict: {
            pdf_file        (str),
            converter_used  (str),   "regex" or "gpt-4o"
            table_rules     (int),   rules from tables (no LLM/regex)
            prose_rules     (int),   rules from converter
            total_rules     (int),   total in DB after run
            sections_run    (int),
            db_summary      (dict),
            warnings        (list[str]), non-fatal issues (e.g. missing spaCy model)
        }
    """
    pdf_path = Path(pdf_path)
    converter_name = "gpt-4o" if USE_GPT4O else "regex"
    logger.info(
        "Starting rule extraction pipeline pdf=%s converter=%s sections=%s seed_db_first=%s ruleset_id=%s",
        pdf_path.name,
        converter_name,
        run_sections,
        seed_db_first,
        ruleset_id or "none",
    )

    print(f"\n{'=' * 60}")
    print("  BIMGuard AI — Module 1 + 3 Pipeline")
    print(f"  PDF       : {pdf_path.name}")
    print(f"  Converter : {converter_name.upper()}")
    print(f"  Sections  : {run_sections}")
    print(f"  DB        : {describe_rule_store()}")
    print(f"{'=' * 60}\n")

    dependency_warnings = list(warm_optional_rule_pipeline_dependencies())
    for warning in dependency_warnings:
        logger.warning("Optional pipeline dependency unavailable: %s", warning)
        print(f"  [WARN] {warning}")

    # ── Initialise ────────────────────────────────────────────────────────────
    store = RuleStore()  # delegates to RuleService (shared web DB)
    generator = RuleGenerator(store)

    if USE_GPT4O:
        converter = RuleConverter(api_key=OPENAI_API_KEY, rule_store=store)
    else:
        converter = RuleConverter()  # regex needs no arguments

    # ── Seed pre-built rules ──────────────────────────────────────────────────
    if seed_db_first:
        logger.info("Seeding baseline rules before extraction")
        print("── SEEDING DB WITH PRE-BUILT CODE RULES ──")
        seed_rules(store, generator)

    # ─────────────────────────────────────────────────────────────────────────
    # MODULE 1 — STEP 1: Document extraction (Unstructured / LightExtractor)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n── MODULE 1 / STEP 1: DOCUMENT EXTRACTION ──")
    text, tables = extract_document_text(pdf_path.name, pdf_path.read_bytes())
    logger.info("Document extraction complete chars=%d tables=%d", len(text), len(tables))

    # ─────────────────────────────────────────────────────────────────────────
    # MODULE 1 — STEP 2: Table → Direct Rules (no converter needed)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n── MODULE 1 / STEP 2: TABLE RULE BUILDER ──")
    table_builder = TableRuleBuilder(store)
    table_rules = table_builder.process_all_tables(tables, generator, ruleset_id)
    logger.info("Table-rule extraction complete rules=%d", table_rules)

    # ─────────────────────────────────────────────────────────────────────────
    # MODULE 1 — STEP 3: Section Chunker
    # ─────────────────────────────────────────────────────────────────────────
    print("\n── MODULE 1 / STEP 3: SECTION CHUNKER ──")
    chunks = SectionChunker().chunk(text)
    logger.info("Section chunking complete sections=%d", len(chunks))

    if not chunks:
        # No headings this chunker recognises (or the source PDF collapsed to
        # one undifferentiated block with no line breaks at all — this happens
        # with some documents/extractors). Fall back to the same generic,
        # size-bounded chunker the AI extraction path already uses instead
        # of giving up and sending nothing downstream.
        print("  [SectionChunker] 0 sections — falling back to generic chunking")
        logger.warning("Section chunker returned no sections; using generic fallback")
        generic_blocks = Module1_DocReader().extract_text_sections(text)
        chunks = [
            {
                "section_number": str(i + 1),
                "section_name": f"Section {i + 1}",
                "text": block,
                "char_count": len(block),
            }
            for i, block in enumerate(generic_blocks)
        ]
        print(f"  [SectionChunker] Generic fallback produced {len(chunks)} chunk(s)")
        logger.info("Generic chunking complete sections=%d", len(chunks))

    # Filter to requested sections only
    if run_sections != "all":
        chunks = [c for c in chunks if c["section_number"] in run_sections]
        logger.info("Applied section filter requested=%s remaining=%d", run_sections, len(chunks))
        print(f"  Running sections: {run_sections}")

    # ─────────────────────────────────────────────────────────────────────────
    # MODULE 1 — STEP 4: Keyword Filter
    # ─────────────────────────────────────────────────────────────────────────
    print("\n── MODULE 1 / STEP 4: KEYWORD FILTER ──")
    warnings: list[str] = list(dependency_warnings)
    try:
        filtered_chunks = KeywordFilter().score_chunks(chunks)
    except (ImportError, OSError) as exc:
        # spaCy or its en_core_web_sm model isn't installed on this server
        # (optional `ml-pipeline` dependency group). Degrade instead of
        # discarding everything: pass paragraphs through unscored (neutral
        # MEDIUM confidence) so RegexRuleConverter still gets a chance to
        # pattern-match — we just lose the keyword-based noise filtering.
        msg = (
            f"Keyword filter unavailable ({exc}) — paragraphs are unscored "
            "for this run (no smart filtering), but regex rule extraction "
            "still ran on all of them."
        )
        logger.warning("%s", msg)
        print(f"  [WARN] {msg}")
        warnings.append(msg)
        filtered_chunks = [
            {
                **c,
                "scored_paragraphs": [
                    {"text": p.strip(), "score": 0, "matched": [], "confidence": "MEDIUM"}
                    for p in re.split(r"\n{2,}", c["text"])
                    if len(p.strip()) >= 20
                ],
            }
            for c in chunks
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # MODULE 3: Converter → RuleGenerator → RuleStore
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n── MODULE 3: {converter_name.upper()} CONVERTER ──")
    prose_rules = 0

    for chunk in filtered_chunks:
        section = chunk["section_number"]
        name = chunk["section_name"]
        print(f"\n  Section {section}: {name}")

        raw_rules = converter.extract_rules(chunk)
        print(f"    Extracted : {len(raw_rules)} rules")

        if raw_rules:
            if ruleset_id:
                for rule in raw_rules:
                    rule["ruleset_id"] = ruleset_id
            saved_ids = generator.save_batch(raw_rules)
            prose_rules += len(saved_ids)
            logger.debug(
                "Processed section=%s extracted_rules=%d saved_rules=%d",
                section,
                len(raw_rules),
                len(saved_ids),
            )
            print(f"    Saved     : {len(saved_ids)} rules")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_rules = store.count()
    db_summary = store.summary()
    logger.info(
        "Rule extraction pipeline complete pdf=%s table_rules=%d prose_rules=%d total_rules=%d sections=%d warnings=%d",
        pdf_path.name,
        table_rules,
        prose_rules,
        total_rules,
        len(filtered_chunks),
        len(warnings),
    )

    print(f"\n{'=' * 60}")
    print("  PIPELINE COMPLETE")
    print(f"  Converter used               : {converter_name}")
    print(f"  Table rules (no converter)   : {table_rules}")
    print(f"  Prose rules ({converter_name})  : {prose_rules}")
    print(f"  Total rules in DB            : {total_rules}")
    print(f"{'=' * 60}\n")

    return {
        "pdf_file": str(pdf_path),
        "converter_used": converter_name,
        "table_rules": table_rules,
        "prose_rules": prose_rules,
        "total_rules": total_rules,
        "sections_run": len(filtered_chunks),
        "db_summary": db_summary,
        "warnings": warnings,
    }


class BIMGuard_App:
    """
    Application-level orchestrator used by the web routes.
    Provides run_dashboard() for stats and orchestrate_workflow() for
    full IFC + compliance analysis.
    """

    def run_dashboard(self) -> dict:
        """Return summary counts for the dashboard page."""
        from app.services.documents_service import DocumentService
        from app.services.projects_service import ProjectsService
        from app.services.rules_service import RuleService

        projects_svc = ProjectsService()
        documents_svc = DocumentService()
        rules_svc = RuleService()

        summary = {
            "total_projects": projects_svc.total_projects(),
            "total_documents": len(documents_svc.list_documents()),
            "total_rules": rules_svc.count(),
        }
        logger.debug("Dashboard summary loaded %s", summary)
        return summary

    def orchestrate_workflow(
        self,
        project_id: int,
        doc_ids: list[int],
        analysis_theme: str = "Architecture",
        rule_folder: str = "",
        include_openings: bool = True,
        include_spaces: bool = True,
        include_type_definitions: bool = False,
    ) -> dict:
        """
        Run the full analysis pipeline for a project:
        1. Load project + documents from DB
        2. Load and parse the IFC file once (or use synthetic demo data)
        3. Run corrosion compliance checks
        4. Return a unified result dict consumed by the analyze route
        """
        from app.services.documents_service import DocumentService
        from app.services.projects_service import ProjectsService
        from app.services.rules_service import RuleService

        from .module2_ifc_read import Module2_IFCRead
        from .module2_ifc_read.ifc_parser import (
            generate_synthetic_elements,
            get_schema_compatibility_note,
            parse_ifc_model,
        )
        from app.services.pipeline_services import AnalysisService, run_compliance_analysis

        started_at = time.monotonic()

        def log_progress(percentage: int, step: str, **details) -> None:
            detail_text = " ".join(f"{key}={value}" for key, value in details.items())
            logger.info(
                "Analysis progress project_id=%d theme=%s progress=%d%% step=%s elapsed=%.2fs%s",
                project_id,
                selected_theme,
                percentage,
                step,
                time.monotonic() - started_at,
                f" {detail_text}" if detail_text else "",
            )

        projects_svc = ProjectsService()
        documents_svc = DocumentService()
        selected_theme = RuleService.normalize_theme(analysis_theme)
        rule_folder = (rule_folder or "").strip()
        log_progress(0, "request-started", documents=len(doc_ids), rule_folder=rule_folder or "all")
        logger.info(
            "Starting compliance workflow project_id=%d theme=%s documents=%d rule_folder=%s",
            project_id,
            selected_theme,
            len(doc_ids),
            rule_folder or "all",
        )

        project = projects_svc.get_project(project_id)
        if project is None:
            log_progress(5, "project-not-found")
            logger.warning("Compliance workflow project not found project_id=%d", project_id)
            return {"error": f"Project {project_id} not found."}
        log_progress(5, "project-loaded", project_name=project.get("name", ""))

        # ── Documents ────────────────────────────────────────────────────────
        documents = []
        for doc_id in doc_ids:
            doc = documents_svc.get_document(doc_id)
            if doc is None:
                continue
            text = doc.get("extracted_text") or ""
            documents.append(
                {
                    "filename": doc.get("filename", ""),
                    "section_count": len([l for l in text.splitlines() if l.strip()]),
                }
            )
        log_progress(10, "documents-loaded", loaded=len(documents), requested=len(doc_ids))

        # ── IFC parsing ──────────────────────────────────────────────────────
        log_progress(15, "ifc-file-resolution-started")
        ifc_path, improvement_lineage = projects_svc.resolve_analysis_ifc(project_id)
        ifc_error = None
        elements = []
        ifc_type_counts: dict = {}
        ifc_totals: dict = {}
        is_demo = False
        m2_reader: Module2_IFCRead | None = None
        ifc_quality_report: dict = {}
        ifc_quality_warnings: list[str] = []
        ifc_quality_improvements: list[str] = []
        ifc_schema_note: str | None = None
        building_summary: dict = {}
        spatial_checks: dict = {}
        egress_checks: dict = {}
        iso_checks: dict = {}

        if ifc_path:
            try:
                # Open IFC once, then reuse the loaded model for both parsing paths.
                log_progress(20, "ifc-model-loading", source=ifc_path)
                m2_reader = Module2_IFCRead(ifc_path)
                log_progress(30, "ifc-model-loaded")
                ifc_quality_report = m2_reader.quality_report or {}
                ifc_quality_warnings = m2_reader.quality_warnings or []
                if improvement_lineage is not None:
                    persisted_summary = improvement_lineage.get("summary") or {}
                    ifc_quality_improvements = list(
                        persisted_summary.get("improvements") or []
                    )
                    ifc_quality_warnings.insert(
                        0,
                        "Using persisted quality-improved IFC "
                        f"version {improvement_lineage.get('version')} from Projects.",
                    )
                ifc_schema_note = get_schema_compatibility_note(m2_reader.ifc_file)
                log_progress(
                    31,
                    "ifc-quality-inspection-complete",
                    warnings=len(ifc_quality_warnings),
                    improvements=len(ifc_quality_improvements),
                    schema=getattr(m2_reader.ifc_file, "schema", "unknown"),
                )
                log_progress(
                    32,
                    "building-summary-started",
                    checks="storeys,floor-heights,areas,fixtures,qa-flags",
                )
                try:
                    building_summary = m2_reader.extract_building_summary()
                    log_progress(
                        34,
                        "building-summary-complete",
                        storeys=building_summary.get("storey_count", 0),
                        spaces=building_summary.get("space_count", 0),
                    )
                except Exception as exc:
                    building_summary = {}
                    logger.warning(
                        "Building summary extraction failed project_id=%d error=%s",
                        project_id,
                        exc,
                        exc_info=True,
                    )
                log_progress(
                    35,
                    "spatial-compliance-started",
                    checks="daylight-ratio,fire-separation,garage-separation,door-space-connectivity",
                )
                try:
                    spatial_checks = m2_reader.extract_spatial_checks()
                    log_progress(
                        39,
                        "spatial-compliance-complete",
                        boundaries=spatial_checks.get("has_boundaries", False),
                        spaces=spatial_checks.get("space_count", 0),
                        daylight_results=len(spatial_checks.get("daylight", [])),
                        daylight_failures=sum(
                            1 for item in spatial_checks.get("daylight", []) if not item.get("passes")
                        ),
                        fire_results=len(spatial_checks.get("fire_separation", [])),
                        fire_failures=sum(
                            1
                            for item in spatial_checks.get("fire_separation", [])
                            if not item.get("passes")
                        ),
                        garage_results=len(spatial_checks.get("garage_separation", [])),
                        door_connections=len(spatial_checks.get("space_connection", [])),
                    )
                except Exception as exc:
                    spatial_checks = {}
                    logger.warning(
                        "Spatial compliance extraction failed project_id=%d error=%s",
                        project_id,
                        exc,
                        exc_info=True,
                    )
                log_progress(
                    40,
                    "egress-compliance-started",
                    checks="exterior-exit-count,space-to-exit-travel-distance",
                )
                try:
                    egress_checks = m2_reader.extract_egress_checks()
                    exit_count = egress_checks.get("exit_count", {})
                    travel_results = egress_checks.get("travel_distance", [])
                    log_progress(
                        44,
                        "egress-compliance-complete",
                        graph=egress_checks.get("has_graph", False),
                        exterior_doors=exit_count.get("total_exterior_doors", 0),
                        exit_checks=len(exit_count.get("results", [])),
                        travel_checks=len(travel_results),
                        travel_failures=sum(
                            1 for item in travel_results if not item.get("passes")
                        ),
                    )
                except Exception as exc:
                    egress_checks = {}
                    logger.warning(
                        "Egress compliance extraction failed project_id=%d error=%s",
                        project_id,
                        exc,
                        exc_info=True,
                    )
                log_progress(
                    45,
                    "iso19650-compliance-started",
                    checks="filename,suitability,revision,duplicate-guid,cde-state,provenance",
                )
                try:
                    iso_checks = m2_reader.extract_iso19650_checks(project=project)
                    log_progress(
                        46,
                        "iso19650-compliance-complete",
                        checks_run=len(iso_checks.get("results", [])),
                        fail_count=iso_checks.get("fail_count", 0),
                    )
                except Exception as exc:
                    iso_checks = {}
                    logger.warning(
                        "ISO 19650 compliance extraction failed project_id=%d error=%s",
                        project_id,
                        exc,
                        exc_info=True,
                    )
                log_progress(
                    47,
                    "ifc-domain-data-extracted",
                    spatial_checks=len(spatial_checks),
                    egress_checks=len(egress_checks),
                    iso_checks=len(iso_checks),
                )
                if selected_theme == "MEP":
                    elements = parse_ifc_model(m2_reader.ifc_file)
                else:
                    elements = []

                ifc_totals = m2_reader.extract_summary_counts(
                    include_openings=include_openings,
                    include_spaces=include_spaces,
                    include_type_definitions=include_type_definitions,
                )

                # Count by IFC type
                for el in elements:
                    ifc_type_counts[el.ifc_type] = ifc_type_counts.get(el.ifc_type, 0) + 1
                log_progress(
                    50,
                    "ifc-summary-complete",
                    products=ifc_totals.get("adjusted_products", 0),
                )
            except Exception as exc:
                ifc_error = str(exc)
                log_progress(50, "ifc-processing-failed", error=type(exc).__name__)
                logger.exception("IFC parsing failed project_id=%d", project_id)
        else:
            # No IFC file — run on synthetic demo data so the UI still renders
            elements = generate_synthetic_elements(25)
            is_demo = True
            ifc_totals = {
                "built_elements": len(elements),
                "all_physical_elements": len(elements),
                "adjusted_physical_elements": len(elements),
                "all_products": len(elements),
                "adjusted_products": len(elements),
                "filters": {
                    "include_openings": include_openings,
                    "include_spaces": include_spaces,
                    "include_type_definitions": include_type_definitions,
                },
                "excluded_or_added": {"openings": 0, "spaces": 0, "type_definitions": 0},
            }
            for el in elements:
                ifc_type_counts[el.ifc_type] = ifc_type_counts.get(el.ifc_type, 0) + 1
            log_progress(50, "synthetic-ifc-data-generated", elements=len(elements))
            logger.info("Using synthetic IFC elements project_id=%d elements=%d", project_id, len(elements))

        # ── Compliance checks ─────────────────────────────────────────────────
        compliance_results = []
        compliance_error = None
        cost_impact = None
        issue_stats: dict = {}
        audit_issues: list[dict] = []
        bcf_topics: list[dict] = []
        audit_source_sha256: str | None = None

        if selected_theme == "MEP":
            log_progress(55, "mep-compliance-started", elements=len(elements))
            try:
                audit_result = run_compliance_analysis(
                    elements,
                    run_id=f"BGR-{project_id}",
                    source_path=ifc_path,
                )
                raw_results = audit_result["results"]
                audit_issues = audit_result["issues"]
                bcf_topics = audit_result["bcf_topics"]
                audit_source_sha256 = audit_result["source_sha256"]
                # Normalise band names to Title case for the UI
                band_map = {
                    "LOW": "Low",
                    "MEDIUM": "Medium",
                    "HIGH": "High",
                    "CRITICAL": "Critical",
                }
                for r in raw_results:
                    r["risk_band"] = band_map.get(r.get("overall_band", "Low"), "Low")
                compliance_results = raw_results

                bands = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
                for r in compliance_results:
                    b = r.get("risk_band", "Low")
                    if b in bands:
                        bands[b] += 1
                issue_stats = bands
                log_progress(65, "mep-compliance-complete", results=len(compliance_results))
            except Exception as exc:
                compliance_error = str(exc)
                log_progress(65, "mep-compliance-failed", error=type(exc).__name__)
                logger.exception("MEP compliance checks failed project_id=%d", project_id)
        else:
            log_progress(65, "mep-compliance-skipped")

        # ── Module 2 + 4 + 5: Rule-based compliance check ────────────────────
        rule_compliance: list[dict] = []
        rule_compliance_summary: dict = {}
        rule_compliance_error: str | None = None
        rule_validations: list[dict] = []  # kept for backward-compat

        try:
            from .module4_comparator import Module4_Comparator
            from .module5_reporter import Module5_Reporter

            if rule_folder:
                library_rules = RuleService().list_by_ruleset(rule_folder)
            else:
                library_rules = RuleService().list_by_theme(selected_theme)
            log_progress(70, "rules-loaded", rules=len(library_rules))
            for rule_index, rule in enumerate(library_rules, start=1):
                logger.info(
                    "Selected ARCH rule=%d/%d reference=%s target=%s property=%s operator=%s check_value=%r min=%r max=%r unit=%s severity=%s",
                    rule_index,
                    len(library_rules),
                    rule.get("reference") or rule.get("id") or "unknown",
                    rule.get("target_ifc_class") or "missing",
                    rule.get("property_name") or "none",
                    rule.get("operator") or "missing",
                    rule.get("check_value"),
                    rule.get("value_min"),
                    rule.get("value_max"),
                    rule.get("unit") or "none",
                    rule.get("severity") or "mandatory",
                )

            # Basic element-presence check (legacy rule_validations card)
            for rule in library_rules:
                target = rule.get("target_ifc_class", "")
                if target not in ifc_type_counts and m2_reader and not ifc_error:
                    try:
                        ifc_type_counts[target] = len(m2_reader.ifc_file.by_type(target))
                    except Exception:
                        ifc_type_counts[target] = 0
                count = ifc_type_counts.get(target, 0)
                rule_validations.append(
                    {
                        "reference": rule.get("reference", "—"),
                        "description": rule.get("description", ""),
                        "rule_type": rule.get("rule_type", ""),
                        "target_ifc_class": target,
                        "element_count": count,
                        "status": "present" if count > 0 else "not_found",
                    }
                )

            # Full Module 2 → 4 → 5 compliance pipeline (only when IFC file exists)
            if m2_reader and not ifc_error and library_rules:
                log_progress(75, "rule-data-extraction-started", rules=len(library_rules))
                _compliance_started_at = time.perf_counter()
                extraction = m2_reader.extract_for_compliance(library_rules)
                log_progress(82, "rule-validation-started", extracted=len(extraction))
                rule_compliance = Module4_Comparator().validate_metadata(extraction)
                compliance_duration_seconds = time.perf_counter() - _compliance_started_at
                for rule_index, result in enumerate(rule_compliance, start=1):
                    logger.info(
                        "Rule validation result=%d/%d reference=%s check=%s.%s operator=%s threshold=%r range=%r..%r unit=%s status=%s elements=%d passed=%d failed=%d missing=%d",
                        rule_index,
                        len(rule_compliance),
                        result.get("rule_ref") or result.get("rule_id") or "unknown",
                        result.get("target") or "unknown",
                        result.get("property_name") or "none",
                        result.get("operator") or "unknown",
                        result.get("check_value"),
                        result.get("value_min"),
                        result.get("value_max"),
                        result.get("unit") or "none",
                        result.get("status") or "unknown",
                        result.get("total_count", 0),
                        result.get("pass_count", 0),
                        result.get("fail_count", 0),
                        result.get("missing_count", 0),
                    )
                log_progress(90, "report-generation-started", results=len(rule_compliance))
                rule_compliance_summary = Module5_Reporter().render_visual_report(
                    rule_compliance, duration_seconds=compliance_duration_seconds
                )
                logger.info(
                    "Compliance report summary project_id=%d total_rules=%d passed=%d failed=%d missing_data=%d no_elements=%d mandatory_failed=%d pass_rate=%s%% targets=%s",
                    project_id,
                    rule_compliance_summary.get("total_rules", 0),
                    rule_compliance_summary.get("passed", 0),
                    rule_compliance_summary.get("failed", 0),
                    rule_compliance_summary.get("missing_data", 0),
                    rule_compliance_summary.get("no_elements", 0),
                    rule_compliance_summary.get("mandatory_failed", 0),
                    rule_compliance_summary.get("pass_rate", 0),
                    rule_compliance_summary.get("by_target", {}),
                )
            else:
                log_progress(
                    90,
                    "rule-compliance-skipped",
                    has_ifc=bool(m2_reader),
                    ifc_error=bool(ifc_error),
                    rules=len(library_rules),
                )

        except Exception as exc:
            rule_compliance_error = str(exc)
            log_progress(90, "rule-compliance-failed", error=type(exc).__name__)
            logger.exception("Rule-based compliance checks failed project_id=%d", project_id)

        if rule_compliance:
            log_progress(95, "audit-results-merging", results=len(rule_compliance))
            existing_issue_count = len(audit_issues)
            existing_topic_count = len(bcf_topics)
            audit_result = AnalysisService().include_rule_results(
                {
                    "pipeline": "audit",
                    "element_count": len(compliance_results),
                    "results": compliance_results,
                    "issues": audit_issues,
                    "bcf_topics": bcf_topics,
                },
                rule_compliance,
                run_id=f"BGR-{project_id}",
            )
            audit_issues = audit_result["issues"]
            bcf_topics = audit_result["bcf_topics"]
            logger.info(
                "Audit merge complete project_id=%d rule_failures_added=%d bcf_topics_added=%d total_issues=%d total_bcf_topics=%d",
                project_id,
                len(audit_issues) - existing_issue_count,
                len(bcf_topics) - existing_topic_count,
                len(audit_issues),
                len(bcf_topics),
            )

        if selected_theme == "MEP":
            ifc_element_count = len(elements)
        else:
            ifc_element_count = int(ifc_totals.get("adjusted_products", 0))

        log_progress(
            100,
            "analysis-complete",
            elements=ifc_element_count,
            rule_results=len(rule_compliance),
        )
        logger.info(
            "Compliance workflow complete project_id=%d elements=%d MEP_results=%d rule_results=%d demo=%s",
            project_id,
            ifc_element_count,
            len(compliance_results),
            len(rule_compliance),
            is_demo,
        )

        return {
            "project": project,
            "analysis_theme": selected_theme,
            "rule_folder": rule_folder,
            "ifc_element_count": ifc_element_count,
            "ifc_type_counts": ifc_type_counts,
            "ifc_totals": ifc_totals,
            "ifc_error": ifc_error,
            "ifc_quality_report": ifc_quality_report,
            "ifc_quality_warnings": ifc_quality_warnings,
            "ifc_quality_improvements": ifc_quality_improvements,
            "ifc_schema_note": ifc_schema_note,
            "documents": documents,
            "compliance_results": compliance_results,
            "audit_issues": audit_issues,
            "bcf_topics": bcf_topics,
            "audit_source_sha256": audit_source_sha256,
            "cost_impact": cost_impact,
            "issue_stats": issue_stats,
            "compliance_is_demo": is_demo,
            "bcf_project_id": project_id,
            "compliance_error": compliance_error,
            "rule_validations": rule_validations,
            # Module 4 results
            "rule_compliance": rule_compliance,
            "rule_compliance_summary": rule_compliance_summary,
            "rule_compliance_error": rule_compliance_error,
            "building_summary": building_summary,
            "spatial_checks": spatial_checks,
            "egress_checks": egress_checks,
            "iso_checks": iso_checks,
        }


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python orchestrator.py <path_to_code_pdf>")
        print("Example: python orchestrator.py data/input_docs/building_code.pdf")
        print(f"\nCurrent converter: {'GPT-4o' if USE_GPT4O else 'Regex'}")
        print("To switch: change USE_GPT4O = True/False at top of file")
        sys.exit(1)

    run_pipeline(
        pdf_path=sys.argv[1],
        run_sections="all",
    )
