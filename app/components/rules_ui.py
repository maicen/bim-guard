import json

from fasthtml.common import Div, Input, Pre, Span, Tbody, Td, Th, Thead, Tr
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
from monsterui.all import Form, FormLabel, Table


# ── IFC class list ────────────────────────────────────────────────────────────
IFC_CLASS_OPTIONS = [
    "IfcBeam", "IfcBuildingElementProxy", "IfcBuildingStorey", "IfcBuilding",
    "IfcColumn", "IfcCovering", "IfcDoor", "IfcFlowTerminal", "IfcFooting",
    "IfcFurnishingElement", "IfcMember", "IfcOpeningElement", "IfcPile",
    "IfcPlate", "IfcProject", "IfcRailing", "IfcRamp", "IfcRampFlight",
    "IfcRoof", "IfcSite", "IfcSlab", "IfcSpace", "IfcStair", "IfcStairFlight",
    "IfcWall", "IfcWallStandardCase", "IfcWindow",
]

_RULE_TYPE_OPTIONS = [
    "numeric_range", "numeric_comparison", "exists_check",
    "regex_match", "classification", "spatial_clearance", "prohibition",
]
_OPERATOR_OPTIONS  = [">=", "<=", "==", "!=", "between", "exists", "matches", "not_exists"]
_UNIT_OPTIONS      = ["mm", "m", "m2", "deg", "ratio", "min", ""]
_SEVERITY_OPTIONS  = ["mandatory", "recommended", "informational"]
_KEYWORD_OPTIONS   = ["shall", "must", "should", "may", ""]
_COMPLIANCE_OPTIONS = ["prescriptive", "performance", "descriptive", ""]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _section_header(label: str):
    """Visual section divider inside the form."""
    return Div(
        Span(label, cls="text-xs font-semibold uppercase tracking-widest text-muted-foreground"),
        cls="border-t pt-4 mt-2 mb-1",
    )


def _select(label: str, name: str, options: list[str], current: str, *, required=False):
    specs = [
        SelectOptionSpec(label=o or "—", value=o, selected=(current == o))
        for o in options
    ]
    return SelectField(
        FieldSpec(label=label, field_id=name, name=name, required=required),
        specs,
    )


def _text(label, name, value="", placeholder="", *, required=False, input_type="text"):
    return TextInputField(
        FieldSpec(
            label=label, field_id=name, name=name,
            value=str(value) if value is not None else "",
            placeholder=placeholder, required=required,
        )
    )


def _textarea(label, name, value="", rows=3):
    return TextAreaField(
        FieldSpec(label=label, field_id=name, name=name, value=value or ""),
        rows=rows,
    )


def _checkbox(label: str, name: str, checked: bool):
    return Div(
        FormLabel(label, fr=name, cls="text-sm font-medium"),
        Input(
            id=name, name=name, type="checkbox", value="1",
            checked=checked or None,
            cls="ml-2 h-4 w-4 rounded border-input",
        ),
        cls="flex items-center gap-2 py-1",
    )


# ── Table rows ────────────────────────────────────────────────────────────────

def rules_table_rows(rows: list[dict]):
    def _build_row(row: dict):
        return Tr(
            Td(row.get("reference", "-")),
            Td(row.get("rule_type", "-")),
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
                            Th("Reference"), Th("Type"), Th("Target Class"),
                            Th("Updated"), Th("Description"), Th("Actions"),
                        )
                    ),
                    Tbody(*rules_table_rows(rows)),
                    cls="min-w-[980px]",
                )
            ),
        ),
        cls="space-y-4",
    )


# ── Rule form (create + edit) ─────────────────────────────────────────────────

