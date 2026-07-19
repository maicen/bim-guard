from fasthtml.common import Button, Details, Div, P, Span, Summary, Tbody, Td, Th, Thead, Tr
from monsterui.all import Form, Input, Table

from app.components.ui import (
    ActionRow,
    AlertSpec,
    CancelAction,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Checkbox,
    FieldSpec,
    FormLabel,
    LinkButton,
    MessageAlert,
    SaveAction,
    SelectField,
    SelectOptionSpec,
    SubmitButton,
    TableActionsMenu,
    TableSpec,
    TextAreaField,
    TextInputField,
    build_table_rows,
)

IFC_CLASS_OPTIONS = [
    "IfcProject",
    "IfcSite",
    "IfcBuilding",
    "IfcBuildingStorey",
    "IfcSpace",
    "IfcZone",
    # Vertical enclosure
    "IfcWall",
    "IfcCurtainWall",
    # Openings
    "IfcDoor",
    "IfcWindow",
    # Horizontal structure
    "IfcSlab",
    "IfcRoof",
    "IfcCovering",
    # Vertical structure
    "IfcColumn",
    "IfcBeam",
    "IfcMember",
    "IfcFooting",
    # Circulation
    "IfcStair",
    "IfcStairFlight",
    "IfcRamp",
    "IfcRampFlight",
    "IfcRailing",
    # Plumbing / fixtures
    "IfcSanitaryTerminal",
    "IfcFlowTerminal",
    # Fire / life safety
    "IfcAlarm",
    "IfcSensor",
    # Furniture
    "IfcFurnishingElement",
    # MEP / piping types
    "IfcPipeSegment",
    "IfcPipeFitting",
    "IfcValve",
    "IfcFlowMovingDevice",
    "IfcFlowStorageDevice",
    "IfcFlowController",
    "IfcDistributionFlowElement",
    "IfcDistributionElement",
    "Unspecified",
]

MECHANISM_OPTIONS = [
    SelectOptionSpec(label="— Any —", value=""),
    SelectOptionSpec(label="OBC", value="OBC"),
    SelectOptionSpec(label="GC-001", value="GC-001"),
    SelectOptionSpec(label="CC-001", value="CC-001"),
    SelectOptionSpec(label="MC-001", value="MC-001"),
    SelectOptionSpec(label="IFC", value="IFC"),
]

RULE_CATEGORY_OPTIONS = [
    SelectOptionSpec(label="property_check", value="property_check"),
    SelectOptionSpec(label="scoring_model", value="scoring_model"),
    SelectOptionSpec(label="threshold_band", value="threshold_band"),
    SelectOptionSpec(label="material_property", value="material_property"),
    SelectOptionSpec(label="reference_config", value="reference_config"),
    SelectOptionSpec(label="mitigation", value="mitigation"),
]

# Matches Module4_Comparator's supported operators (module4_comparator/__init__.py docstring).
OPERATOR_OPTIONS = [
    SelectOptionSpec(label="— none —", value=""),
    SelectOptionSpec(label=">=", value=">="),
    SelectOptionSpec(label="<=", value="<="),
    SelectOptionSpec(label=">", value=">"),
    SelectOptionSpec(label="<", value="<"),
    SelectOptionSpec(label="==", value="=="),
    SelectOptionSpec(label="!=", value="!="),
    SelectOptionSpec(label="between", value="between"),
    SelectOptionSpec(label="exists", value="exists"),
    SelectOptionSpec(label="not_exists", value="not_exists"),
    SelectOptionSpec(label="matches", value="matches"),
]

SEVERITY_OPTIONS = [
    SelectOptionSpec(label="mandatory", value="mandatory"),
    SelectOptionSpec(label="recommended", value="recommended"),
    SelectOptionSpec(label="informational", value="informational"),
]

_MECHANISM_BADGE = {
    "OBC": "bg-blue-100 text-blue-800",
    "GC-001": "bg-amber-100 text-amber-800",
    "CC-001": "bg-rose-100 text-rose-800",
    "MC-001": "bg-green-100 text-green-800",
    "IFC": "bg-purple-100 text-purple-800",
}


