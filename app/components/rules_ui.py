from fasthtml.common import Div, Tbody, Td, Th, Thead, Tr
from app.components.ui import (
    ActionRow,
    AlertSpec,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CancelAction,
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
from monsterui.all import Form, Table


IFC_CLASS_OPTIONS = [
    "IfcProject",
    "IfcSite",
    "IfcBuilding",
    "IfcBuildingStorey",
    "IfcSpace",
    "IfcWall",
    "IfcDoor",
    "IfcWindow",
    "IfcSlab",
    "IfcRoof",
    "IfcColumn",
    "IfcBeam",
    "IfcStair",
    "IfcRailing",
    "IfcFlowTerminal",
]


def rules_table_rows(rows: list[dict]):
    def _build_row(row: dict):
        return Tr(
            Td(row.get("reference", "-")),
            Td(row.get("rule_type", "Required")),
            Td(row.get("target_ifc_class", "-")),
            Td(row.get("updated_at", "-"), cls="text-sm text-muted-foreground"),
            Td(
                (row.get("description") or "")[:120]
                + ("..." if len(row.get("description") or "") > 120 else ""),
                cls="text-sm text-muted-foreground",
            ),
            Td(
                TableActionsMenu(
                    edit_href=f"/library/rules/{row['id']}/edit",
                    delete_action=f"/library/rules/{row['id']}/delete",
                    view_href=f"/library/rules/{row['id']}",
                )
            ),
        )

    return build_table_rows(
        rows,
        _build_row,
        TableSpec(empty_message="No rules available yet.", empty_colspan=6),
    )


def rules_panel(rows: list[dict], message: str | None = None, level: str = "success"):
    alert = MessageAlert(AlertSpec(message=message, level=level))

    return Div(
        *alert,
        Card(
            CardHeader(CardTitle("Rule Library")),
            CardContent(
                Table(
                    Thead(
                        Tr(
                            Th("Reference"),
                            Th("Type"),
                            Th("Target Class"),
                            Th("Updated"),
                            Th("Description"),
                            Th("Actions"),
                        )
                    ),
                    Tbody(*rules_table_rows(rows)),
                    cls="min-w-[980px]",
                )
            ),
        ),
        cls="space-y-4",
    )


def rule_form(title: str, action: str, rule: dict | None = None):
    rule = rule or {}
    selected_ifc_class = rule.get("target_ifc_class", "")
    ifc_options = [
        SelectOptionSpec(
            label=ifc_class,
            value=ifc_class,
            selected=selected_ifc_class == ifc_class,
        )
        for ifc_class in IFC_CLASS_OPTIONS
    ]
    if selected_ifc_class and selected_ifc_class not in IFC_CLASS_OPTIONS:
        ifc_options.insert(
            0,
            SelectOptionSpec(
                label=selected_ifc_class,
                value=selected_ifc_class,
                selected=True,
            ),
        )

    return Card(
        CardHeader(CardTitle(title)),
        CardContent(
            Form(
                ActionRow(
                    SaveAction("Save Rule"),
                    CancelAction(href="/library/rules"),
                    cls="gap-2",
                ),
                TextInputField(
                    FieldSpec(
                        label="Reference",
                        field_id="reference",
                        name="reference",
                        value=rule.get("reference", ""),
                        placeholder="e.g. REQ-ISO-001",
                        required=True,
                    )
                ),
                TextInputField(
                    FieldSpec(
                        label="Rule Type",
                        field_id="rule_type",
                        name="rule_type",
                        value=rule.get("rule_type", "Required"),
                        required=True,
                    )
                ),
                SelectField(
                    FieldSpec(
                        label="Target IFC Class",
                        field_id="target_ifc_class",
                        name="target_ifc_class",
                        required=True,
                    ),
                    ifc_options,
                ),
                TextAreaField(
                    FieldSpec(
                        label="Description",
                        field_id="description",
                        name="description",
                        value=rule.get("description", ""),
                        required=True,
                    ),
                    rows=5,
                ),
                TextAreaField(
                    FieldSpec(
                        label="Parameters (JSON or text)",
                        field_id="parameters",
                        name="parameters",
                        value=rule.get("parameters", "{}"),
                    ),
                    rows=6,
                ),
                method="post",
                action=action,
                cls="space-y-4",
            )
        ),
    )
