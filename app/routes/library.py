from pathlib import Path

from fasthtml.common import (
    A,
    Br,
    Div,
    P,
    RedirectResponse,
    Span,
    Style,
    Tbody,
    Td,
    Th,
    Thead,
    Title,
    Tr,
    UploadFile,
)
from fastlite import database
from app.components.layout import DashboardLayout
from app.components.ui import BackAction, DeleteAction, EditAction, ViewAction
from app.modules.module1_doc_reader import Module1_DocReader
from app.utils import md5_hex, now_iso_utc, safe_upload_name, store_upload_bytes
from monsterui.all import (
    Alert,
    AlertT,
    Button,
    Card,
    CardBody,
    CardHeader,
    CardTitle,
    Container,
    DivLAligned,
    Form,
    ButtonT,
    H1,
    H3,
    Input,
    Label,
    Subtitle,
    Table,
    TextArea,
    FormLabel,
    UkIcon,
)
import asyncio


DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "bimguard.sqlite"

UPLOAD_DIR = DB_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_db = database(str(DB_PATH))
_documents = _db["documents"]
_documents.create(
    {
        "id": int,
        "md5_hash": str,
        "filename": str,
        "file_path": str,
        "extracted_text": str,
        "upload_date": str,
    },
    pk="id",
    if_not_exists=True,
)


def _find_document_by_md5(md5_hash: str):
    for row in _documents.rows:
        if row.get("md5_hash") == md5_hash:
            return row
    return None


def _documents_table_rows():
    rows = sorted(list(_documents.rows), key=lambda r: r["id"], reverse=True)
    if not rows:
        return [
            Tr(
                Td(
                    "No documents uploaded yet.",
                    colspan="5",
                    cls="text-center text-muted-foreground",
                )
            )
        ]

    rendered = []
    for row in rows:
        extracted_text = (row.get("extracted_text") or "").strip()
        preview = extracted_text[:140] + ("..." if len(extracted_text) > 140 else "")
        rendered.append(
            Tr(
                Td(row.get("filename", "-")),
                Td(row.get("md5_hash", "-"), cls="font-mono text-xs"),
                Td(row.get("upload_date", "-")),
                Td(preview or "No text extracted", cls="text-muted-foreground text-sm"),
                Td(
                    DivLAligned(
                        ViewAction(href=f"/library/documents/{row['id']}"),
                        EditAction(href=f"/library/documents/{row['id']}/edit"),
                        DeleteAction(action=f"/library/documents/{row['id']}/delete"),
                        cls="gap-1",
                    )
                ),
            )
        )
    return rendered


def _documents_table_card():
    return Card(
        CardHeader(CardTitle("Stored Documents")),
        Div(
            Table(
                Thead(
                    Tr(
                        Th("Filename"),
                        Th("MD5"),
                        Th("Uploaded"),
                        Th("Preview"),
                        Th("Actions"),
                    )
                ),
                Tbody(*_documents_table_rows()),
                cls="min-w-[900px]",
            ),
            cls="w-full overflow-x-auto",
        ),
        cls="w-full max-w-full overflow-hidden",
    )


def _documents_panel(message: str | None = None, level: str = "success"):
    alert = ()
    if message:
        cls = AlertT.success if level == "success" else AlertT.warning
        alert = (Alert(message, cls=cls),)

    return Div(*alert, _documents_table_card(), id="documents-panel", cls="space-y-4")


def _document_edit_form(document: dict):
    return Card(
        CardHeader(CardTitle(f"Edit: {document.get('filename', 'Document')}")),
        CardBody(
            Form(
                DivLAligned(
                    Button("Save Changes", cls=ButtonT.primary),
                    A(
                        Button("Cancel", cls=ButtonT.secondary),
                        href="/library/documents",
                    ),
                    cls="gap-2",
                ),
                Div(
                    FormLabel("Filename", fr="filename"),
                    Input(
                        id="filename",
                        name="filename",
                        value=document.get("filename", ""),
                        required=True,
                    ),
                    cls="space-y-1",
                ),
                Div(
                    FormLabel("Extracted Text", fr="extracted_text"),
                    TextArea(
                        document.get("extracted_text", ""),
                        id="extracted_text",
                        name="extracted_text",
                        rows="12",
                    ),
                    cls="space-y-1",
                ),
                method="post",
                action=f"/library/documents/{document['id']}/update",
                cls="space-y-4",
            )
        ),
    )


def RuleCard(rule):
    return Div(
        Div(
            Span(rule["reference"], cls="font-semibold"),
            Label(rule["type"]),
            cls="flex justify-between items-start mb-2",
        ),
        P(rule["description"], cls="mb-2 text-sm text-muted-foreground"),
        Div(
            f"Target: {rule['target_ifc_class']}",
            Br(),
            f"Params: {rule['parameters']}",
            cls="bg-background rounded p-2 border font-mono text-xs",
        ),
        cls="p-4 rounded-lg border bg-muted/40 text-sm mb-4",
    )


