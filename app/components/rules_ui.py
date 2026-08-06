from fasthtml.common import (
    Button,
    Details,
    Div,
    Option,
    P,
    Script,
    Span,
    Summary,
    Tbody,
    Td,
    Th,
    Thead,
    Tr,
)
from monsterui.all import Form, Input, Select, Table

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
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
    TableSpec,
    TextAreaField,
    TextInputField,
    build_table_rows,
)
from app.components.ui import (
    Table as UITable,
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
    SelectOptionSpec(label="Building Code", value="CODE"),
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
    "CODE": "bg-blue-100 text-blue-800",
    "GC-001": "bg-amber-100 text-amber-800",
    "CC-001": "bg-rose-100 text-rose-800",
    "MC-001": "bg-green-100 text-green-800",
    "IFC": "bg-purple-100 text-purple-800",
}

_FOLDER_SCOPE_OPTIONS = [
    ("", "Any"),
    ("CODE", "Building Code"),
    ("GC-001", "GC-001"),
    ("CC-001", "CC-001"),
    ("MC-001", "MC-001"),
    ("IFC", "IFC"),
]


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
            "this.closest('form').querySelectorAll('tbody tr')"
            ".forEach(function(row){"
            "if(row.style.display==='none'){return;}"
            "var cb=row.querySelector('input[name=rule_ids]');"
            "if(cb){cb.checked=this.checked;}"
            "}, this)"
        ),
    )


def _needs_review_badge(row: dict):
    if not row.get("needs_review"):
        return Span("-", cls="text-xs text-muted-foreground")
    confidence = row.get("confidence")
    label = "Review" + (f" ({confidence})" if confidence not in (None, "") else "")
    return Span(
        label,
        cls="text-xs font-medium px-2 py-0.5 rounded bg-amber-100 text-amber-800",
    )


def _short_description(text: str, limit: int = 100) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _rules_data_row(row: dict):
    reference = str(row.get("reference") or "")
    mechanism = str(row.get("mechanism") or "")
    rule_type = str(row.get("rule_type") or "")
    target_ifc_class = str(row.get("target_ifc_class") or "")
    rule_category = str(row.get("rule_category") or "")
    ruleset_id = str(row.get("ruleset_id") or "")
    needs_review = "yes" if row.get("needs_review") else "no"
    updated_at = str(row.get("updated_at") or "")
    description = str(row.get("description") or "")

    return TableRow(
        TableCell(
            Input(type="checkbox", name="rule_ids", value=str(row["id"]), cls="h-4 w-4"),
            **{"data-col": "select"},
        ),
        TableCell(reference or "-", **{"data-col": "reference"}),
        TableCell(ruleset_id or "-", **{"data-col": "folder"}),
        TableCell(_mechanism_badge(mechanism), **{"data-col": "mechanism"}),
        TableCell(rule_type or "-", **{"data-col": "type"}),
        TableCell(target_ifc_class or "-", **{"data-col": "target_class"}),
        TableCell(
            rule_category or "-",
            cls="text-xs text-muted-foreground",
            **{"data-col": "category"},
        ),
        TableCell(_needs_review_badge(row), **{"data-col": "review"}),
        TableCell(
            updated_at or "-", cls="text-sm text-muted-foreground", **{"data-col": "updated"}
        ),
        TableCell(
            _short_description(description),
            cls="text-sm text-muted-foreground",
            **{"data-col": "description"},
        ),
        TableCell(
            TableActionsMenu(
                edit_href=f"/library/rules/{row['id']}/edit",
                delete_action=f"/library/rules/{row['id']}/delete",
                view_href=f"/library/rules/{row['id']}",
            ),
            **{"data-col": "actions"},
        ),
        **{
            "data-row": "rule",
            "data-reference": reference.lower(),
            "data-mechanism": mechanism.upper(),
            "data-type": rule_type.lower(),
            "data-target": target_ifc_class.lower(),
            "data-category": rule_category.lower(),
            "data-folder": ruleset_id.lower(),
            "data-review": needs_review,
            "data-updated": updated_at.lower(),
            "data-description": description.lower(),
        },
    )


