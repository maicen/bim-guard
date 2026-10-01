"""Document management, sections, hierarchical tree, and DocLang bounding boxes."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.modules.contracts.base import CDEState, IsoGovernanceFieldsRequired

__all__ = ['DocumentUpdateRequest', 'DocumentResponse', 'DocumentDetailResponse', 'GenerateDoclangRequest', 'GoogleDriveImportRequest', 'GoogleDriveImportResult', 'GoogleDriveImportResponse', 'DocumentConfirmRequest', 'ClauseMetadata', 'DeonticStatement', 'DocumentNodeContract', 'DocumentIngestResponse', 'DocumentSection', 'DocumentSectionsResponse', 'SectionTreeNode', 'DocumentSectionTreeResponse', 'SectionGraphResponse', 'DocumentElementBbox', 'DocumentElementBboxesResponse', 'RuleSourceSummary', 'DocumentElementWithRules', 'RuleSourceMapResponse', 'RulesetDocumentSourceMap', 'RulesetSourceMapResponse']

# ---------------------------------------------------------------------------
# Document Contracts
# ---------------------------------------------------------------------------


class DocumentUpdateRequest(BaseModel):
    """Payload for updating document metadata."""

    filename: Optional[str] = Field(None, min_length=1, description="Updated document filename")
    doc_type: Optional[str] = Field(None, description="Updated document type classification")

    # ISO 19650 Container Naming & CDE Metadata
    project_code: Optional[str] = Field(None, description="ISO 19650 Project Code")
    originator: Optional[str] = Field(None, description="ISO 19650 Originator Code")
    suitability_code: Optional[str] = Field(None, description="ISO 19650 Suitability Code")
    revision_code: Optional[str] = Field(None, description="ISO 19650 Revision Code")
    cde_state: Optional[CDEState] = Field(None, description="CDE State")
    approved_by: Optional[str] = Field(
        None,
        description="Lead Appointed Party approver name, required by CDEStateMachine to authorize a SHARED to PUBLISHED transition",
    )

class DocumentResponse(IsoGovernanceFieldsRequired):
    """Summary document item returned in lists."""

    id: int
    filename: str
    doc_type: str = Field(default="Specification", description="Document classification type")
    file_path: Optional[str] = None
    upload_date: Optional[str] = None
    text_preview: Optional[str] = Field(default=None, description="Preview of DocLang-derived plain text")
    char_count: int = 0
    has_doclang: bool = Field(default=False, description="Whether canonical DocLang XML is available")
    doclang_storage_path: Optional[str] = Field(
        default=None, description="Storage reference to offloaded DocLang XML or archive"
    )
    doclang_archive_path: Optional[str] = Field(
        default=None, description="Storage reference to pre-generated DocLang .dclx archive"
    )
    doclang_xml: Optional[str] = Field(
        default="",
        description="Canonical DocLang XML export if available (omitted in list summaries to preserve bandwidth)",
    )

    # ISO 19650 & CDE fields
    project_code: Optional[str] = ""

class DocumentDetailResponse(IsoGovernanceFieldsRequired):
    """Complete document record including its full plain text, derived from DocLang."""

    id: int
    filename: str
    doc_type: str = Field(default="Specification", description="Document classification type")
    file_path: Optional[str] = None
    upload_date: Optional[str] = None
    text: str = Field(default="", description="Full plain text, derived on demand from DocLang XML (not persisted)")
    char_count: int = 0
    doclang_storage_path: Optional[str] = Field(
        default=None, description="Storage reference to offloaded DocLang XML or archive"
    )
    doclang_archive_path: Optional[str] = Field(
        default=None, description="Storage reference to pre-generated DocLang .dclx archive"
    )
    doclang_xml: str = Field(default="", description="Canonical DocLang XML export (with OTSL tables)")

    # ISO 19650 & CDE fields
    project_code: Optional[str] = ""

class GenerateDoclangRequest(BaseModel):
    """Payload to (re)generate DocLang XML for an already-stored document."""

    parser: Optional[str] = Field(default="auto", description="Extraction parser (currently only 'auto' is valid)")
    engine_instance: Optional[str] = Field(default="", description="Named parsing engine instance to use")
    start_page: Optional[int] = Field(default=None, description="1-based start page to extract (PDF only)")
    end_page: Optional[int] = Field(default=None, description="1-based end page to extract (PDF only)")

class GoogleDriveImportRequest(BaseModel):
    """Payload for importing one or more documents from Google Drive share links."""

    urls: list[str] = Field(..., min_length=1, description="Google Drive file URLs or bare file IDs")
    doc_type: Optional[str] = Field(default="Specification", description="Document type applied to every import")
    project_code: Optional[str] = Field(default="", description="ISO 19650 Project Code")
    originator: Optional[str] = Field(default="", description="ISO 19650 Originator Code")
    suitability_code: Optional[str] = Field(default="S0", description="ISO 19650 Suitability Code")
    revision_code: Optional[str] = Field(default="P01.01", description="ISO 19650 Revision Code")
    parser: Optional[str] = Field(default="auto", description="Extraction parser (currently only 'auto' is valid)")
    engine_instance: Optional[str] = Field(default="", description="Named parsing engine instance to use")

class GoogleDriveImportResult(BaseModel):
    """Per-URL outcome of a Google Drive import batch."""

    url: str
    ok: bool
    document: Optional[DocumentDetailResponse] = None
    error: Optional[str] = None

class GoogleDriveImportResponse(BaseModel):
    """Result of importing a batch of Google Drive share links."""

    results: list[GoogleDriveImportResult] = Field(default_factory=list)

class DocumentConfirmRequest(BaseModel):
    """Payload to confirm a direct-to-cloud document upload."""

    storage_reference: str = Field(..., description="The reference generated by the upload-url endpoint")
    file_name: str = Field(..., description="Original filename")
    doc_type: str = Field(default="Specification", description="Document type")
    project_code: str = Field(default="", description="ISO 19650 project code")
    originator: str = Field(default="", description="ISO 19650 originator")
    suitability_code: str = Field(default="S0", description="ISO 19650 suitability")
    revision_code: str = Field(default="P01.01", description="ISO 19650 revision")
    organization_id: Optional[int] = Field(default=None, description="Owning organization ID")
    parser: str = Field(default="auto", description="Parser to use (auto, docling, etc.)")
    engine_instance: str = Field(default="", description="Parsing engine instance reference")
    generate_doclang: bool = Field(default=False, description="Whether to trigger DocLang generation immediately")
    start_page: Optional[int] = Field(default=None, description="Start page for PDF extraction")
    end_page: Optional[int] = Field(default=None, description="End page for PDF extraction")

# ---------------------------------------------------------------------------
# LlamaIndex Document Ingestion Contracts
# ---------------------------------------------------------------------------


class ClauseMetadata(BaseModel):
    """Provenance for a single extracted document node (clause/table/section)."""

    clause_id: Optional[str] = Field(default=None, description="Clause/article reference, e.g. '9.8.2.1.(1)'")
    page_number: Optional[int] = Field(default=None, description="1-based source page number, when known")
    parent_section: Optional[str] = Field(default=None, description="Nearest enclosing section heading")
    section_path: list[str] = Field(default_factory=list, description="Breadcrumb of headings, e.g. ['5', '5.3', '5.3.2']")
    node_type: Literal["paragraph", "table", "list", "heading"] = "paragraph"
    source_document_id: int = Field(..., description="FK to documents.id")
    bbox: Optional[dict[str, Any]] = Field(
        default=None, description="Bounding box coordinates on the page: {l, t, r, b, coord_origin}"
    )
    element_id: Optional[str] = Field(
        default=None,
        description="DocLang element id this clause's bbox was zipped from -- matches DocumentElementBbox.element_id",
    )

class DeonticStatement(BaseModel):
    """A single 'shall/must/should/may' obligation extracted from a clause."""

    text: str = Field(..., description="The extracted obligation sentence")
    modality: Literal["shall", "must", "should", "may"]
    subject: Optional[str] = Field(default=None, description="IFC entity/discipline the obligation refers to")
    clause: ClauseMetadata

class DocumentNodeContract(BaseModel):
    """A LlamaIndex node persisted for BCF/rule traceability."""

    node_id: str
    text: str
    metadata: ClauseMetadata
    deontic_statements: list[DeonticStatement] = Field(default_factory=list)

class DocumentIngestResponse(BaseModel):
    """Result of running LlamaIndex ingestion over one document."""

    document_id: int
    nodes: list[DocumentNodeContract]
    deontic_statement_count: int = 0

class DocumentSection(BaseModel):
    """One heading-delimited section/paragraph, offered as an extraction-scope choice."""

    id: Optional[str] = Field(default=None, description="Stable id within the document, e.g. 's12'")
    section_number: Optional[str] = Field(default=None, description="Detected clause/section number, e.g. '9.8.2'")
    section_name: Optional[str] = Field(default=None, description="Heading text for the section")
    text: str = Field(..., description="Full text of the section, for scoped rule extraction")
    char_count: int = 0
    page_number: Optional[int] = Field(
        default=None, description="Resolved source-document page this section starts on, when known"
    )
    printed_page_number: Optional[str] = Field(
        default=None, description="Logical or printed page number from document TOC or pagination layout"
    )
    node_type: str = Field(default="section", description="Type of node: 'section', 'heading', 'table', 'paragraph'")
    bbox: Optional[dict[str, Any]] = Field(default=None, description="Bounding box coordinates on the page")
    summary: Optional[str] = Field(default=None, description="Semantic summary of section provisions and requirements")
    end_page_number: Optional[int] = Field(default=None, description="Resolved source-document page this section ends on")
    key_topics: list[str] = Field(default_factory=list, description="Key architectural topics and domain concepts")
    citations: list[str] = Field(default_factory=list, description="Referenced sections, tables, or standards")
    target_ifc_classes: list[str] = Field(default_factory=list, description="Target IFC entity classes mentioned or governed")

class DocumentSectionsResponse(BaseModel):
    """Sections detected in a document, for choosing an extraction scope."""

    document_id: int
    sections: list[DocumentSection] = Field(default_factory=list)

class SectionTreeNode(BaseModel):
    """One node in the hierarchical outline built from a document's detected sections."""

    id: str = Field(..., description="Stable id matching the corresponding flat DocumentSection")
    section_number: Optional[str] = None
    section_name: Optional[str] = None
    char_count: int = 0
    page_number: Optional[int] = Field(
        default=None, description="Resolved source-document page this section starts on, when known"
    )
    printed_page_number: Optional[str] = Field(
        default=None, description="Logical or printed page number from document TOC or pagination layout"
    )
    node_type: str = Field(default="section", description="Type of outline node: 'section', 'heading', 'table'")
    bbox: Optional[dict[str, Any]] = Field(default=None, description="Bounding box coordinates on the page")
    summary: Optional[str] = Field(default=None, description="Semantic summary of section provisions and requirements")
    end_page_number: Optional[int] = Field(default=None, description="Resolved source-document page this section ends on")
    key_topics: list[str] = Field(default_factory=list, description="Key architectural topics and domain concepts")
    citations: list[str] = Field(default_factory=list, description="Referenced sections, tables, or standards")
    target_ifc_classes: list[str] = Field(default_factory=list, description="Target IFC entity classes mentioned or governed")
    children: list["SectionTreeNode"] = Field(default_factory=list)

