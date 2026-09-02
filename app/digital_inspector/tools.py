"""LangGraph tools for the Digital Inspector agent.

Each tool is a thin wrapper around an existing domain service pulled from
`ApplicationContainer` (`app.bootstrap`) — no compliance/IFC/bSDD logic is
reimplemented here.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.logging_config import get_logger

logger = get_logger(__name__)


@tool
def query_ifc_model(project_id: int) -> dict:
    """Look up a project's IFC model metadata: file path, hash, and status.

    Use this to check whether a project has an uploaded IFC model before
    running validation, or to answer "what model is loaded for this
    project" style questions.
    """
    from app.bootstrap import get_container

    project = get_container().projects_service.get_project(project_id)
    if project is None:
        return {"found": False, "project_id": project_id}
    return {
        "found": True,
        "project_id": project_id,
        "name": project.get("name"),
        "status": project.get("status"),
        "ifc_file_path": project.get("ifc_file_path"),
        "ifc_md5_hash": project.get("ifc_md5_hash"),
        "analysis_type": project.get("analysis_type"),
    }


@tool
def check_db_cache(ruleset_id: str) -> dict:
    """List the compliance rules already stored for a ruleset/rule folder.

    Use this to check what rules exist for a ruleset before extracting new
    ones from a document, avoiding duplicate extraction work.
    """
    from app.bootstrap import get_container

    rules = get_container().rules_service.list_by_ruleset(ruleset_id)
    return {
        "ruleset_id": ruleset_id,
        "rule_count": len(rules),
        "rule_ids": [row.get("reference") or row.get("rule_id") for row in rules][:50],
    }


@tool
def bsdd_lookup(query: str, dictionary_uri: str | None = None) -> dict:
    """Search the buildingSMART Data Dictionary (bSDD) for classes matching a query.

    Use this to resolve an IFC class or classification code a user asks
    about, e.g. "what's the bSDD entry for a fire damper".
    """
    from app.services.bsdd_client import DEFAULT_BSDD_CLIENT

    result = DEFAULT_BSDD_CLIENT.search_classes(query, dictionary_uri=dictionary_uri)
    return {
        "query": result.query,
        "total": result.total,
        "classes": [
            {"code": c.code, "name": c.name, "uri": c.uri, "dictionary_uri": c.dictionary_uri}
            for c in result.classes[:10]
        ],
    }


@tool
def run_validation(project_id: int, rule_folder: str = "") -> dict:
    """Run the architectural compliance pipeline for a project and summarize results.

    Delegates to the same `ArchAnalysisService.run_analysis` the
    `/api/analyze/arch` route uses — this is the full deterministic
    pipeline, not a re-implementation of it. Use this when asked to check
    or re-check a project's compliance, optionally scoped to one
    rule_folder/ruleset.
    """
    from app.bootstrap import get_container

    try:
        result = get_container().arch_analysis_service.run_analysis(
            project_id, rule_folder=rule_folder
        )
    except ValueError as exc:
        return {"project_id": project_id, "error": str(exc)}

    issues = result.issues
    return {
        "project_id": project_id,
        "rule_folder": rule_folder or "all",
        "issue_count": len(issues),
        "issues_preview": [
            {"guid": i.get("guid"), "reason": i.get("reason")} for i in issues[:10]
        ],
    }


@tool
def extract_rules_from_document(document_id: int) -> dict:
    """Extract reviewable rule drafts from a document via LlamaIndex (Module 1+3).

    Use this when asked to pull compliance rules out of an uploaded
    specification/code document. Results are persisted as `pending_review`
    drafts, not written directly into the rule library — a human still
    reviews them via `GET /api/documents/{id}/rules/drafts`.
    """
    import asyncio

    from app.bootstrap import get_container
    from app.services.rule_extraction_service import RuleExtractionService

    doc = get_container().documents_service.get_document(document_id)
    if doc is None:
        return {"document_id": document_id, "error": "document not found"}
    text = doc.get("extracted_text") or ""
    if not text.strip():
        return {"document_id": document_id, "error": "document has no extracted text"}

    drafts = asyncio.run(RuleExtractionService().extract_rule_drafts(document_id, text))
    return {
        "document_id": document_id,
        "draft_count": len(drafts),
        "drafts_preview": [
            {"rule_id": d.proposed_rule.rule_id, "description": d.proposed_rule.description}
            for d in drafts[:10]
        ],
    }


@tool
def check_cde_transition(project_id: int, target_state: str) -> dict:
    """Check whether a project can transition to a target ISO 19650 CDE state, and why not if it can't.

    target_state is one of "WIP", "SHARED", "PUBLISHED", "ARCHIVED". Use
    this to answer "can this project move to Shared" style questions
    without actually performing the transition — it evaluates the same
    gate logic `transition_project()` uses but makes no database write.
    """
    from app.bootstrap import get_container
    from app.digital_inspector.cde_graph import check_transition

    project = get_container().projects_service.get_project(project_id)
    if project is None:
        return {"project_id": project_id, "error": "project not found"}

    current_state = project.get("cde_state") or "WIP"
    return {
        "project_id": project_id,
        "current_state": current_state,
        **check_transition(
            current_state,
            target_state,
            filename=project.get("ifc_file_path", ""),
            approved_by=project.get("cde_approved_by", ""),
            is_approved=bool(project.get("cde_approved_by")),
        ),
    }


DIGITAL_INSPECTOR_TOOLS = [
    query_ifc_model,
    check_db_cache,
    bsdd_lookup,
    run_validation,
    extract_rules_from_document,
    check_cde_transition,
]