def rule_form(title: str, action: str, rule: dict | None = None):
    rule = rule or {}

    def _v(key, default=""):
        """Get a rule field value, decoding JSON-encoded numerics when needed."""
        val = rule.get(key, default)
        if val is None:
            return default
        # value_min / value_max / check_value are stored as JSON strings
        if key in ("check_value", "value_min", "value_max"):
            try:
                decoded = json.loads(str(val))
                return "" if decoded is None else str(decoded)
            except (json.JSONDecodeError, TypeError):
                return str(val) if val else ""
        return str(val)

    # Rule JSON preview (read-only)
    rule_json_str = json.dumps(
        {k: v for k, v in rule.items() if k not in ("created_at", "updated_at")},
        indent=2,
    ) if rule else ""

    current_ifc = _v("target_ifc_class")
    ifc_opts = [
        SelectOptionSpec(label=c, value=c, selected=(current_ifc == c))
        for c in IFC_CLASS_OPTIONS
    ]
    if current_ifc and current_ifc not in IFC_CLASS_OPTIONS:
        ifc_opts.insert(0, SelectOptionSpec(label=current_ifc, value=current_ifc, selected=True))

    return Card(
        CardHeader(CardTitle(title, cls="text-4xl font-bold text-center")),
        CardContent(
            Form(
                ActionRow(
                    SaveAction("Save Rule"),
                    CancelAction(href="/library/rules"),
                    cls="gap-2",
                ),

                # ── IDENTITY ─────────────────────────────────────────────
                _section_header("Identity"),
                _text("Reference", "reference", _v("reference"), "e.g. 9.8.2.1.(1)", required=True),
                _select("Rule Type", "rule_type", _RULE_TYPE_OPTIONS, _v("rule_type", "numeric_range"), required=True),
                _text("Mechanism", "mechanism", _v("mechanism"), "e.g. dimensional, existence, fire-rating"),
                _text("Ruleset ID", "ruleset_id", _v("ruleset_id"), "e.g. OBC-Part9, custom"),
                _text("Rule Category", "rule_category", _v("rule_category"), "e.g. egress, structural, accessibility"),

                # ── IFC TARGET ───────────────────────────────────────────
                _section_header("IFC Target"),
                SelectField(
                    FieldSpec(label="Target IFC Class", field_id="target_ifc_class", name="target_ifc_class", required=True),
                    ifc_opts,
                ),
                _text("Property Set", "property_set", _v("property_set"), "e.g. Pset_StairFlightCommon"),
                _text("Property Name", "property_name", _v("property_name"), "e.g. TreadDepth"),
                _text("Fallback Property", "fallback_property", _v("fallback_property"), "alternative if primary missing"),

                # ── RULE LOGIC ───────────────────────────────────────────
                _section_header("Rule Logic"),
                _select("Operator", "operator", _OPERATOR_OPTIONS, _v("operator")),
                _text("Check Value", "check_value", _v("check_value"), "numeric or null"),
                _text("Value Min (between)", "value_min", _v("value_min"), "lower bound"),
                _text("Value Max (between)", "value_max", _v("value_max"), "upper bound"),
                _select("Unit", "unit", _UNIT_OPTIONS, _v("unit")),

                # ── CLASSIFICATION ───────────────────────────────────────
                _section_header("Classification"),
                _select("Severity", "severity", _SEVERITY_OPTIONS, _v("severity", "mandatory")),
                _select("Keyword", "keyword", _KEYWORD_OPTIONS, _v("keyword")),
                _select("Compliance Type", "compliance_type", _COMPLIANCE_OPTIONS, _v("compliance_type")),

                # ── CONTENT ──────────────────────────────────────────────
                _section_header("Content"),
                _textarea("Description", "description", _v("description"), rows=4),
                _textarea("Source Text", "source_text", _v("source_text"), rows=3),

                # ── META ─────────────────────────────────────────────────
                _section_header("Meta"),
                _text("Confidence (0.0–1.0)", "confidence", _v("confidence"), "0.0 – 1.0"),
                _checkbox("Needs Review", "needs_review", bool(rule.get("needs_review"))),

                # Rule JSON — read-only reference
                Div(
                    FormLabel("Rule JSON (read-only reference)", cls="text-sm font-medium"),
                    Pre(
                        rule_json_str or "— fill in fields above and save —",
                        cls="text-xs bg-muted p-3 rounded border overflow-x-auto max-h-64 mt-1 text-muted-foreground",
                    ),
                    cls="space-y-1 mt-2",
                ) if rule_json_str else "",

                method="post",
                action=action,
                cls="space-y-3",
            )
        ),
    )
