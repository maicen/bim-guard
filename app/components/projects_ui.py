from fasthtml.common import Div, Option, Tbody, Td, Th, Thead, Tr
from app.components.layout import DashboardLayout
from app.components.ui import (
    CancelAction,
    CreateAction,
    DeleteAction,
    EditAction,
    SaveAction,
    ViewAction,
)
from monsterui.all import (
    Alert,
    AlertT,
    Card,
    Container,
    DivFullySpaced,
    DivLAligned,
    DivVStacked,
    Form,
    FormLabel,
    H1,
    H2,
    H3,
    Input,
    Select,
    Subtitle,
    Table,
    TableT,
    TextArea,
    UkIcon,
)


def project_form(
    title: str, action: str, project: dict | None = None, include_ifc: bool = False
):
    project = project or {}
    ifc_field = (
        (
            DivVStacked(
                FormLabel("IFC Model", fr="ifc_file"),
                Input(
                    id="ifc_file",
                    name="ifc_file",
                    type="file",
                    accept=".ifc",
                ),
                cls="space-y-1",
            ),
        )
        if include_ifc
        else ()
    )
    return Card(
        Form(
            DivVStacked(
                FormLabel("Project Name", fr="name"),
                Input(
                    id="name",
                    name="name",
                    value=project.get("name", ""),
                    placeholder="e.g. Airport Terminal A",
                    required=True,
                ),
                cls="space-y-1",
            ),
            DivVStacked(
                FormLabel("Description", fr="description"),
                TextArea(
                    project.get("description", ""),
                    id="description",
                    name="description",
                    placeholder="Scope, goals, and notes",
                    rows="5",
                ),
                cls="space-y-1",
            ),
            DivVStacked(
                FormLabel("Status", fr="status"),
                Select(
                    Option(
                        "Draft",
                        value="Draft",
                        selected=project.get("status") == "Draft",
                    ),
                    Option(
                        "Active",
                        value="Active",
                        selected=project.get("status") == "Active",
                    ),
                    Option(
                        "Archived",
                        value="Archived",
                        selected=project.get("status") == "Archived",
                    ),
                    id="status",
                    name="status",
                ),
                cls="space-y-1",
            ),
            *ifc_field,
            DivLAligned(
                SaveAction("Save Project"),
                CancelAction(href="/projects"),
                cls="gap-2",
            ),
            method="post",
            action=action,
            enctype="multipart/form-data" if include_ifc else None,
            cls="space-y-4",
        ),
        header=Div(H2(title), Subtitle("Manage your BIM compliance projects.")),
    )


def projects_table_rows(rows: list[dict]):
    if not rows:
        return [
            Tr(
                Td(
                    "No projects yet. Create your first one.",
                    colspan="7",
                    cls="text-center text-muted-foreground",
                )
            )
        ]

    rendered = []
    for row in rows:
        rendered.append(
            Tr(
                Td(str(row["id"])),
                Td(row["name"]),
                Td(row.get("status", "Draft")),
                Td(
                    UkIcon("file-check", height=15, width=15, cls="text-success")
                    if row.get("ifc_file_path")
                    else UkIcon(
                        "file-x", height=15, width=15, cls="text-muted-foreground"
                    )
                ),
                Td(row.get("created_at", "-")),
                Td(row.get("updated_at", "-")),
                Td(
                    DivLAligned(
                        *(
                            [
                                ViewAction(
                                    href=f"/viewer?project_id={row['id']}",
                                    title="Open IFC in Viewer",
                                )
                            ]
                            if row.get("ifc_file_path")
                            else []
                        ),
                        EditAction(href=f"/projects/{row['id']}/edit"),
                        DeleteAction(action=f"/projects/{row['id']}/delete"),
                        cls="gap-1",
                    )
                ),
            )
        )
    return rendered


def projects_page(rows: list[dict], message: str | None = None):
    msg_block = ()
    if message:
        msg_block = (Alert(message, cls=AlertT.success),)

    return DashboardLayout(
        Container(
            DivFullySpaced(
                Div(
                    H1("Projects"),
                    Subtitle("Create, track, and update your project records."),
                ),
                CreateAction(href="/projects/new", title="New Project"),
            ),
            *msg_block,
            Card(
                Table(
                    Thead(
                        Tr(
                            Th("ID"),
                            Th("Name"),
                            Th("Status"),
                            Th("IFC"),
                            Th("Created"),
                            Th("Updated"),
                            Th("Actions"),
                        )
                    ),
                    Tbody(*projects_table_rows(rows)),
                    cls=TableT.hover,
                ),
                header=H3("Project Registry"),
            ),
            cls="space-y-4",
        )
    )
