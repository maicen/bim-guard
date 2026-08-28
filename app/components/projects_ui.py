import json

from fasthtml.common import A, Div, Tbody, Td, Th, Thead, Tr
from monsterui.all import (
    H1,
    H2,
    Button,
    ButtonT,
    Container,
    DivFullySpaced,
    DivVStacked,
    Form,
    FormLabel,
    Input,
    Label,
    Subtitle,
    Table,
    TableT,
    UkIcon,
)

from app.components.layout import DashboardLayout
from app.constants import ANALYSIS_TYPES, DEFAULT_ANALYSIS_TYPE, normalise_analysis_types
from app.components.ui import (
    ActionRow,
    AlertSpec,
    CancelAction,
    CheckboxGroupField,
    CheckboxOptionSpec,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CreateAction,
    DropdownMenuItem,
    FieldSpec,
    MessageAlert,
    SaveAction,
    SelectField,
    SelectOptionSpec,
    TableActionsMenu,
    TableSpec,
    TextAreaField,
    TextInputField,
    build_table_rows,
)


#: What each analysis type does, shown under its checkbox. Keyed by the values
#: in :data:`app.constants.ANALYSIS_TYPES` so a new type surfaces here as a
#: missing hint rather than a missing box.
_ANALYSIS_TYPE_HINTS: dict[str, str] = {
    "Piping (Corrosive)": "GC-001 galvanic, CC-001 crevice and MC-001 microbial corrosion checks.",
    "Halo": "Blue Halo seismic bracing clearance at LOD 300.",
    "Architecture": "Architectural code checks — doors, windows, stairs, egress.",
}


def _analysis_types_field(project: dict):
    """Build the analysis-type checkbox group for the project form.

    A new project with nothing stored starts on
    :data:`app.constants.DEFAULT_ANALYSIS_TYPE`, so the common case is one click
    from done. An existing project reflects exactly what it was saved with.
    """
    selected = normalise_analysis_types(project.get("analysis_types")) or (
        [DEFAULT_ANALYSIS_TYPE] if not project else []
    )
    return CheckboxGroupField(
        label="Analysis Types",
        name="analysis_types",
        options=[
            CheckboxOptionSpec(
                label=analysis_type,
                value=analysis_type,
                checked=analysis_type in selected,
                hint=_ANALYSIS_TYPE_HINTS.get(analysis_type, ""),
            )
            for analysis_type in ANALYSIS_TYPES
        ],
        help_text=(
            "Pick at least one. The first one ticked is the project's primary "
            "analysis, and is where you land after creating it."
        ),
    )


def _ifc_dropzone_field():
    """File picker that also accepts a dropped file.

    The input itself stays a plain ``<input type=file>``: it is what the form
    actually submits, and it keeps working with JavaScript off or still loading.
    ``static/js/upload-dropzone.js`` upgrades the surrounding label into a drop
    target when it runs, which is why the markup carries the ids that script
    looks for rather than any behaviour of its own.
    """
    return DivVStacked(
        FormLabel("IFC Model", fr="ifc_file"),
        Label(
            Div(
                UkIcon("upload-cloud", cls="w-8 h-8 mx-auto text-muted-foreground"),
                Div("Drop an IFC file here, or click to choose", cls="text-sm mt-2"),
                Div(".ifc only", cls="text-xs text-muted-foreground mt-1"),
                cls="text-center",
            ),
            Input(
                id="ifc_file",
                name="ifc_file",
                type="file",
                accept=".ifc",
                cls="sr-only",
            ),
            id="project-ifc-dropzone",
            for_="ifc_file",
            cls=(
                "block border-2 border-dashed border-border rounded-lg p-8 "
                "cursor-pointer transition-colors hover:border-primary hover:bg-muted/40"
            ),
        ),
        Div(id="project-ifc-filename", cls="text-xs text-muted-foreground"),
        cls="space-y-1 items-stretch",
    )


def project_form(title: str, action: str, project: dict | None = None, include_ifc: bool = False):
    project = project or {}
    ifc_field = (_ifc_dropzone_field(),) if include_ifc else ()
    return Card(
        CardHeader(
            CardTitle(H2(title)),
            Subtitle("Manage your BIM compliance projects."),
        ),
        CardContent(
            Form(
                TextInputField(
                    FieldSpec(
                        label="Project Name",
                        field_id="name",
                        name="name",
                        value=project.get("name", ""),
                        placeholder="e.g. Airport Terminal A",
                        required=True,
                    )
                ),
                TextAreaField(
                    FieldSpec(
                        label="Description",
                        field_id="description",
                        name="description",
                        value=project.get("description", ""),
                        placeholder="Scope, goals, and notes",
                    ),
                    rows=5,
                ),
                SelectField(
                    FieldSpec(label="Status", field_id="status", name="status"),
                    [
                        SelectOptionSpec(
                            "Draft",
                            "Draft",
                            selected=project.get("status") == "Draft",
                        ),
                        SelectOptionSpec(
                            "Active",
                            "Active",
                            selected=project.get("status") == "Active",
                        ),
                        SelectOptionSpec(
                            "Archived",
                            "Archived",
                            selected=project.get("status") == "Archived",
                        ),
                    ],
                ),
                _analysis_types_field(project),
                *ifc_field,
                ActionRow(
                    SaveAction("Save Project"),
                    CancelAction(href="/projects/archive"),
                    cls="gap-2",
                ),
                method="post",
                action=action,
                enctype="multipart/form-data" if include_ifc else None,
                cls="space-y-4",
            )
        ),
    )