SectionTreeNode.model_rebuild()

class DocumentSectionTreeResponse(BaseModel):
    """Hierarchical + flat section data for a document, for the scoped-extraction tree picker.

    ``tree`` nests sections for display; ``sections`` is the same data
    flattened (ids match) so callers can look up a selected node's full
    text without re-walking the tree. ``enhanced`` reports whether the
    optional AI label-cleanup pass ran successfully — the tree is fully
    usable either way.
    """

    document_id: int
    tree: list[SectionTreeNode] = Field(default_factory=list)
    sections: list[DocumentSection] = Field(default_factory=list)
    enhanced: bool = False

class SectionGraphResponse(BaseModel):
    """Graph RAG structural and relational context for a document's sections."""

    document_id: int
    section_id: Optional[str] = None
    records: list[dict[str, Any]] = Field(default_factory=list)
    available: bool = False

class DocumentElementBbox(BaseModel):
    """One rendered block's (heading/paragraph/table/picture) bounding box on the page.

    ``element_id`` matches the id injected into the document's DocLang XML at
    extraction time (``<custom><bg_element_id value="..."/></custom>``, see
    app/modules/document_parsing/doclang_element_ids.py) — the same id the
    frontend's DocLang XML/rendered-block parsers read directly off each
    element, so no separate client-side order-matching is needed to line this
    up with what's on screen.
    """

    element_id: str
    kind: Literal["heading", "paragraph", "list", "table", "picture"] = "paragraph"
    page_number: Optional[int] = None
    bbox: Optional[dict[str, Any]] = Field(default=None, description="{l, t, r, b, coord_origin}")
    order: int = Field(default=0, description="Reading-order index, for reading-order/cross-reference arrows")

