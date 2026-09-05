"""FastAPI router for compliance rules, rulesets, folders, and extraction."""

from __future__ import annotations

import json
import re
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.dependencies import get_rules_service
from app.logging_config import get_logger
from app.modules.contracts import (
    IdsImportResponse,
    RuleBulkActionResponse,
    RuleBulkDeleteRequest,
    RuleBulkUpdateRequest,
    RuleCreateRequest,
    RuleDraftReviewRequest,
    RuleExtractionDraft,
    RuleFolderBulkActionResponse,
    RuleFolderBulkDeleteRequest,
    RuleFolderBulkUpdateRequest,
    RuleFolderCreateRequest,
    RuleFolderResponse,
    RuleFolderUpdateRequest,
    RuleResponse,
    RuleSnapshotCreateRequest,
    RuleSnapshotResponse,
    RuleSourceResponse,
    RuleUpdateRequest,
)
from app.services.rule_extraction_service import RuleExtractionService
from app.services.rule_snapshot_service import RuleSnapshotService
from app.services.rules_service import RuleService

logger = get_logger(__name__)

router = APIRouter()


def _rule_response(row: dict) -> RuleResponse:
    """Build a RuleResponse from a raw rules-table row.

    The persistence layer stores the human-readable rule identifier under
    the "reference" column (see RuleService._rules schema); RuleResponse
    exposes it as "rule_id" for a clearer public contract, so it needs
    bridging here rather than relying on Pydantic to find a same-named key.
    """
    if not row.get("rule_id"):
        row = {**row, "rule_id": row.get("reference")}
    return RuleResponse(**row)


@router.get("", response_model=list[RuleResponse], summary="List rules with optional filters")
def list_rules(
    service: Annotated[RuleService, Depends(get_rules_service)],
    response: Response,
    mechanism: Optional[str] = Query(None, description="Filter by mechanism (e.g. GC-001, CODE)"),
    ruleset_id: Optional[str] = Query(None, description="Filter by ruleset identifier"),
    category: Optional[str] = Query(None, description="Filter by domain category: Arch, Piping, or seismic"),
    keyword: Optional[str] = Query(None, description="Keyword search query"),
    needs_review: Optional[int] = Query(None, description="Filter by review status (1 or 0)"),
) -> list[RuleResponse]:
    """Retrieve compliance rules with optional multi-criteria filtering."""
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=60"
    if mechanism:
        rules = service.list_by_mechanism(mechanism)
    elif ruleset_id:
        rules = service.list_by_ruleset(ruleset_id)
    elif category:
        rules = service.list_by_category(category)
    else:
        rules = service.list_rules()

    if category and (mechanism or ruleset_id):
        norm_cat = service.normalize_category(category)
        rules = [r for r in rules if (r.get("category") == norm_cat or service.infer_category(r) == norm_cat)]

    if needs_review is not None:
        rules = [r for r in rules if r.get("needs_review") == needs_review]

    if keyword:
        kw = keyword.lower()
        rules = [
            r
            for r in rules
            if kw in (r.get("rule_id") or r.get("reference") or "").lower()
            or kw in (r.get("description") or "").lower()
            or kw in (r.get("source_text") or "").lower()
            or kw in (r.get("property_name") or "").lower()
        ]

    return [_rule_response(r) for r in rules]


@router.get("/folders", response_model=list[RuleFolderResponse], summary="List ruleset folders")
def list_rule_folders(
    service: Annotated[RuleService, Depends(get_rules_service)],
    response: Response,
    category: Optional[str] = Query(None, description="Filter by domain category: Arch, Piping, or seismic"),
) -> list[RuleFolderResponse]:
    """Return all rule folders along with their member rules."""
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=60"
    folders = service.list_folders_with_rules(category=category)
    result: list[RuleFolderResponse] = []
    for f in folders:
        rules_list = [_rule_response(r) for r in f.get("rules", [])]
        result.append(
            RuleFolderResponse(
                id=f.get("id"),
                ruleset_id=f.get("ruleset_id", ""),
                display_name=f.get("display_name", ""),
                description=f.get("description", ""),
                mechanism_scope=f.get("mechanism_scope", ""),
                category=f.get("category", "Arch"),
                rules=rules_list,
            )
        )
    return result


