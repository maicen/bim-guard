"""FastAPI router for compliance rules, rulesets, folders, and extraction."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse

from app.api.dependencies import get_rules_service
from app.logging_config import get_logger
from app.modules.contracts import (
    RuleCreateRequest,
    RuleFolderCreateRequest,
    RuleFolderResponse,
    RuleFolderUpdateRequest,
    RuleResponse,
    RuleUpdateRequest,
)
from app.services.rule_extraction_service import RuleExtractionService
from app.services.rules_service import RuleService

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=list[RuleResponse], summary="List rules with optional filters")
def list_rules(
    service: Annotated[RuleService, Depends(get_rules_service)],
    mechanism: Optional[str] = Query(None, description="Filter by mechanism (e.g. GC-001, CODE)"),
    ruleset_id: Optional[str] = Query(None, description="Filter by ruleset identifier"),
    category: Optional[str] = Query(None, description="Filter by domain category: Arch, Piping, or seismic"),
    keyword: Optional[str] = Query(None, description="Keyword search query"),
    needs_review: Optional[int] = Query(None, description="Filter by review status (1 or 0)"),
) -> list[RuleResponse]:
    """Retrieve compliance rules with optional multi-criteria filtering."""
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
            if kw in (r.get("rule_id") or "").lower()
            or kw in (r.get("description") or "").lower()
            or kw in (r.get("source_text") or "").lower()
            or kw in (r.get("property_name") or "").lower()
        ]

    return [RuleResponse(**r) for r in rules]


@router.get("/folders", response_model=list[RuleFolderResponse], summary="List ruleset folders")
def list_rule_folders(
    service: Annotated[RuleService, Depends(get_rules_service)],
    category: Optional[str] = Query(None, description="Filter by domain category: Arch, Piping, or seismic"),
) -> list[RuleFolderResponse]:
    """Return all rule folders along with their member rules."""
    folders = service.list_folders_with_rules(category=category)
    result: list[RuleFolderResponse] = []
    for f in folders:
        rules_list = [RuleResponse(**r) for r in f.get("rules", [])]
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
            rules_list = [RuleResponse(**r) for r in f.get("rules", [])]
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


@router.get("/{rule_id}", response_model=RuleResponse, summary="Get rule by ID")
def get_rule(
    rule_id: int,
    service: Annotated[RuleService, Depends(get_rules_service)],
) -> RuleResponse:
    """Retrieve a single rule by integer ID."""
    rule = service.get_rule(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID {rule_id} not found.",
        )
    return RuleResponse(**rule)


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
        return RuleResponse(**created)
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
    return RuleResponse(**(updated or service.get_rule(rule_id)))


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
    xml_content = RuleService.export_ids_xml(ruleset_id, rules)
    return PlainTextResponse(
        xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{ruleset_id}.ids"'},
    )


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
    created_count = 0
    for payload in rules:
        try:
            service.create_rule(
                rule_id=payload.rule_id,
                description=payload.description or "",
                source_text="",
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
            created_count += 1
        except Exception as exc:
            logger.warning("Could not bulk create rule %s: %s", payload.rule_id, exc)

    return {
        "success": True,
        "created_count": created_count,
        "total_requested": len(rules),
    }


