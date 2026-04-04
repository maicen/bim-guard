from fasthtml.common import Div, Option, Tbody, Td, Th, Thead, Tr
from app.components.ui import (
    CancelAction,
    DeleteAction,
    EditAction,
    SaveAction,
    ViewAction,
)
from monsterui.all import (
    Alert,
    AlertT,
    Card,
    CardBody,
    CardHeader,
    CardTitle,
    DivLAligned,
    Form,
    FormLabel,
    Input,
    Select,
    Table,
    TextArea,
)


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
    if not rows:
        return [
            Tr(
                Td(
                    "No rules available yet.",
                    colspan="6",
                    cls="text-center text-muted-foreground",
                )
            )
        ]

    rendered = []
    for row in rows:
        rendered.append(
            Tr(
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
                    DivLAligned(
                        ViewAction(href=f"/library/rules/{row['id']}"),
                        EditAction(href=f"/library/rules/{row['id']}/edit"),
                        DeleteAction(action=f"/library/rules/{row['id']}/delete"),
                        cls="gap-1",
                    )
                ),
            )
        )
    return rendered


def rules_panel(rows: list[dict], message: str | None = None, level: str = "success"):
    alert = ()
    if message:
        cls = AlertT.success if level == "success" else AlertT.warning
        alert = (Alert(message, cls=cls),)

    return Div(
        *alert,
        Card(
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
            ),
            header=CardHeader(CardTitle("Rule Library")),
        ),
        cls="space-y-4",
    )


def rule_form(title: str, action: str, rule: dict | None = None):
    rule = rule or {}
    selected_ifc_class = rule.get("target_ifc_class", "")
    ifc_options = [
        Option(
            ifc_class,
            value=ifc_class,
            selected=selected_ifc_class == ifc_class,
        )
        for ifc_class in IFC_CLASS_OPTIONS
    ]
    if selected_ifc_class and selected_ifc_class not in IFC_CLASS_OPTIONS:
        ifc_options.insert(
            0,
            Option(
                selected_ifc_class,
                value=selected_ifc_class,
                selected=True,
            ),
        )

    return Card(
        CardHeader(CardTitle(title)),
        CardBody(
            Form(
                DivLAligned(
                    SaveAction("Save Rule"),
                    CancelAction(href="/library/rules"),
                    cls="gap-2",
                ),
                Div(
                    FormLabel("Reference", fr="reference"),
                    Input(
                        id="reference",
                        name="reference",
                        value=rule.get("reference", ""),
                        placeholder="e.g. REQ-ISO-001",
                        required=True,
                    ),
                    cls="space-y-1",
                ),
                Div(
                    FormLabel("Rule Type", fr="rule_type"),
                    Input(
                        id="rule_type",
                        name="rule_type",
                        value=rule.get("rule_type", "Required"),
                        required=True,
                    ),
                    cls="space-y-1",
                ),
                Div(
                    FormLabel("Target IFC Class", fr="target_ifc_class"),
                    Select(
                        *ifc_options,
                        id="target_ifc_class",
                        name="target_ifc_class",
                        required=True,
                    ),
                    cls="space-y-1",
                ),
                Div(
                    FormLabel("Description", fr="description"),
                    TextArea(
                        rule.get("description", ""),
                        id="description",
                        name="description",
                        rows="5",
                        required=True,
                    ),
                    cls="space-y-1",
                ),
                Div(
                    FormLabel("Parameters (JSON or text)", fr="parameters"),
                    TextArea(
                        rule.get("parameters", "{}"),
                        id="parameters",
                        name="parameters",
                        rows="6",
                    ),
                    cls="space-y-1",
                ),
                method="post",
                action=action,
                cls="space-y-4",
            )
        ),
    )