def _mechanism_badge(mechanism: str):
    mech = (mechanism or "").upper()
    css = _MECHANISM_BADGE.get(mech, "bg-muted text-muted-foreground")
    return Span(mech or "—", cls=f"text-xs font-medium px-2 py-0.5 rounded {css}")


def _select_all_checkbox():
    """Header checkbox that toggles every rule_ids checkbox in its own form."""
    return Input(
        type="checkbox",
        cls="h-4 w-4",
        title="Select all",
        onclick=(
            "this.closest('form').querySelectorAll('input[name=rule_ids]')"
            ".forEach(function(cb){cb.checked = this.checked}, this)"
        ),
    )


def rules_table_rows(rows: list[dict]):
    def _build_row(row: dict):
        return Tr(
            Td(Input(type="checkbox", name="rule_ids", value=str(row["id"]), cls="h-4 w-4")),
            Td(row.get("reference", "-")),
            Td(_mechanism_badge(row.get("mechanism", ""))),
            Td(row.get("rule_type", "-")),
            Td(row.get("target_ifc_class", "-")),
            Td(row.get("rule_category", "-"), cls="text-xs text-muted-foreground"),
            Td(row.get("updated_at", "-"), cls="text-sm text-muted-foreground"),
            Td(
                (row.get("description") or "")[:100]
                + ("..." if len(row.get("description") or "") > 100 else ""),
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
        TableSpec(empty_message="No rules available yet.", empty_colspan=9),
    )


def rules_folders_panel(folders: list[dict], message: str | None = None, level: str = "success"):
    """Named rule folders (ruleset_id groups), expandable to show and manage
    the rules inside — includes both webpage-extracted folders and built-in
    seeded rulesets (e.g. OBC-PART9). Each folder dict should carry a "rules"
    key (list of rule rows) for the expanded table; falls back to empty."""
    alert = MessageAlert(AlertSpec(message=message, level=level))

    if not folders:
        body = P(
            "No named folders yet. Folders are created when you save extracted "
            "rules under a name in the Rule Extraction Studio.",
            cls="text-sm text-muted-foreground",
        )
    else:
        items = []
        for f in folders:
            ruleset_id = f["ruleset_id"]
            folder_rules = f.get("rules") or []
            rename_form = Form(
                Input(type="hidden", name="old_id", value=ruleset_id),
                Input(
                    name="new_id",
                    value=ruleset_id,
                    cls="text-xs h-8",
                    style="width:180px;padding:2px 8px;border-radius:6px;",
                ),
                Button(
                    "Rename",
                    type="submit",
                    cls=(
                        "text-xs px-2 py-1 rounded bg-secondary "
                        "text-secondary-foreground hover:opacity-90"
                    ),
                ),
                hx_post="/api/rules/folders/rename",
                hx_target="#rule-folders-panel",
                hx_swap="outerHTML",
                cls="flex items-center gap-2",
            )
            delete_folder_form = Form(
                Input(type="hidden", name="ruleset_id", value=ruleset_id),
                Button(
                    "Delete Folder",
                    type="submit",
                    cls=(
                        "text-xs px-2 py-1 rounded bg-destructive/10 text-destructive "
                        "hover:bg-destructive/20"
                    ),
                ),
                hx_post="/api/rules/folders/delete",
                hx_target="#rule-folders-panel",
                hx_swap="outerHTML",
                hx_confirm=(
                    f"Delete folder \"{ruleset_id}\" and all {f['count']} rule(s) "
                    "inside it? This cannot be undone."
                ),
                cls="flex items-center",
            )
            rule_table = (
                Form(
                    Div(
                        SubmitButton(
                            "Delete Selected",
                            variant="secondary",
                            cls="text-xs text-destructive",
                        ),
                        cls="flex justify-end mb-1",
                    ),
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th(_select_all_checkbox()),
                                    Th("Reference"),
                                    Th("Mechanism"),
                                    Th("Type"),
                                    Th("Target Class"),
                                    Th("Category"),
                                    Th("Updated"),
                                    Th("Description"),
                                    Th("Actions"),
                                )
                            ),
                            Tbody(*rules_table_rows(folder_rules)),
                            cls="w-full min-w-[1100px]",
                        ),
                        cls="w-full overflow-auto max-h-[50vh] border rounded-md",
                    ),
                    method="post",
                    action="/api/rules/bulk-delete",
                    onsubmit=(
                        "return confirm('Delete the selected rule(s)? "
                        "This cannot be undone.')"
                    ),
                )
                if folder_rules
                else P("No rules found in this folder.", cls="text-xs text-muted-foreground")
            )
            items.append(
                Details(
                    Summary(
                        Span(ruleset_id, cls="text-sm font-medium"),
                        Span(
                            f"{f['count']} rule(s)",
                            cls="text-xs text-muted-foreground ml-2",
                        ),
                        cls="cursor-pointer select-none py-2 list-none",
                    ),
                    Div(rename_form, delete_folder_form, cls="flex items-center gap-3 mb-3"),
                    rule_table,
                    cls="py-1 border-b last:border-0",
                )
            )
        body = Div(*items)

    return Div(
        *alert,
        Card(
            CardHeader(CardTitle("Rule Folders")),
            CardContent(body),
        ),
        id="rule-folders-panel",
        cls="space-y-2",
    )