def setup_routes(rt):
    @rt("/library/documents")
    def documents():
        return Title("Documents - BIM Guard"), DashboardLayout(
            Container(
                H1("Documents", cls="text-3xl font-bold tracking-tight"),
                P(
                    "Upload PDF, Markdown, or text references, extract their text, and manage your document library.",
                    cls="text-muted-foreground",
                ),
                Card(
                    CardHeader(CardTitle("Upload Document")),
                    CardBody(
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
                            Button("Upload Document", cls=ButtonT.primary),
                            Div(
                                UkIcon("loader-2", cls="w-5 h-5 animate-spin"),
                                Span("Processing document...", cls="ml-2 text-sm"),
                                id="documents-upload-spinner",
                                cls="htmx-indicator hidden items-center",
                            ),
                            Style(
                                ".htmx-indicator.htmx-request { display: flex !important; }"
                            ),
                            hx_post="/api/documents/upload",
                            hx_target="#documents-panel",
                            hx_indicator="#documents-upload-spinner",
                            enctype="multipart/form-data",
                            cls="space-y-4",
                        )
                    ),
                ),
                _documents_panel(),
                cls="space-y-4",
            )
        )

    @rt("/api/documents/upload", methods=["POST"])
    async def documents_upload(document: UploadFile):
        filename = safe_upload_name(document.filename)
        suffix = Path(filename).suffix.lower()
        if suffix not in {".pdf", ".md", ".txt"}:
            return _documents_panel(
                "Only PDF, Markdown (.md), and text (.txt) files are supported.",
                level="warning",
            )

        file_content = await document.read()
        if not file_content:
            return _documents_panel("Uploaded file is empty.", level="warning")

        md5_hash = md5_hex(file_content)
        existing = _find_document_by_md5(md5_hash)
        if existing is not None:
            return _documents_panel(
                f"Document already exists: {existing.get('filename', filename)}",
                level="warning",
            )

        stored_path = store_upload_bytes(filename, file_content, UPLOAD_DIR)

        reader = Module1_DocReader()
        if suffix == ".pdf":
            extracted_text = reader.parse_pdf(file_content)
        else:
            extracted_text = file_content.decode("utf-8", errors="replace").strip()

        _documents.insert(
            {
                "md5_hash": md5_hash,
                "filename": filename,
                "file_path": str(stored_path),
                "extracted_text": extracted_text,
                "upload_date": now_iso_utc(),
            }
        )

        return _documents_panel(f"Uploaded and stored: {filename}", level="success")

    @rt("/library/documents/{document_id}")
    def document_details(document_id: int):
        document = _documents.get(document_id)
        if document is None:
            return Title("Document Not Found - BIM Guard"), DashboardLayout(
                Container(
                    Alert("Document not found.", cls=AlertT.warning),
                    BackAction(href="/library/documents", title="Back to Documents"),
                    cls="space-y-4",
                )
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
                    EditAction(
                        href=f"/library/documents/{document_id}/edit",
                        cls=ButtonT.primary,
                    ),
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
        document = _documents.get(document_id)
        if document is None:
            return Title("Document Not Found - BIM Guard"), DashboardLayout(
                Container(
                    Alert("Document not found.", cls=AlertT.warning),
                    BackAction(href="/library/documents", title="Back to Documents"),
                    cls="space-y-4",
                )
            )

        return Title("Edit Document - BIM Guard"), DashboardLayout(
            Container(
                _document_edit_form(document),
                cls="space-y-4",
            )
        )

    @rt("/library/documents/{document_id}/update", methods=["POST"])
    def document_update(document_id: int, filename: str, extracted_text: str = ""):
        document = _documents.get(document_id)
        if document is None:
            return RedirectResponse("/library/documents", status_code=303)

        _documents.update(
            updates={
                "filename": Path(filename).name.strip()
                or document.get("filename", "document.pdf"),
                "extracted_text": extracted_text,
            },
            pk_values=document_id,
        )
        return RedirectResponse(f"/library/documents/{document_id}", status_code=303)

    @rt("/library/documents/{document_id}/delete", methods=["POST"])
    def document_delete(document_id: int):
        document = _documents.get(document_id)
        if document is not None:
            file_path = document.get("file_path")
            if file_path:
                try:
                    path = Path(file_path)
                    if path.exists():
                        path.unlink()
                except OSError:
                    pass
            _documents.delete(document_id)

        return RedirectResponse("/library/documents", status_code=303)

    @rt("/library/rules")
    def get():
        # Mocking the rules fetched from the react-query endpoint
        mock_rule_doc = {
            "name": "ISO 19650 Naming Convention",
            "description": "Standard naming conventions for BIM models.",
            "categories": [
                {
                    "id": 1,
                    "name": "File Naming",
                    "rules": [
                        {
                            "id": 101,
                            "reference": "REQ-01",
                            "type": "Required",
                            "description": "File name must follow Project-Originator-Volume-Level-Type-Role-Number format.",
                            "target_ifc_class": "IfcProject",
                            "parameters": {"regex": "^[A-Z0-9]{2,6}-[A-Z0-9]{3}-.*$"},
                        }
                    ],
                }
            ],
        }

        cards = []
        for cat in mock_rule_doc["categories"]:
            rules = [RuleCard(r) for r in cat["rules"]]
            cards.append(
                Card(
                    CardHeader(CardTitle(cat["name"], cls="text-lg")),
                    CardBody(*rules, cls="flex flex-col gap-4"),
                )
            )

        return Title("Rules Manager - BIM Guard"), DashboardLayout(
            Div(
                H1("Rule Manager", cls="text-3xl font-bold mb-4 tracking-tight"),
                P(
                    "View and edit extracted validation rules.",
                    cls="text-muted-foreground mb-8",
                ),
                Div(
                    Card(
                        CardHeader(
                            CardTitle(mock_rule_doc["name"]),
                            Subtitle(mock_rule_doc["description"]),
                        )
                    ),
                    Div(*cards, cls="grid gap-4 md:grid-cols-2"),
                    cls="flex flex-col gap-6",
                ),
                cls="container mx-auto py-6",
            )
        )

    @rt("/library/rules/extract")
    def get():
        return (
            Title("Rule Extraction - BIM Guard"),
            DashboardLayout(
                Div(
                    Div(
                        Div(
                            H1(
                                "Rule Extraction Studio",
                                cls="text-lg font-semibold tracking-tight",
                            ),
                            P(
                                "Upload a BEP document to extract rules via AI.",
                                cls="text-xs text-muted-foreground",
                            ),
                        ),
                        cls="flex items-center justify-between px-6 py-3 border-b bg-background",
                    ),
                    Div(
                        # Left panel (File upload form using HTMX)
                        Div(
                            Form(
                                Label("Upload BEP Document (PDF)", cls="mb-2"),
                                Input(
                                    type="file",
                                    name="document",
                                    accept=".pdf",
                                    cls="mb-4 mt-2",
                                ),
                                Button("Extract Rules", type="submit", cls="mt-2"),
                                hx_post="/api/rules/extract",
                                hx_target="#extracted-rules-container",
                                hx_indicator="#extract-spinner",
                                enctype="multipart/form-data",
                                cls="bg-background p-6 rounded-lg shadow-sm border",
                            ),
                            cls="flex-1 bg-muted/30 p-6 overflow-auto",
                        ),
                        Div(style="width:1px; background:#e5e7eb;"),
                        # Right panel (Results)
                        Div(
                            H3(
                                "Extracted Rules",
                                cls="text-lg font-semibold mb-4 px-6 pt-6",
                            ),
                            # Spinner
                            Div(
                                UkIcon(
                                    "loader-2", cls="w-6 h-6 animate-spin text-primary"
                                ),
                                Span(
                                    "Scanning document and building rules via AI...",
                                    cls="ml-2 text-sm text-muted-foreground",
                                ),
                                id="extract-spinner",
                                cls="htmx-indicator flex items-center justify-center p-6 hidden",
                            ),
                            Style(
                                ".htmx-indicator.hidden { display: none; } .htmx-request .htmx-indicator { display: flex !important; } .htmx-request.htmx-indicator { display: flex !important; }"
                            ),
                            # Target for HTMX
                            Div(
                                P(
                                    "Upload a document and click 'Extract' to see results here.",
                                    cls="text-sm text-muted-foreground text-center py-10",
                                ),
                                id="extracted-rules-container",
                                cls="px-6 pb-6 space-y-4",
                            ),
                            cls="w-full md:w-[400px] lg:w-[450px] bg-background border-l overflow-y-auto",
                        ),
                        cls="flex flex-1 overflow-hidden",
                    ),
                    cls="flex flex-col h-[calc(100vh-4rem)] -m-6",  # offset layout padding to fill screen
                )
            ),
        )

    @rt("/api/rules/extract", methods=["POST"])
    async def post(document: UploadFile):
        # Simulate processing time
        await asyncio.sleep(1.5)

        # Here we would normally call app.modules.orchestrator or module3_rule_builder
        # But for this port we just return extracted fragments
        rules = [
            {
                "ref": "REQ-DOC-01",
                "desc": "All files must start with Project ID",
                "target": "IfcProject",
            },
            {
                "ref": "REQ-DOC-02",
                "desc": "Columns must have LoadBearing property",
                "target": "IfcColumn",
            },
        ]

        fragments = []
        for r in rules:
            fragments.append(
                Div(
                    Div(
                        Span(r["ref"], cls="font-semibold text-sm"),
                        Label("New"),
                        cls="flex justify-between items-center mb-1",
                    ),
                    P(r["desc"], cls="text-sm text-muted-foreground mb-2"),
                    Div(
                        f"Target: {r['target']}",
                        cls="font-mono text-xs bg-muted p-1.5 rounded",
                    ),
                    cls="p-4 border rounded-md shadow-sm mb-4",
                )
            )

        success_msg = Alert(
            UkIcon("check-circle", cls="h-4 w-4"),
            Span(f"Extracted {len(rules)} rules from {document.filename}"),
            cls="mb-4 text-emerald-600 border-emerald-600 [&>svg]:text-emerald-600",
        )

        return Div(success_msg, *fragments)