def _rules_table_header_cell(label: str, sort_key: str, data_col: str):
    return TableHead(
        Button(
            label,
            type="button",
            cls="text-xs font-medium text-muted-foreground hover:text-foreground",
            **{"data-sort": sort_key},
        ),
        **{"data-col": data_col},
    )


def _rules_data_table(rows: list[dict], empty_message: str):
    if rows:
        body_rows = [_rules_data_row(row) for row in rows]
    else:
        body_rows = [
            TableRow(
                TableCell(
                    empty_message,
                    colspan="11",
                    cls="text-center text-muted-foreground",
                )
            )
        ]

    folder_values = sorted(
        {
            str(row.get("ruleset_id") or "").strip()
            for row in rows
            if str(row.get("ruleset_id") or "").strip()
        }
    )

    return Div(
        Div(
            Div(
                Input(
                    type="search",
                    placeholder="Search reference, folder, type, class, category, description...",
                    cls="h-8 w-full md:w-[340px]",
                    **{"data-table-search": "rules"},
                ),
                Select(
                    Option("All folders", value=""),
                    *[Option(folder, value=folder) for folder in folder_values],
                    cls="h-8 w-[220px]",
                    **{"data-filter-folder": "true"},
                ),
                Select(
                    Option("All mechanisms", value=""),
                    Option("Building Code", value="CODE"),
                    Option("GC-001", value="GC-001"),
                    Option("CC-001", value="CC-001"),
                    Option("MC-001", value="MC-001"),
                    Option("IFC", value="IFC"),
                    cls="h-8 w-[180px]",
                    **{"data-filter-mechanism": "true"},
                ),
                Select(
                    Option("10 rows", value="10"),
                    Option("25 rows", value="25", selected=True),
                    Option("50 rows", value="50"),
                    cls="h-8 w-[120px]",
                    **{"data-page-size": "true"},
                ),
                cls="flex flex-wrap items-center gap-2",
            ),
            Details(
                Summary("Columns", cls="cursor-pointer text-sm text-muted-foreground"),
                Div(
                    Div(
                        Input(
                            type="checkbox",
                            checked=True,
                            cls="h-4 w-4",
                            **{"data-column-toggle": "folder"},
                        ),
                        Span("Folder", cls="text-xs"),
                        cls="flex items-center gap-2",
                    ),
                    Div(
                        Input(
                            type="checkbox",
                            checked=True,
                            cls="h-4 w-4",
                            **{"data-column-toggle": "reference"},
                        ),
                        Span("Reference", cls="text-xs"),
                        cls="flex items-center gap-2",
                    ),
                    Div(
                        Input(
                            type="checkbox",
                            checked=True,
                            cls="h-4 w-4",
                            **{"data-column-toggle": "mechanism"},
                        ),
                        Span("Mechanism", cls="text-xs"),
                        cls="flex items-center gap-2",
                    ),
                    Div(
                        Input(
                            type="checkbox",
                            checked=True,
                            cls="h-4 w-4",
                            **{"data-column-toggle": "type"},
                        ),
                        Span("Type", cls="text-xs"),
                        cls="flex items-center gap-2",
                    ),
                    Div(
                        Input(
                            type="checkbox",
                            checked=True,
                            cls="h-4 w-4",
                            **{"data-column-toggle": "target_class"},
                        ),
                        Span("Target Class", cls="text-xs"),
                        cls="flex items-center gap-2",
                    ),
                    Div(
                        Input(
                            type="checkbox",
                            checked=True,
                            cls="h-4 w-4",
                            **{"data-column-toggle": "category"},
                        ),
                        Span("Category", cls="text-xs"),
                        cls="flex items-center gap-2",
                    ),
                    Div(
                        Input(
                            type="checkbox",
                            checked=True,
                            cls="h-4 w-4",
                            **{"data-column-toggle": "review"},
                        ),
                        Span("Review", cls="text-xs"),
                        cls="flex items-center gap-2",
                    ),
                    Div(
                        Input(
                            type="checkbox",
                            checked=True,
                            cls="h-4 w-4",
                            **{"data-column-toggle": "updated"},
                        ),
                        Span("Updated", cls="text-xs"),
                        cls="flex items-center gap-2",
                    ),
                    Div(
                        Input(
                            type="checkbox",
                            checked=True,
                            cls="h-4 w-4",
                            **{"data-column-toggle": "description"},
                        ),
                        Span("Description", cls="text-xs"),
                        cls="flex items-center gap-2",
                    ),
                    cls="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2",
                ),
                cls="rounded-md border px-3 py-2",
            ),
            cls="flex flex-col gap-3 md:flex-row md:items-start md:justify-between",
        ),
        Div(
            UITable(
                TableHeader(
                    TableRow(
                        TableHead(_select_all_checkbox(), **{"data-col": "select"}),
                        _rules_table_header_cell("Reference", "reference", "reference"),
                        _rules_table_header_cell("Folder", "folder", "folder"),
                        _rules_table_header_cell("Mechanism", "mechanism", "mechanism"),
                        _rules_table_header_cell("Type", "type", "type"),
                        _rules_table_header_cell("Target Class", "target", "target_class"),
                        _rules_table_header_cell("Category", "category", "category"),
                        _rules_table_header_cell("Review", "review", "review"),
                        _rules_table_header_cell("Updated", "updated", "updated"),
                        _rules_table_header_cell("Description", "description", "description"),
                        TableHead("Actions", **{"data-col": "actions"}),
                    )
                ),
                TableBody(*body_rows),
                cls="min-w-[1200px]",
                **{"data-rules-table": "true"},
            ),
            cls="w-full min-w-0 max-h-[65vh] overflow-auto border rounded-md",
        ),
        Div(
            P(
                "No matching rules found for the current filters.",
                cls="text-sm text-muted-foreground",
                style="display:none",
                **{"data-no-matches": "true"},
            ),
            Div(
                Span(
                    "0 of 0 row(s)",
                    cls="text-xs text-muted-foreground",
                    **{"data-row-count": "true"},
                ),
                Div(
                    Button(
                        "Previous",
                        type="button",
                        cls="h-8 px-3 border rounded-md",
                        **{"data-page-prev": "true"},
                    ),
                    Span(
                        "Page 1 of 1",
                        cls="text-xs text-muted-foreground",
                        **{"data-page-label": "true"},
                    ),
                    Button(
                        "Next",
                        type="button",
                        cls="h-8 px-3 border rounded-md",
                        **{"data-page-next": "true"},
                    ),
                    cls="flex items-center gap-2",
                ),
                cls="flex flex-wrap items-center justify-between gap-3",
            ),
            cls="space-y-2",
        ),
        Script(
            "(function(){"
            "if(window.__rulesDataTableBooted){return;}"
            "window.__rulesDataTableBooted=true;"
            "function initTable(root){"
            "if(!root||root.dataset.tableBound==='1'){return;}"
            "root.dataset.tableBound='1';"
            "var rows=Array.from(root.querySelectorAll('tbody tr[data-row=rule]'));"
            "if(!rows.length){return;}"
            "var search=root.querySelector('[data-table-search=rules]');"
            "var folder=root.querySelector('[data-filter-folder=true]');"
            "var mech=root.querySelector('[data-filter-mechanism=true]');"
            "var size=root.querySelector('[data-page-size=true]');"
            "var prev=root.querySelector('[data-page-prev=true]');"
            "var next=root.querySelector('[data-page-next=true]');"
            "var pageLabel=root.querySelector('[data-page-label=true]');"
            "var rowCount=root.querySelector('[data-row-count=true]');"
            "var noMatch=root.querySelector('[data-no-matches=true]');"
            "var sortButtons=Array.from(root.querySelectorAll('[data-sort]'));"
            "var toggles=Array.from(root.querySelectorAll('[data-column-toggle]'));"
            "var state={query:'',folder:'',mechanism:'',sortKey:'updated',sortDir:'desc',page:1,pageSize:25};"
            "function bySort(a,b){"
            "var key=state.sortKey;"
            "var av=(a.dataset[key]||'').toString();"
            "var bv=(b.dataset[key]||'').toString();"
            "if(key==='review'){av=av==='yes'?'1':'0';bv=bv==='yes'?'1':'0';}"
            "var cmp=av.localeCompare(bv,undefined,{numeric:true,sensitivity:'base'});"
            "return state.sortDir==='asc'?cmp:-cmp;"
            "}"
            "function matches(row){"
            "var query=state.query;"
            "var folderOk=!state.folder||row.dataset.folder===state.folder;"
            "var mechOk=!state.mechanism||row.dataset.mechanism===state.mechanism;"
            "if(!folderOk){return false;}"
            "if(!mechOk){return false;}"
            "if(!query){return true;}"
            "var haystack=[row.dataset.reference,row.dataset.folder,row.dataset.type,row.dataset.target,row.dataset.category,row.dataset.description,row.dataset.updated].join(' ');"
            "return haystack.indexOf(query)!==-1;"
            "}"
            "function render(){"
            "var filtered=rows.filter(matches).sort(bySort);"
            "var total=filtered.length;"
            "var totalPages=Math.max(1,Math.ceil(total/state.pageSize));"
            "if(state.page>totalPages){state.page=totalPages;}"
            "if(state.page<1){state.page=1;}"
            "var start=(state.page-1)*state.pageSize;"
            "var end=start+state.pageSize;"
            "rows.forEach(function(row){row.style.display='none';});"
            "filtered.slice(start,end).forEach(function(row){row.style.display='';});"
            "if(noMatch){noMatch.style.display=total?'none':'';}"
            "if(rowCount){rowCount.textContent=(total?((start+1)+'-'+Math.min(end,total)):'0')+' of '+total+' row(s)';}"
            "if(pageLabel){pageLabel.textContent='Page '+state.page+' of '+totalPages;}"
            "if(prev){prev.disabled=state.page<=1;prev.classList.toggle('opacity-50',prev.disabled);}"
            "if(next){next.disabled=state.page>=totalPages;next.classList.toggle('opacity-50',next.disabled);}"
            "}"
            "if(search){search.addEventListener('input',function(e){state.query=(e.target.value||'').trim().toLowerCase();state.page=1;render();});}"
            "if(folder){folder.addEventListener('change',function(e){state.folder=(e.target.value||'').trim().toLowerCase();state.page=1;render();});}"
            "if(mech){mech.addEventListener('change',function(e){state.mechanism=(e.target.value||'').toUpperCase();state.page=1;render();});}"
            "if(size){size.addEventListener('change',function(e){var v=parseInt(e.target.value||'25',10);state.pageSize=isNaN(v)?25:v;state.page=1;render();});}"
            "if(prev){prev.addEventListener('click',function(){state.page-=1;render();});}"
            "if(next){next.addEventListener('click',function(){state.page+=1;render();});}"
            "sortButtons.forEach(function(btn){btn.addEventListener('click',function(){var key=btn.getAttribute('data-sort');if(!key){return;}if(state.sortKey===key){state.sortDir=state.sortDir==='asc'?'desc':'asc';}else{state.sortKey=key;state.sortDir='asc';}state.page=1;render();});});"
            "toggles.forEach(function(toggle){toggle.addEventListener('change',function(){var col=toggle.getAttribute('data-column-toggle');if(!col){return;}var visible=!!toggle.checked;root.querySelectorAll('[data-col='+col+']').forEach(function(cell){cell.style.display=visible?'':'none';});});});"
            "render();"
            "}"
            "function initAll(scope){"
            "(scope||document).querySelectorAll('[data-rules-data-table=true]').forEach(initTable);"
            "}"
            "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',function(){initAll(document);});}else{initAll(document);}"
            "if(document.body){document.body.addEventListener('htmx:afterSwap',function(evt){initAll(evt&&evt.target?evt.target:document);});}"
            "})();"
        ),
        cls="space-y-3",
        **{"data-rules-data-table": "true"},
    )