# NOTE: every route below that has a literal single-path-segment name (like
# "/export-ids" or "/snapshots") MUST stay declared before the generic
# GET/PUT/DELETE "/{rule_id}" routes further down this file. FastAPI/
# Starlette match routes in declaration order and "/{rule_id}" has no type
# converter in the path itself (int coercion happens after routing), so it
# matches ANY single path segment at the routing level — a literal route
# declared after it gets shadowed and 422s on "invalid int" instead of ever
# running. (This previously broke GET /rules/export-ids in production; keep
# this comment so nobody reintroduces the same bug.)


@router.get("/export-ids", summary="Export active rules as buildingSMART IDS XML")
def export_all_ids_xml(
    service: Annotated[RuleService, Depends(get_rules_service)],
    ruleset_id: str | None = None,
):
    """Export active rules or specific ruleset into buildingSMART IDS XML format."""
    if ruleset_id:
        rules = service.list_by_ruleset(ruleset_id)
    else:
        rules = service.list_rules()
    if not rules:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No rules found for IDS XML export.",
        )
    filename = f"{ruleset_id}.ids" if ruleset_id else "bimguard_rules.ids"
    try:
        xml_content = RuleService.export_ids_xml(ruleset_id or "BIMGUARD_EXPORT", rules)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PlainTextResponse(
        xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export-ids/{ruleset_id}", summary="Export ruleset as IDS XML")
def export_ids_xml(
    ruleset_id: str,
    service: Annotated[RuleService, Depends(get_rules_service)],
):
    """Export a ruleset into buildingSMART IDS XML format."""
    rules = service.list_by_ruleset(ruleset_id)
    if not rules:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rules found for ruleset {ruleset_id}.",
        )
    try:
        xml_content = RuleService.export_ids_xml(ruleset_id, rules)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PlainTextResponse(
        xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{ruleset_id}.ids"'},
    )


@router.get("/export-json", summary="Export active rules as canonical JSON")
def export_all_json(
    service: Annotated[RuleService, Depends(get_rules_service)],
    ruleset_id: str | None = None,
):
    """Export active rules or a specific ruleset into the canonical JSON ruleset format."""
    if ruleset_id:
        rules = service.list_by_ruleset(ruleset_id)
    else:
        rules = service.list_rules()
    if not rules:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No rules found for JSON export.",
        )
    filename = f"{ruleset_id}.json" if ruleset_id else "bimguard_rules.json"
    payload = RuleService.export_ruleset(ruleset_id or "BIMGUARD_EXPORT", rules)
    return JSONResponse(
        payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export-json/{ruleset_id}", summary="Export ruleset as canonical JSON")
def export_json(
    ruleset_id: str,
    service: Annotated[RuleService, Depends(get_rules_service)],
):
    """Export a ruleset into the canonical JSON ruleset format."""
    rules = service.list_by_ruleset(ruleset_id)
    if not rules:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rules found for ruleset {ruleset_id}.",
        )
    payload = RuleService.export_ruleset(ruleset_id, rules)
    return JSONResponse(
        payload,
        headers={"Content-Disposition": f'attachment; filename="{ruleset_id}.json"'},
    )


