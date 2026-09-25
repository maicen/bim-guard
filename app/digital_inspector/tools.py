"""LangGraph tools for the Digital Inspector agent.

Each tool is a thin wrapper around an existing domain service pulled from
`ApplicationContainer` (`app.bootstrap`) — no compliance/IFC/bSDD logic is
reimplemented here.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

from langchain_core.tools import tool

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.modules.ifc_reader import IFCReader

logger = get_logger(__name__)

# project_id -> (ifc_md5_hash, IFCReader). A geometry question routed through
# the ReAct loop typically chains 2-3 of the geometry tools below in one
# turn (find_elements -> get_element_geometry x2 -> get_distance...); without
# this, each call would re-parse the IFC file from disk from scratch (there
# is no cached parsed-model instance anywhere else in the app either -- every
# other caller, e.g. run_validation, re-parses per call too). Bounded LRU so a
# chatty multi-project session can't grow this unbounded; invalidated
# automatically when a project's ifc_md5_hash changes (a re-upload).
_READER_CACHE: "OrderedDict[int, tuple[str, IFCReader]]" = OrderedDict()
_READER_CACHE_MAX = 4


def _get_cached_reader(project_id: int) -> "IFCReader | None":
    """Return the project's primary-model IFCReader, parsed once and reused across tool calls."""
    from app.bootstrap import get_container
    from app.modules.ifc_reader import IFCReader

    project = get_container().projects_service.get_project(project_id)
    if project is None:
        return None
    current_hash = project.get("ifc_md5_hash") or ""

    cached = _READER_CACHE.get(project_id)
    if cached is not None and cached[0] == current_hash:
        _READER_CACHE.move_to_end(project_id)
        return cached[1]

    path = get_container().models_service.resolve_primary_path(project_id)
    if path is None:
        return None
    reader = IFCReader(path)

    _READER_CACHE[project_id] = (current_hash, reader)
    _READER_CACHE.move_to_end(project_id)
    while len(_READER_CACHE) > _READER_CACHE_MAX:
        _READER_CACHE.popitem(last=False)
    return reader


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
    from app.services.rule_extraction_service import (
        RuleExtractionService,
        RuleGenerationFailedError,
    )

    documents_service = get_container().documents_service
    doc = documents_service.get_document(document_id)
    if doc is None:
        return {"document_id": document_id, "error": "document not found"}
    text = documents_service.get_document_text(doc)
    if not text.strip():
        return {"document_id": document_id, "error": "document has no extracted text"}

    try:
        drafts = asyncio.run(RuleExtractionService().extract_rule_drafts(document_id, text))
    except RuleGenerationFailedError as exc:
        return {"document_id": document_id, "error": str(exc)}
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


@tool
def find_elements(
    project_id: int,
    ifc_class: str,
    storey_name: str | None = None,
    name_contains: str | None = None,
    limit: int = 20,
) -> dict:
    """Find elements of a given IFC class in a project, optionally filtered by storey or name.

    Use this first to resolve a fuzzy reference ("the exit door on level 2")
    to a concrete GUID before calling get_element_geometry or
    get_distance_between_elements — those two need an exact GUID, not a
    description.
    """
    reader = _get_cached_reader(project_id)
    if reader is None or reader.ifc_file is None:
        return {"project_id": project_id, "error": "no IFC model available for this project"}

    try:
        elements = reader.ifc_file.by_type(ifc_class)
    except Exception as exc:
        return {"project_id": project_id, "error": f"unknown or unparseable IFC class {ifc_class!r}: {exc}"}

    name_needle = (name_contains or "").strip().lower()
    storey_needle = (storey_name or "").strip().lower()
    matches = []
    for el in elements:
        if name_needle and name_needle not in (getattr(el, "Name", None) or "").lower():
            continue
        location = reader.get_spatial_location(el)
        if storey_needle and (location.get("storey_name") or "").strip().lower() != storey_needle:
            continue
        matches.append(
            {
                "guid": el.GlobalId,
                "name": getattr(el, "Name", None),
                "storey_name": location.get("storey_name"),
            }
        )
        if len(matches) >= limit:
            break

    return {"project_id": project_id, "ifc_class": ifc_class, "match_count": len(matches), "matches": matches}


@tool
def get_element_geometry(project_id: int, guid: str) -> dict:
    """Get an element's bounding box, centroid, and spatial context (storey/space/building).

    Use this once you have a specific element GUID (e.g. from find_elements)
    and need its size, position, or which storey/space it belongs to.
    """
    reader = _get_cached_reader(project_id)
    if reader is None or reader.ifc_file is None:
        return {"project_id": project_id, "guid": guid, "error": "no IFC model available for this project"}

    try:
        element = reader.ifc_file.by_guid(guid)
    except Exception:
        return {"project_id": project_id, "guid": guid, "error": "no element with this GUID in the model"}

    bbox = reader.geometry_extractor.get_bounding_box(element) if reader.geometry_extractor else None
    centroid = reader.geometry_extractor.get_centroid_or_none(element) if reader.geometry_extractor else None
    location = reader.get_spatial_location(element)

    return {
        "project_id": project_id,
        "guid": guid,
        "name": getattr(element, "Name", None),
        "ifc_class": element.is_a(),
        "bounding_box_mm": bbox,
        "centroid_mm": {"x": centroid[0], "y": centroid[1], "z": centroid[2]} if centroid else None,
        **location,
    }


@tool
def get_distance_between_elements(project_id: int, guid_a: str, guid_b: str) -> dict:
    """Compute the shortest surface-to-surface distance (mm) between two elements.

    Returns distance_mm: null (not 0) when the separation cannot be measured
    (missing geometry on either element) -- never treat a null as "touching".
    """
    reader = _get_cached_reader(project_id)
    if reader is None or reader.ifc_file is None or reader.geometry_extractor is None:
        return {"project_id": project_id, "error": "no IFC model available for this project"}

    try:
        element_a = reader.ifc_file.by_guid(guid_a)
        element_b = reader.ifc_file.by_guid(guid_b)
    except Exception:
        return {"project_id": project_id, "error": "one or both GUIDs were not found in the model"}

    distance = reader.geometry_extractor.calculate_shortest_distance(element_a, element_b)
    return {"project_id": project_id, "guid_a": guid_a, "guid_b": guid_b, "distance_mm": distance}


DIGITAL_INSPECTOR_TOOLS = [
    query_ifc_model,
    check_db_cache,
    bsdd_lookup,
    run_validation,
    extract_rules_from_document,
    check_cde_transition,
    find_elements,
    get_element_geometry,
    get_distance_between_elements,
]