def projects_table_rows(rows: list[dict]):
    def _actions_menu(row: dict):
        return TableActionsMenu(
            edit_href=f"/projects/{row['id']}/edit",
            delete_action=f"/projects/{row['id']}/delete",
            view_href=(f"/viewer?project_id={row['id']}" if row.get("ifc_file_path") else None),
            view_label="Open IFC in Viewer",
            extra_items=(
                [
                    DropdownMenuItem(
                        "Quality Improvements",
                        onclick=f"window.location.href='/projects/{row['id']}/enhancements'",
                    )
                ]
                if row.get("ifc_file_path")
                else None
            ),
        )

    def _build_row(row: dict):
        return Tr(
            Td(str(row["id"])),
            Td(row["name"]),
            Td(row.get("status", "Draft")),
            Td(
                UkIcon("file-check", height=15, width=15, cls="text-success")
                if row.get("ifc_file_path")
                else UkIcon("file-x", height=15, width=15, cls="text-muted-foreground")
            ),
            Td(row.get("created_at", "-")),
            Td(row.get("updated_at", "-")),
            Td(_actions_menu(row)),
        )

    return build_table_rows(
        rows,
        _build_row,
        TableSpec(
            empty_message="No projects yet. Create your first one.",
            empty_colspan=7,
        ),
    )


def projects_page(rows: list[dict], message: str | None = None):
    msg_block = MessageAlert(AlertSpec(message=message, level="success"))

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
                CardHeader(CardTitle("Project Registry")),
                CardContent(
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
                    )
                ),
            ),
            cls="space-y-4",
        )
    )


def project_enhancements_page(
    project: dict,
    lineage_rows: list[dict],
    *,
    message: str | None = None,
    level: str = "success",
):
    """Render the explicit IFC quality-improvement command and immutable history."""
    history_rows = [
        Tr(
            Td(f"v{row.get('source_version', 0)}"),
            Td(f"v{row.get('version', '?')}"),
            Td("Completed"),
            Td(str(row.get("source_reference") or ""), cls="max-w-64 truncate font-mono text-xs"),
            Td(str(row.get("output_reference") or ""), cls="max-w-64 truncate font-mono text-xs"),
            Td(
                json.dumps(row.get("summary") or {}, sort_keys=True),
                cls="max-w-72 truncate font-mono text-xs",
            ),
            Td(str(row.get("created_at") or "-")),
            Td(
                A(
                    Button("Download", cls=ButtonT.secondary),
                    href=(
                        f"/projects/{project['id']}/enhancements/{row['id']}/download"
                    ),
                )
            ),
        )
        for row in lineage_rows
    ]

    return DashboardLayout(
        Container(
            H1(f"Quality Improvements - {project.get('name', 'Project')}"),
            Subtitle(
                "Improve and persist a new IFC version without modifying the uploaded source. "
                "Identical source files reuse the existing result."
            ),
            *MessageAlert(AlertSpec(message=message, level=level)),
            Card(
                CardHeader(CardTitle("Run IFC Quality Improvements")),
                CardContent(
                    Form(
                        DivVStacked(
                            FormLabel("Enhancement authorization token", fr="enhancement_token"),
                            Input(
                                id="enhancement_token",
                                name="enhancement_token",
                                type="password",
                                required=True,
                                autocomplete="off",
                            ),
                            cls="space-y-1",
                        ),
                        Button("Run Quality Improvements", type="submit", cls=ButtonT.primary),
                        method="post",
                        action=f"/projects/{project['id']}/enhance",
                        cls="space-y-4",
                    )
                ),
            ),
            Card(
                CardHeader(CardTitle("Persisted Improvement History")),
                CardContent(
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("Source Version"),
                                    Th("Generated Version"),
                                    Th("Status"),
                                    Th("Source"),
                                    Th("Generated Artifact"),
                                    Th("Summary"),
                                    Th("Created"),
                                    Th("Artifact"),
                                )
                            ),
                            Tbody(
                                *history_rows
                                if history_rows
                                else Tr(Td("No enhanced versions yet.", colspan="8"))
                            ),
                            cls=TableT.hover,
                        ),
                        cls="w-full overflow-x-auto",
                    )
                ),
            ),
            cls="space-y-4",
        )
    )