@router.post("/import-json", response_model=IdsImportResponse, summary="Import rules from a canonical JSON ruleset file")
async def import_json_rules(
    service: Annotated[RuleService, Depends(get_rules_service)],
    file: UploadFile = File(...),
    ruleset_id: str = Form(...),
) -> IdsImportResponse:
    """Parse an uploaded canonical JSON ruleset file and save its rules under ruleset_id."""
    content_bytes = await file.read()
    try:
        json_data = json.loads(content_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON file: {exc}") from exc
    if not isinstance(json_data, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON ruleset must be an object.")

    json_data = {**json_data, "ruleset_id": ruleset_id}
    rules = json_data.get("rules")
    total_parsed = len(rules) if isinstance(rules, list) else 0
    if not total_parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No importable rules found in JSON file.",
        )

    try:
        created_count = service.import_ruleset(json_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return IdsImportResponse(
        success=True,
        created_count=created_count,
        total_parsed=total_parsed,
        ruleset_id=ruleset_id,
    )


@router.post("/import-ids", response_model=IdsImportResponse, summary="Import rules from a buildingSMART IDS XML file")
async def import_ids_rules(
    service: Annotated[RuleService, Depends(get_rules_service)],
    file: UploadFile = File(...),
    ruleset_id: str = Form(...),
) -> IdsImportResponse:
    """Parse an uploaded IDS (.ids/XML) file and save its rules under ruleset_id."""
    content_bytes = await file.read()
    xml_text = content_bytes.decode("utf-8", errors="replace")
    try:
        rows = service.import_ids_xml(xml_text, ruleset_id=ruleset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No importable rules found in IDS file.",
        )

    kwargs_list = [
        dict(
            reference=row.get("reference", ""),
            rule_type=row.get("rule_type", "numeric_comparison"),
            description=row.get("description", ""),
            target_ifc_class=row.get("target_ifc_class", ""),
            source_text=row.get("source_text", ""),
            property_set=row.get("property_set", ""),
            property_name=row.get("property_name", ""),
            operator=row.get("operator", "="),
            check_value=row.get("check_value"),
            value_min=row.get("value_min"),
            value_max=row.get("value_max"),
            mechanism=row.get("mechanism", "CODE"),
            ruleset_id=ruleset_id,
            rule_category=row.get("rule_category", "property_check"),
            severity=row.get("severity", "mandatory"),
            extraction_method="ids_import",
            needs_review=True,
        )
        for row in rows
    ]

    try:
        created_count = len(service.create_rules_bulk(kwargs_list))
    except Exception as exc:
        # Batch insert failed outright (e.g. one bad row) — fall back to
        # inserting rules individually so valid rows still get saved.
        logger.warning("Bulk IDS import insert failed (%s); falling back to per-rule insert", exc)
        created_count = 0
        for row, kwargs in zip(rows, kwargs_list):
            try:
                service.create_rule(**kwargs)
                created_count += 1
            except Exception as row_exc:
                logger.warning("Could not import IDS rule %s: %s", row.get("reference"), row_exc)

    return IdsImportResponse(
        success=True,
        created_count=created_count,
        total_parsed=len(rows),
        ruleset_id=ruleset_id,
    )


@router.post(
    "/snapshots",
    response_model=RuleSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a named, timestamped snapshot of a ruleset's current rules",
)
def create_rule_snapshot(payload: RuleSnapshotCreateRequest) -> RuleSnapshotResponse:
    """Freeze the current rules of a ruleset into a persisted, reusable snapshot."""
    try:
        row = RuleSnapshotService().create_snapshot(
            ruleset_id=payload.ruleset_id,
            name=payload.name or payload.ruleset_id,
            source_mode=payload.source_mode or "manual",
            notes=payload.notes or "",
            created_by=payload.created_by or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RuleSnapshotResponse(**row)


@router.get("/snapshots", response_model=list[RuleSnapshotResponse], summary="List rule configuration snapshots")
def list_rule_snapshots() -> list[RuleSnapshotResponse]:
    """Return all saved rule-configuration snapshots, newest first."""
    return [RuleSnapshotResponse(**r) for r in RuleSnapshotService().list_snapshots()]


@router.get("/snapshots/{snapshot_id}", response_model=RuleSnapshotResponse, summary="Get one rule snapshot")
def get_rule_snapshot(snapshot_id: int) -> RuleSnapshotResponse:
    """Retrieve one saved rule-configuration snapshot by ID."""
    row = RuleSnapshotService().get_snapshot(snapshot_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Snapshot {snapshot_id} not found.")
    return RuleSnapshotResponse(**row)


@router.delete("/snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a rule snapshot")
def delete_rule_snapshot(snapshot_id: int) -> None:
    """Delete a saved rule-configuration snapshot."""
    if not RuleSnapshotService().delete_snapshot(snapshot_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Snapshot {snapshot_id} not found.")


@router.get("/snapshots/{snapshot_id}/pdf", summary="Download a rule snapshot as a structured PDF")
def download_rule_snapshot_pdf(snapshot_id: int):
    """Render and return a snapshot's frozen rule configuration as a PDF spec sheet."""
    svc = RuleSnapshotService()
    snapshot = svc.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Snapshot {snapshot_id} not found.")
    rules = svc.get_snapshot_rules(snapshot_id)

    from app.services.pdf_report_service import render_snapshot_pdf

    pdf_bytes = render_snapshot_pdf(snapshot, rules)
    filename = f"{(snapshot.get('name') or 'rule_configuration').replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/folders",
    response_model=RuleFolderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ruleset folder",
)
def create_rule_folder(
    payload: RuleFolderCreateRequest,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> RuleFolderResponse:
    """Create a new ruleset folder category."""
    norm_cat = service.normalize_category(payload.category)
    created = service.create_folder(
        ruleset_id=payload.ruleset_id,
        display_name=payload.display_name or payload.ruleset_id,
        description=payload.description or "",
        mechanism_scope=payload.mechanism_scope or "",
        category=norm_cat,
    )
    if not created:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Folder '{payload.ruleset_id}' already exists or has invalid ID.",
        )
    folders = service.list_folders_with_rules()
    for f in folders:
        if service.normalize_ruleset_id(f.get("ruleset_id")) == service.normalize_ruleset_id(payload.ruleset_id):
            return RuleFolderResponse(
                id=f.get("id"),
                ruleset_id=f.get("ruleset_id", ""),
                display_name=f.get("display_name", ""),
                description=f.get("description", ""),
                mechanism_scope=f.get("mechanism_scope", ""),
                category=f.get("category", norm_cat),
                rules=[],
            )
    return RuleFolderResponse(
        ruleset_id=payload.ruleset_id,
        display_name=payload.display_name or payload.ruleset_id,
        description=payload.description or "",
        mechanism_scope=payload.mechanism_scope or "",
        category=norm_cat,
        rules=[],
    )


@router.post(
    "/folders/bulk-update",
    response_model=RuleFolderBulkActionResponse,
    summary="Update metadata for multiple ruleset folders in bulk",
)
def bulk_update_rule_folders(
    payload: RuleFolderBulkUpdateRequest,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> RuleFolderBulkActionResponse:
    """Update category and/or mechanism scope for multiple ruleset folders."""
    updates = {}
    if payload.category is not None:
        updates["category"] = payload.category
    if payload.mechanism_scope is not None:
        updates["mechanism_scope"] = payload.mechanism_scope

    updated_ids = service.bulk_update_folders(payload.ruleset_ids, updates)
    return RuleFolderBulkActionResponse(
        success_count=len(updated_ids),
        affected_ruleset_ids=updated_ids,
        deleted_rules_count=0,
    )


@router.post(
    "/folders/bulk-delete",
    response_model=RuleFolderBulkActionResponse,
    summary="Delete multiple ruleset folders and member rules in bulk",
)
def bulk_delete_rule_folders(
    payload: RuleFolderBulkDeleteRequest,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> RuleFolderBulkActionResponse:
    """Delete multiple ruleset folders along with all member rules."""
    deleted_ids, deleted_rules = service.bulk_delete_folders(payload.ruleset_ids)
    return RuleFolderBulkActionResponse(
        success_count=len(deleted_ids),
        affected_ruleset_ids=deleted_ids,
        deleted_rules_count=deleted_rules,
    )


@router.get(
    "/folders/{ruleset_id}",
    response_model=RuleFolderResponse,
    summary="Get a ruleset folder by ID",
)
def get_rule_folder(
    ruleset_id: str,
    service: Annotated[RuleService, Depends(get_rules_service)],
    response: Response,
) -> RuleFolderResponse:
    """Retrieve details and member rules for a single ruleset folder."""
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=60"
    folder = service.get_folder(ruleset_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ruleset folder '{ruleset_id}' not found.",
        )
    rules_list = [_rule_response(r) for r in folder.get("rules", [])]
    return RuleFolderResponse(
        id=folder.get("id"),
        ruleset_id=folder.get("ruleset_id", ""),
        display_name=folder.get("display_name", ""),
        description=folder.get("description", ""),
        mechanism_scope=folder.get("mechanism_scope", ""),
        category=folder.get("category", "Arch"),
        rules=rules_list,
    )


@router.put(
    "/folders/{ruleset_id}",
    response_model=RuleFolderResponse,
    summary="Update an existing ruleset folder",
)
def update_rule_folder(
    ruleset_id: str,
    payload: RuleFolderUpdateRequest,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> RuleFolderResponse:
    """Update metadata and category for a ruleset folder."""
    updated = service.update_folder_metadata(
        ruleset_id=ruleset_id,
        display_name=payload.display_name,
        description=payload.description,
        mechanism_scope=payload.mechanism_scope,
        category=payload.category,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ruleset folder '{ruleset_id}' not found.",
        )
    folders = service.list_folders_with_rules()
    for f in folders:
        if service.normalize_ruleset_id(f.get("ruleset_id")) == service.normalize_ruleset_id(ruleset_id):
            rules_list = [_rule_response(r) for r in f.get("rules", [])]
            return RuleFolderResponse(
                id=f.get("id"),
                ruleset_id=f.get("ruleset_id", ""),
                display_name=f.get("display_name", ""),
                description=f.get("description", ""),
                mechanism_scope=f.get("mechanism_scope", ""),
                category=f.get("category", "Arch"),
                rules=rules_list,
            )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found after update")


@router.delete(
    "/folders/{ruleset_id}",
    summary="Delete a ruleset folder",
)
def delete_rule_folder(
    ruleset_id: str,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> dict:
    """Delete a ruleset folder and all of its associated member rules."""
    folder = service.get_folder(ruleset_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ruleset folder '{ruleset_id}' not found.",
        )
    deleted_rules = service.delete_folder(ruleset_id)
    return {
        "success": True,
        "ruleset_id": ruleset_id,
        "deleted_rules": deleted_rules,
    }


@router.post(
    "/bulk-update",
    response_model=RuleBulkActionResponse,
    summary="Update fields on multiple compliance rules in bulk",
)
def bulk_update_rules(
    payload: RuleBulkUpdateRequest,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> RuleBulkActionResponse:
    """Update ruleset folder, category, mechanism, severity, property set, or review status across multiple rules."""
    updates = {}
    if payload.ruleset_id is not None:
        updates["ruleset_id"] = payload.ruleset_id
    if payload.category is not None:
        updates["category"] = payload.category
    if payload.mechanism is not None:
        updates["mechanism"] = payload.mechanism
    if payload.severity is not None:
        updates["severity"] = payload.severity
    if payload.needs_review is not None:
        updates["needs_review"] = payload.needs_review
    if payload.property_set is not None:
        updates["property_set"] = payload.property_set

    updated_ids = service.bulk_update_rules(payload.rule_ids, updates)
    return RuleBulkActionResponse(
        success_count=len(updated_ids),
        affected_ids=updated_ids,
    )


@router.post(
    "/bulk-delete",
    response_model=RuleBulkActionResponse,
    summary="Delete multiple compliance rules in bulk",
)
def bulk_delete_rules(
    payload: RuleBulkDeleteRequest,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> RuleBulkActionResponse:
    """Delete multiple compliance rules by integer primary key IDs."""
    deleted_count = service.delete_rules(payload.rule_ids)
    return RuleBulkActionResponse(
        success_count=deleted_count,
        affected_ids=payload.rule_ids,
    )


@router.get("/{rule_id}", response_model=RuleResponse, summary="Get rule by ID")
def get_rule(
    rule_id: int,
    service: Annotated[RuleService, Depends(get_rules_service)],
    response: Response,
) -> RuleResponse:
    """Retrieve a single rule by integer ID."""
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=60"
    rule = service.get_rule(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID {rule_id} not found.",
        )
    return _rule_response(rule)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _find_best_matching_page(pages: list[dict], snippet: str) -> Optional[int]:
    """Resolve which page's text a rule's source snippet lives on.

    Whitespace-normalized substring match first (the common case — the
    snippet is a contiguous quote from one page); falls back to the page
    with the highest word-overlap ratio when no page contains it verbatim
    (e.g. the snippet spans a page break, or minor OCR/whitespace drift).
    """
    norm_snippet = _normalize_for_match(snippet)
    if not norm_snippet or not pages:
        return None

    for page in pages:
        if norm_snippet in _normalize_for_match(page.get("text", "")):
            return page.get("page_number")

    snippet_words = set(norm_snippet.split())
    if not snippet_words:
        return None

    best_page, best_score = None, 0.0
    for page in pages:
        page_words = set(_normalize_for_match(page.get("text", "")).split())
        if not page_words:
            continue
        overlap = len(snippet_words & page_words) / len(snippet_words)
        if overlap > best_score:
            best_score, best_page = overlap, page.get("page_number")

    return best_page if best_score > 0.3 else None


@router.get(
    "/{rule_id}/source",
    response_model=RuleSourceResponse,
    summary="Resolve a rule's source document/page for document-viewer annotation",
)
def get_rule_source(
    rule_id: int,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> RuleSourceResponse:
    """Resolve a rule's `source_document_id` + `source_text` into a viewer target.

    404s when the rule has no source document (manually-authored rules,
    or rules created before this linkage existed).
    """
    rule = service.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule with ID {rule_id} not found.")

    document_id = rule.get("source_document_id")
    if not document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule_id} has no source document.",
        )

    from app.services.document_pages_service import DocumentPagesService
    from app.services.documents_service import DocumentService

    doc = DocumentService().get_document(int(document_id))
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source document {document_id} for rule {rule_id} no longer exists.",
        )

    snippet = rule.get("source_text") or ""
    pages = DocumentPagesService().get_pages(int(document_id))
    page_number = _find_best_matching_page(pages, snippet)

    return RuleSourceResponse(
        document_id=int(document_id),
        filename=doc.get("filename", "document"),
        page_number=page_number,
        snippet=snippet,
    )


@router.post(
    "",
    response_model=RuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new rule",
)
def create_rule(
    payload: RuleCreateRequest,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> RuleResponse:
    """Create a new compliance rule entry in the database."""
    try:
        created = service.create_rule(
            rule_id=payload.rule_id,
            description=payload.description or "",
            source_text="",
            target_ifc_class=payload.target_ifc_class or "",
            property_set=payload.property_set or "",
            property_name=payload.property_name or "",
            operator=payload.operator or "==",
            check_value=payload.check_value,
            value_min=payload.value_min,
            value_max=payload.value_max,
            value_min_property=payload.value_min_property or "",
            value_max_property=payload.value_max_property or "",
            value_min_offset=payload.value_min_offset or 0,
            value_max_offset=payload.value_max_offset or 0,
            compare_property=payload.compare_property or "",
            name_pattern=payload.name_pattern or "",
            uniqueness_scope=payload.uniqueness_scope or "",
            unit=payload.unit or "",
            severity=payload.severity,
            mechanism=payload.mechanism or "CODE",
            ruleset_id=payload.ruleset_id,
            rule_category=payload.rule_category or "property_check",
            category=payload.category or "",
            confidence=payload.confidence or "1.0",
            extraction_method=payload.extraction_method or "manual",
            needs_review=payload.needs_review,
        )
        return _rule_response(created)
    except Exception as exc:
        logger.error("Failed to create rule: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/{rule_id}", response_model=RuleResponse, summary="Update an existing rule")
def update_rule(
    rule_id: int,
    payload: RuleUpdateRequest,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> RuleResponse:
    """Update fields on an existing compliance rule."""
    existing = service.get_rule(rule_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID {rule_id} not found.",
        )

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    updated = service.update_rule(rule_id, **updates)
    return _rule_response(updated or service.get_rule(rule_id))


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete rule")
def delete_rule(
    rule_id: int,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> None:
    """Delete a rule by primary key ID."""
    existing = service.get_rule(rule_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID {rule_id} not found.",
        )
    service.delete_rule(rule_id)


@router.post("/extract", summary="Extract rules from document text or file")
async def extract_rules(
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
) -> dict:
    """Extract compliance rules from uploaded document or provided raw text via LLM."""
    text = ""
    if file is not None and file.filename:
        content_bytes = await file.read()
        lower_name = file.filename.lower()
        if lower_name.endswith(".pdf"):
            from app.services.documents_service import DocumentService
            text = DocumentService.parse_pdf_content(content_bytes)
        else:
            text = content_bytes.decode("utf-8", errors="replace")
    elif raw_text:
        text = raw_text

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No document or text content was provided for rule extraction.",
        )

    extraction_service = RuleExtractionService()
    result = await extraction_service.extract_rules_from_text(text)
    return {
        "rules": result.rules,
        "warnings": result.warnings,
        "count": len(result.rules),
    }


@router.patch(
    "/drafts/{draft_id}",
    response_model=RuleExtractionDraft,
    summary="Review (accept/reject/edit) one rule extraction draft",
)
def review_rule_draft(draft_id: int, payload: RuleDraftReviewRequest) -> RuleExtractionDraft:
    """Record a review decision on one extraction draft."""
    from app.services.rule_draft_service import RuleDraftService

    try:
        row = RuleDraftService().review_draft(draft_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RuleExtractionDraft.model_validate(row)


@router.post(
    "/drafts/{draft_id}/promote",
    response_model=RuleResponse,
    summary="Promote an accepted/edited rule extraction draft into the rule library",
)
def promote_rule_draft(draft_id: int) -> dict:
    """Insert an accepted/edited draft's proposed rule into `public.rules`."""
    from app.services.rule_draft_service import RuleDraftService

    try:
        created = RuleDraftService().promote_draft(draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return created


@router.post("/seed", summary="Seed rule library with engine rulesets")
def seed_rules(
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> dict:
    """Seed corrosion mechanisms GC-001, CC-001, MC-001 into the rule library."""
    from app.services.ruleset_seeder import seed_engine_rulesets

    seeded = seed_engine_rulesets(service)
    total_rules = service.count()
    return {
        "success": True,
        "seeded_rulesets": seeded,
        "total_rules": total_rules,
    }


@router.post("/bulk", summary="Bulk insert extracted compliance rules")
def bulk_create_rules(
    rules: list[RuleCreateRequest],
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> dict:
    """Save a batch of extracted rules into the library."""
    kwargs_list = [
        dict(
            rule_id=payload.rule_id,
            description=payload.description or "",
            source_text="",
            target_ifc_class=payload.target_ifc_class or "",
            property_set=payload.property_set or "",
            property_name=payload.property_name or "",
            operator=payload.operator or "==",
            check_value=payload.check_value,
            value_min=payload.value_min,
            value_max=payload.value_max,
            unit=payload.unit or "",
            severity=payload.severity,
            mechanism=payload.mechanism or "CODE",
            ruleset_id=payload.ruleset_id,
            rule_category=payload.rule_category or "property_check",
            confidence=payload.confidence or "1.0",
            extraction_method=payload.extraction_method or "ai_extracted",
            needs_review=payload.needs_review,
        )
        for payload in rules
    ]

    try:
        created_count = len(service.create_rules_bulk(kwargs_list))
    except Exception as exc:
        # Batch insert failed outright (e.g. one bad row) — fall back to
        # inserting rules individually so valid rows still get saved.
        logger.warning("Bulk rule insert failed (%s); falling back to per-rule insert", exc)
        created_count = 0
        for payload, kwargs in zip(rules, kwargs_list):
            try:
                service.create_rule(**kwargs)
                created_count += 1
            except Exception as row_exc:
                logger.warning("Could not bulk create rule %s: %s", payload.rule_id, row_exc)

    return {
        "success": True,
        "created_count": created_count,
        "total_requested": len(rules),
    }