def rules_panel(rows: list[dict], message: str | None = None, level: str = "success"):
    alert = MessageAlert(AlertSpec(message=message, level=level))

    return Div(
        *alert,
        Card(
            CardHeader(
                Div(
                    CardTitle("Rule Library"),
                    LinkButton(
                        "Import JSON Ruleset",
                        href="/library/rules/import-json",
                        variant="secondary",
                        cls="text-sm",
                    ),
                    cls="flex items-center justify-between gap-2 flex-wrap",
                )
            ),
            CardContent(
                Form(
                    Div(
                        SubmitButton(
                            "Delete Selected",
                            variant="secondary",
                            cls="text-sm text-destructive",
                        ),
                        cls="flex justify-end mb-2",
                    ),
                    Div(
                        Div(
                            Table(
                                Thead(
                                    Tr(
                                        Th(_select_all_checkbox()),
                                        Th("Reference"),
                                        Th("Mechanism"),
                                        Th("Type"),
                                        Th("Target Class"),
                                        Th("Category"),
                                        Th("Updated"),
                                        Th("Description"),
                                        Th("Actions"),
                                    )
                                ),
                                Tbody(*rules_table_rows(rows)),
                                cls="w-full min-w-[1200px]",
                            ),
                            cls="w-full min-w-0 max-h-[65vh] overflow-auto",
                        ),
                        cls="w-full min-w-0",
                    ),
                    method="post",
                    action="/api/rules/bulk-delete",
                    onsubmit=(
                        "return confirm('Delete the selected rule(s)? "
                        "This cannot be undone.')"
                    ),
                    cls="w-full min-w-0 pt-0",
                ),
            ),
            cls="w-full max-w-full h-full min-h-0 overflow-hidden",
        ),
        cls="space-y-4",
    )