class DocumentElementBboxesResponse(BaseModel):
    """Per-element bbox list for a document's PDF-page overlay.

    Empty for documents whose DocLang XML predates this feature, or that came
    from a raw ``.dclg``/``.dclx`` import (no Docling extraction pass, so no
    ids were ever injected) — the caller should treat an empty list as "no
    per-element overlay available", not an error.
    """

    document_id: int
    elements: list[DocumentElementBbox] = Field(default_factory=list)

class RuleSourceSummary(BaseModel):
    """Lightweight rule shape for the rule-source map view."""

    id: int
    rule_id: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    category: Optional[str] = None
    source_page_number: Optional[int] = None
    source_bbox: Optional[dict[str, Any]] = None
    source_element_id: Optional[str] = None
    match_status: Literal["exact", "unmapped", "orphaned"] = "unmapped"

class DocumentElementWithRules(DocumentElementBbox):
    """One document element annotated with the rule(s) extracted from it."""

    rules: list[RuleSourceSummary] = Field(default_factory=list)

class RuleSourceMapResponse(BaseModel):
    """Every rule extracted from a document, mapped against its exact source element.

    ``unmapped_rules`` holds rules with no ``source_element_id`` at all
    (extracted before that linkage existed) -- only an approximate page/bbox
    location. ``orphaned_rules`` holds rules whose ``source_element_id`` is
    set but matches no *current* element (the source document was likely
    re-parsed/re-uploaded and element ids shifted) -- these need re-linking,
    not just an approximate location.
    """

    document_id: int
    elements: list[DocumentElementWithRules] = Field(default_factory=list)
    unmapped_rules: list[RuleSourceSummary] = Field(default_factory=list)
    orphaned_rules: list[RuleSourceSummary] = Field(default_factory=list)

class RulesetDocumentSourceMap(BaseModel):
    """One source document's contribution to a ruleset's source map."""

    document_id: int
    filename: str
    elements: list[DocumentElementWithRules] = Field(default_factory=list)
    unmapped_rules: list[RuleSourceSummary] = Field(default_factory=list)
    orphaned_rules: list[RuleSourceSummary] = Field(default_factory=list)

class RulesetSourceMapResponse(BaseModel):
    """Every rule in a ruleset, mapped against its exact source element, across every source document.

    A ruleset's rules are not necessarily all extracted from one document
    (``source_document_id`` and ``ruleset_id`` are independent columns), so
    this groups by document first and reuses the same per-document
    exact/unmapped/orphaned split as ``RuleSourceMapResponse``.
    """

    ruleset_id: str
    documents: list[RulesetDocumentSourceMap] = Field(default_factory=list)