def rules_table_rows(rows: list[dict], empty_message: str = "No rules available yet."):
    def _build_row(row: dict):
        return Tr(
            Td(Input(type="checkbox", name="rule_ids", value=str(row["id"]), cls="h-4 w-4")),
            Td(row.get("reference", "-")),
            Td(_mechanism_badge(row.get("mechanism", ""))),
            Td(row.get("rule_type", "-")),
            Td(row.get("target_ifc_class", "-")),
            Td(row.get("rule_category", "-"), cls="text-xs text-muted-foreground"),
            Td(_needs_review_badge(row)),
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
        TableSpec(empty_message=empty_message, empty_colspan=10),
    )


def rules_folders_panel(
    folders: list[dict],
    message: str | None = None,
    level: str = "success",
    as_card: bool = False,
):
    """Render rule folders with inline rename/delete and expandable contents.

    Each folder dict should carry a "rules" key (list of rule rows) for the
    expanded table; it falls back to an empty list when omitted.
    """
    alert = MessageAlert(AlertSpec(message=message, level=level))

    create_form = Form(
        Input(
            name="ruleset_id",
            placeholder="Folder ID (ruleset_id), e.g. BUILDING-CODE-PART9",
            required=True,
            cls="text-xs h-8 w-full md:w-[280px]",
        ),
        Input(
            name="display_name",
            placeholder="Display name",
            cls="text-xs h-8 w-full md:w-[220px]",
        ),
        Input(
            name="description",
            placeholder="Description",
            cls="text-xs h-8 w-full md:w-[280px]",
        ),
        Select(
            *[Option(label, value=value) for value, label in _FOLDER_SCOPE_OPTIONS],
            name="mechanism_scope",
            cls="text-xs h-8 w-full md:w-[160px]",
        ),
        Button(
            "Create Folder",
            type="submit",
            cls="text-xs px-3 py-1 rounded bg-primary text-primary-foreground hover:opacity-90",
        ),
        hx_post="/api/rules/folders/create",
        hx_target="#rule-folders-panel",
        hx_swap="outerHTML",
        cls="flex flex-wrap items-center gap-2",
    )

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
            display_name = (f.get("display_name") or ruleset_id).strip() or ruleset_id
            description = (f.get("description") or "").strip()
            mechanism_scope = (f.get("mechanism_scope") or "").strip().upper()
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
            metadata_form = Form(
                Input(type="hidden", name="ruleset_id", value=ruleset_id),
                Input(
                    name="display_name",
                    value=display_name,
                    placeholder="Display name",
                    cls="text-xs h-8 w-full md:w-[220px]",
                ),
                Input(
                    name="description",
                    value=description,
                    placeholder="Description",
                    cls="text-xs h-8 w-full md:w-[300px]",
                ),
                Select(
                    *[
                        Option(label, value=value, selected=value == mechanism_scope)
                        for value, label in _FOLDER_SCOPE_OPTIONS
                    ],
                    name="mechanism_scope",
                    cls="text-xs h-8 w-full md:w-[160px]",
                ),
                Button(
                    "Save Metadata",
                    type="submit",
                    cls=(
                        "text-xs px-2 py-1 rounded bg-secondary "
                        "text-secondary-foreground hover:opacity-90"
                    ),
                ),
                hx_post="/api/rules/folders/update",
                hx_target="#rule-folders-panel",
                hx_swap="outerHTML",
                cls="flex flex-wrap items-center gap-2",
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
                    f'Delete folder "{ruleset_id}" and all {f["count"]} rule(s) '
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
                                    Th("Review"),
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
                        "return confirm('Delete the selected rule(s)? This cannot be undone.')"
                    ),
                )
                if folder_rules
                else P("No rules found in this folder.", cls="text-xs text-muted-foreground")
            )
            items.append(
                Details(
                    Summary(
                        Span(display_name, cls="text-sm font-medium"),
                        Span(ruleset_id, cls="text-xs text-muted-foreground ml-2"),
                        Span(
                            f"{f['count']} rule(s)",
                            cls="text-xs text-muted-foreground ml-2",
                        ),
                        cls="cursor-pointer select-none py-2 list-none",
                    ),
                    P(description, cls="text-xs text-muted-foreground mb-2")
                    if description
                    else None,
                    Div(
                        metadata_form,
                        rename_form,
                        delete_folder_form,
                        cls="flex flex-wrap items-center gap-3 mb-3",
                    ),
                    rule_table,
                    cls="py-1 border-b last:border-0",
                )
            )
        body = Div(*items)

    panel = Div(*alert, create_form, body, id="rule-folders-panel", cls="space-y-2")
    if not as_card:
        return panel

    return Div(
        Card(
            CardHeader(CardTitle("Rule Folders")),
            CardContent(panel),
            cls="w-full",
        ),
        cls="space-y-2",
    )


