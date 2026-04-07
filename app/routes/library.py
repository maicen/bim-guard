from pathlib import Path

from fasthtml.common import (
    Div,
    P,
    Title,
    UploadFile,
)
from app.components.documents_ui import document_edit_form, documents_panel
from app.components.layout import DashboardLayout
from app.components.rule_extraction_ui import (
    rule_extraction_empty_file_result,
    rule_extraction_page_content,
    rule_extraction_results,
)
from app.components.rules_ui import rule_form, rules_panel
from app.components.ui import (
    BackAction,
    Card as UICard,
    CardContent as UICardContent,
    CardHeader as UICardHeader,
    CardTitle as UICardTitle,
    CreateAction,
    EditAction,
    HtmxSpinner,
    LinkButton,
    NotFoundBlock,
    SubmitButton,
)
from app.modules.module1_doc_reader import Module1_DocReader
from app.services.documents_service import DocumentService
from app.services.rule_extraction_service import RuleExtractionService
from app.services.rules_service import RuleService
from app.utils import (
    md5_hex,
    redirect_see_other,
    safe_upload_name,
    store_upload_bytes,
)
from monsterui.all import (
    Card,
    CardBody,
    CardHeader,
    CardTitle,
    Container,
    DivLAligned,
    Form,
    H1,
    Input,
    FormLabel,
)

_document_service = DocumentService()
_rule_service = RuleService()
_rule_extraction_service = RuleExtractionService()


def _not_found_page(entity: str, back_href: str, back_title: str):
    return Title(f"{entity} Not Found - BIM Guard"), DashboardLayout(
        Container(NotFoundBlock(entity, back_href, back_title))
    )


