from fasthtml.common import Div, Tbody, Td, Th, Thead, Tr
from app.components.ui import CancelAction, DeleteAction, EditAction, SaveAction, ViewAction
from monsterui.all import Alert, AlertT, Card, CardBody, CardHeader, CardTitle, DivLAligned, Form, FormLabel, Input, Table, TextArea


def documents_table_rows(rows: list[dict]):
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


def documents_panel(rows: list[dict], message: str | None = None, level: str = "success"):
    alert = ()
    if message:
        cls = AlertT.success if level == "success" else AlertT.warning
        alert = (Alert(message, cls=cls),)

    return Div(
        *alert,
        Card(
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
                    Tbody(*documents_table_rows(rows)),
                    cls="min-w-[900px]",
                ),
                cls="w-full overflow-x-auto",
            ),
            cls="w-full max-w-full overflow-hidden",
        ),
        id="documents-panel",
        cls="space-y-4",
    )


def document_edit_form(document: dict):
    return Card(
        CardHeader(CardTitle(f"Edit: {document.get('filename', 'Document')}")),
        CardBody(
            Form(
                DivLAligned(
                    SaveAction("Save Changes"),
                    CancelAction(href="/library/documents"),
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