def rules_panel(
    rows: list[dict],
    folders: list[dict],
    message: str | None = None,
    folders_message: str | None = None,
    level: str = "success",
    needs_review_only: bool = False,
    needs_review_count: int = 0,
):
    alert = MessageAlert(AlertSpec(message=message, level=level))

    if needs_review_only:
        filter_toggle = LinkButton(
            "All Rules",
            href="/library/rules",
            variant="secondary",
            cls="text-sm",
        )
        empty_message = "Nothing flagged for review right now."
    else:
        label = f"Needs Review ({needs_review_count})" if needs_review_count else "Needs Review"
        filter_toggle = LinkButton(
            label,
            href="/library/rules?needs_review=1",
            variant="secondary",
            cls="text-sm",
        )
        empty_message = "No rules available yet."

    return Div(
        *alert,
        Card(
            CardHeader(
                Div(
                    CardTitle("Rule Library" + (" — Needs Review" if needs_review_only else "")),
                    Div(
                        filter_toggle,
                        LinkButton(
                            "Import JSON Ruleset",
                            href="/library/rules/import-json",
                            variant="secondary",
                            cls="text-sm",
                        ),
                        cls="flex items-center gap-2",
                    ),
                    cls="flex items-center justify-between gap-2 flex-wrap",
                )
            ),
            CardContent(
                Div(
                    Div(
                        Span("Rule Folders", cls="text-sm font-semibold"),
                        P(
                            "Folders map to ruleset_id and can be renamed or deleted in-place.",
                            cls="text-xs text-muted-foreground",
                        ),
                        cls="space-y-1",
                    ),
                    rules_folders_panel(
                        folders,
                        message=folders_message,
                        level=level,
                    ),
                    Form(
                        Div(
                            SubmitButton(
                                "Delete Selected",
                                variant="secondary",
                                cls="text-sm text-destructive",
                            ),
                            cls="flex justify-end mb-2",
                        ),
                        _rules_data_table(rows, empty_message),
                        method="post",
                        action="/api/rules/bulk-delete",
                        onsubmit=(
                            "return confirm('Delete the selected rule(s)? This cannot be undone.')"
                        ),
                        cls="w-full min-w-0 pt-0",
                    ),
                    cls="space-y-4",
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
                        placeholder="e.g. BUILDING-CODE-PART9",
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
                Span(
                    "Relative bounds (optional) — when the min/max is itself another "
                    "property of the element (e.g. tread depth must be between its own "
                    "Run and Run + 25mm), set the property name here instead of a fixed "
                    "Value Min/Max above. Leave blank to use the fixed values above.",
                    cls="text-xs text-muted-foreground block",
                ),
                Div(
                    TextInputField(
                        FieldSpec(
                            label="Value Min Property",
                            field_id="value_min_property",
                            name="value_min_property",
                            value=rule.get("value_min_property", ""),
                            placeholder="e.g. Run",
                        )
                    ),
                    TextInputField(
                        FieldSpec(
                            label="Value Min Offset",
                            field_id="value_min_offset",
                            name="value_min_offset",
                            value=_decode_json_field(rule.get("value_min_offset")),
                            placeholder="added to Min Property",
                        ),
                        input_type="number",
                    ),
                    TextInputField(
                        FieldSpec(
                            label="Value Max Property",
                            field_id="value_max_property",
                            name="value_max_property",
                            value=rule.get("value_max_property", ""),
                            placeholder="e.g. Run",
                        )
                    ),
                    TextInputField(
                        FieldSpec(
                            label="Value Max Offset",
                            field_id="value_max_offset",
                            name="value_max_offset",
                            value=_decode_json_field(rule.get("value_max_offset")),
                            placeholder="added to Max Property",
                        ),
                        input_type="number",
                    ),
                    cls="grid grid-cols-4 gap-3",
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