def setup_routes(rt):
    @rt("/library/documents")
    def documents():
        upload_spinner, upload_spinner_style = HtmxSpinner(
            "documents-upload-spinner", "Processing document..."
        )

        return Title("Documents - BIM Guard"), DashboardLayout(
            Container(
                H1("Documents", cls="text-3xl font-bold tracking-tight"),
                P(
                    "Upload PDF, Markdown, or text references, extract their text, and manage your document library.",
                    cls="text-muted-foreground",
                ),
                UICard(
                    UICardHeader(UICardTitle("Upload Document")),
                    UICardContent(
                        Form(
                            Div(
                                FormLabel("Document (.pdf, .md, .txt)", fr="document"),
                                Input(
                                    id="document",
                                    type="file",
                                    name="document",
                                    accept=".pdf,.md,.txt",
                                    required=True,
                                ),
                                cls="space-y-1",
                            ),
                            SubmitButton("Upload Document", variant="primary"),
                            upload_spinner,
                            upload_spinner_style,
                            hx_post="/api/documents/upload",
                            hx_target="#documents-panel",
                            hx_indicator="#documents-upload-spinner",
                            enctype="multipart/form-data",
                            cls="space-y-4",
                        )
                    ),
                ),
                documents_panel(_document_service.list_documents()),
                cls="space-y-4",
            )
        )

    @rt("/api/documents/upload", methods=["POST"])
    async def documents_upload(document: UploadFile):
        filename = safe_upload_name(document.filename)
        suffix = Path(filename).suffix.lower()
        if suffix not in {".pdf", ".md", ".txt"}:
            return documents_panel(
                _document_service.list_documents(),
                "Only PDF, Markdown (.md), and text (.txt) files are supported.",
                level="warning",
            )

        file_content = await document.read()
        if not file_content:
            return documents_panel(
                _document_service.list_documents(),
                "Uploaded file is empty.",
                level="warning",
            )

        md5_hash = md5_hex(file_content)
        existing = _document_service.find_by_md5(md5_hash)
        if existing is not None:
            return documents_panel(
                _document_service.list_documents(),
                f"Document already exists: {existing.get('filename', filename)}",
                level="warning",
            )

        stored_path = store_upload_bytes(
            filename, file_content, _document_service.upload_dir
        )

        reader = Module1_DocReader()
        if suffix == ".pdf":
            extracted_text = reader.parse_pdf(file_content)
        else:
            extracted_text = file_content.decode("utf-8", errors="replace").strip()

        _document_service.create_document(
            md5_hash=md5_hash,
            filename=filename,
            file_path=str(stored_path),
            extracted_text=extracted_text,
        )

        return documents_panel(
            _document_service.list_documents(),
            f"Uploaded and stored: {filename}",
            level="success",
        )

    @rt("/library/documents/{document_id}")
    def document_details(document_id: int):
        document = _document_service.get_document(document_id)
        if document is None:
            return _not_found_page(
                "Document", "/library/documents", "Back to Documents"
            )

        extracted_text = (document.get("extracted_text") or "").strip()
        return Title(
            f"{document.get('filename', 'Document')} - BIM Guard"
        ), DashboardLayout(
            Container(
                H1(document.get("filename", "Document")),
                DivLAligned(
                    P(
                        f"MD5: {document.get('md5_hash', '-')}",
                        cls="font-mono text-xs text-muted-foreground",
                    ),
                    P(
                        f"Uploaded: {document.get('upload_date', '-')}",
                        cls="text-sm text-muted-foreground",
                    ),
                    EditAction(href=f"/library/documents/{document_id}/edit"),
                    BackAction(href="/library/documents", title="Back to Documents"),
                    cls="gap-2",
                ),
                Card(
                    CardHeader(CardTitle("Extracted Text")),
                    CardBody(
                        P(
                            extracted_text or "No text extracted for this document.",
                            cls="whitespace-pre-wrap text-sm",
                        ),
                        cls="max-h-[60vh] overflow-y-auto",
                    ),
                ),
                cls="space-y-4",
            )
        )

    @rt("/library/documents/{document_id}/edit")
    def document_edit(document_id: int):
        document = _document_service.get_document(document_id)
        if document is None:
            return _not_found_page(
                "Document", "/library/documents", "Back to Documents"
            )

        return Title("Edit Document - BIM Guard"), DashboardLayout(
            Container(
                document_edit_form(document),
                cls="space-y-4",
            )
        )

    @rt("/library/documents/{document_id}/update", methods=["POST"])
    def document_update(document_id: int, filename: str, extracted_text: str = ""):
        document = _document_service.get_document(document_id)
        if document is None:
            return redirect_see_other("/library/documents")

        _document_service.update_document(
            document_id=document_id,
            filename=Path(filename).name.strip()
            or document.get("filename", "document.pdf"),
            extracted_text=extracted_text,
        )
        return redirect_see_other(f"/library/documents/{document_id}")

    @rt("/library/documents/{document_id}/delete", methods=["POST"])
    def document_delete(document_id: int):
        _document_service.delete_document_with_file(document_id)

        return redirect_see_other("/library/documents")

    @rt("/library/rules")
    def rules_list(message: str = ""):
        return Title("Rules - BIM Guard"), DashboardLayout(
            Container(
                DivLAligned(
                    H1("Rule Library", cls="text-3xl font-bold tracking-tight"),
                    CreateAction(href="/library/rules/new", title="Create Rule"),
                    cls="justify-between",
                ),
                P(
                    "Create, update, and manage compliance rules used during analysis.",
                    cls="text-muted-foreground",
                ),
                DivLAligned(
                    LinkButton(
                        "Open Extraction Studio",
                        href="/library/rules/extract",
                        variant="secondary",
                    ),
                    cls="justify-end",
                ),
                rules_panel(_rule_service.list_rules(), message=message or None),
                cls="space-y-4",
            )
        )

    @rt("/library/rules/new")
    def rules_new():
        return Title("Create Rule - BIM Guard"), DashboardLayout(
            Container(
                rule_form("Create Rule", "/library/rules/create"), cls="space-y-4"
            )
        )

    @rt("/library/rules/create", methods=["POST"])
    def rules_create(
        reference: str,
        rule_type: str,
        description: str,
        target_ifc_class: str,
        parameters: str = "{}",
    ):
        _rule_service.create_rule(
            reference,
            rule_type,
            description,
            target_ifc_class,
            parameters,
        )
        return redirect_see_other("/library/rules")

    @rt("/library/rules/{rule_id}")
    def rules_details(rule_id: int):
        rule = _rule_service.get_rule(rule_id)
        if rule is None:
            return _not_found_page("Rule", "/library/rules", "Back to Rules")

        return Title(f"{rule.get('reference', 'Rule')} - BIM Guard"), DashboardLayout(
            Container(
                DivLAligned(
                    H1(rule.get("reference", "Rule")),
                    EditAction(href=f"/library/rules/{rule_id}/edit"),
                    cls="justify-between",
                ),
                Card(
                    CardHeader(CardTitle("Rule Details")),
                    CardBody(
                        P(f"Type: {rule.get('rule_type', '-')}", cls="text-sm"),
                        P(
                            f"Target IFC Class: {rule.get('target_ifc_class', '-')}",
                            cls="text-sm",
                        ),
                        P(rule.get("description", ""), cls="text-sm"),
                        Div(
                            rule.get("parameters", "{}"),
                            cls="font-mono text-xs bg-muted p-2 rounded border",
                        ),
                        cls="space-y-3",
                    ),
                ),
                BackAction(href="/library/rules", title="Back to Rules"),
                cls="space-y-4",
            )
        )

    @rt("/library/rules/{rule_id}/edit")
    def rules_edit(rule_id: int):
        rule = _rule_service.get_rule(rule_id)
        if rule is None:
            return redirect_see_other("/library/rules")

        return Title("Edit Rule - BIM Guard"), DashboardLayout(
            Container(
                rule_form("Edit Rule", f"/library/rules/{rule_id}/update", rule),
                cls="space-y-4",
            )
        )

    @rt("/library/rules/{rule_id}/update", methods=["POST"])
    def rules_update(
        rule_id: int,
        reference: str,
        rule_type: str,
        description: str,
        target_ifc_class: str,
        parameters: str = "{}",
    ):
        if _rule_service.get_rule(rule_id) is None:
            return redirect_see_other("/library/rules")

        _rule_service.update_rule(
            rule_id,
            reference,
            rule_type,
            description,
            target_ifc_class,
            parameters,
        )
        return redirect_see_other(f"/library/rules/{rule_id}")

    @rt("/library/rules/{rule_id}/delete", methods=["POST"])
    def rules_delete(rule_id: int):
        if _rule_service.get_rule(rule_id) is not None:
            _rule_service.delete_rule(rule_id)
        return redirect_see_other("/library/rules")

    @rt("/library/rules/extract")
    def rules_extract_page():
        return (
            Title("Rule Extraction - BIM Guard"),
            DashboardLayout(rule_extraction_page_content()),
        )

    @rt("/api/rules/extract", methods=["POST"])
    async def rules_extract_api(document: UploadFile):
        file_content = await document.read()
        if not file_content:
            return rule_extraction_empty_file_result()

        rules = await _rule_extraction_service.extract_rules(file_content)
        return rule_extraction_results(rules, document.filename)