def _decode_json_field(value) -> str:
    """Unwrap a JSON-encoded DB scalar (e.g. '800' or 'null') to a plain form value."""
    if value is None or value == "":
        return ""
    try:
        import json

        decoded = json.loads(value)
        return "" if decoded is None else str(decoded)
    except (TypeError, ValueError):
        return str(value)


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
            SelectOptionSpec(label=selected_ifc_class, value=selected_ifc_class, selected=True),
        )

    selected_mech = rule.get("mechanism", "")
    mech_options = [
        SelectOptionSpec(label=o.label, value=o.value, selected=o.value == selected_mech)
        for o in MECHANISM_OPTIONS
    ]

    selected_cat = rule.get("rule_category", "property_check")
    cat_options = [
        SelectOptionSpec(label=o.label, value=o.value, selected=o.value == selected_cat)
        for o in RULE_CATEGORY_OPTIONS
    ]

    selected_operator = rule.get("operator", "")
    operator_options = [
        SelectOptionSpec(label=o.label, value=o.value, selected=o.value == selected_operator)
        for o in OPERATOR_OPTIONS
    ]

    selected_severity = rule.get("severity", "mandatory")
    severity_options = [
        SelectOptionSpec(label=o.label, value=o.value, selected=o.value == selected_severity)
        for o in SEVERITY_OPTIONS
    ]

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
                        value=rule.get("rule_type", "numeric_comparison"),
                        required=True,
                    )
                ),
                SelectField(
                    FieldSpec(
                        label="Mechanism",
                        field_id="mechanism",
                        name="mechanism",
                    ),
                    mech_options,
                ),
                TextInputField(
                    FieldSpec(
                        label="Ruleset ID",
                        field_id="ruleset_id",
                        name="ruleset_id",
                        value=rule.get("ruleset_id", ""),
                        placeholder="e.g. OBC-PART9",
                    )
                ),
                SelectField(
                    FieldSpec(
                        label="Rule Category",
                        field_id="rule_category",
                        name="rule_category",
                    ),
                    cat_options,
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
                Span("Compliance Check", cls="text-sm font-semibold block pt-2"),
                TextInputField(
                    FieldSpec(
                        label="Property Set",
                        field_id="property_set",
                        name="property_set",
                        value=rule.get("property_set", ""),
                        placeholder="e.g. Pset_WindowCommon",
                    )
                ),
                TextInputField(
                    FieldSpec(
                        label="Property Name",
                        field_id="property_name",
                        name="property_name",
                        value=rule.get("property_name", ""),
                        placeholder="e.g. ClearOpeningArea",
                    )
                ),
                TextInputField(
                    FieldSpec(
                        label="Fallback Property",
                        field_id="fallback_property",
                        name="fallback_property",
                        value=rule.get("fallback_property", ""),
                        placeholder="tried when Property Name is absent",
                    )
                ),
                SelectField(
                    FieldSpec(
                        label="Operator",
                        field_id="operator",
                        name="operator",
                    ),
                    operator_options,
                ),
                Div(
                    TextInputField(
                        FieldSpec(
                            label="Check Value",
                            field_id="check_value",
                            name="check_value",
                            value=_decode_json_field(rule.get("check_value")),
                            placeholder="single-threshold operators",
                        ),
                        input_type="number",
                    ),
                    TextInputField(
                        FieldSpec(
                            label="Value Min",
                            field_id="value_min",
                            name="value_min",
                            value=_decode_json_field(rule.get("value_min")),
                            placeholder="'between' operator",
                        ),
                        input_type="number",
                    ),
                    TextInputField(
                        FieldSpec(
                            label="Value Max",
                            field_id="value_max",
                            name="value_max",
                            value=_decode_json_field(rule.get("value_max")),
                            placeholder="'between' operator",
                        ),
                        input_type="number",
                    ),
                    cls="grid grid-cols-3 gap-3",
                ),
                TextInputField(
                    FieldSpec(
                        label="Unit",
                        field_id="unit",
                        name="unit",
                        value=rule.get("unit", ""),
                        placeholder="e.g. mm, m2",
                    )
                ),
                Span("Classification & Metadata", cls="text-sm font-semibold block pt-2"),
                SelectField(
                    FieldSpec(
                        label="Severity",
                        field_id="severity",
                        name="severity",
                    ),
                    severity_options,
                ),
                TextInputField(
                    FieldSpec(
                        label="Keyword",
                        field_id="keyword",
                        name="keyword",
                        value=rule.get("keyword", ""),
                        placeholder="e.g. shall",
                    )
                ),
                TextInputField(
                    FieldSpec(
                        label="Compliance Type",
                        field_id="compliance_type",
                        name="compliance_type",
                        value=rule.get("compliance_type", ""),
                        placeholder="e.g. prescriptive",
                    )
                ),
                TextInputField(
                    FieldSpec(
                        label="Confidence (0-1)",
                        field_id="confidence",
                        name="confidence",
                        value=str(rule.get("confidence") or ""),
                        placeholder="e.g. 0.8",
                    ),
                    input_type="number",
                ),
                Div(
                    Checkbox(
                        id="needs_review",
                        name="needs_review",
                        checked=bool(rule.get("needs_review")),
                    ),
                    FormLabel("Needs review", fr="needs_review", cls="cursor-pointer"),
                    cls="flex items-center gap-2",
                ),
                Span("Source", cls="text-sm font-semibold block pt-2"),
                TextAreaField(
                    FieldSpec(
                        label="Source Text (original document paragraph)",
                        field_id="source_text",
                        name="source_text",
                        value=rule.get("source_text", ""),
                        placeholder="No source text recorded for this rule.",
                    ),
                    rows=6,
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
