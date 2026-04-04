from pathlib import Path

from fasthtml.common import (
    A,
    Div,
    FileResponse,
    Option,
    RedirectResponse,
    Tbody,
    Td,
    Th,
    Thead,
    Title,
    Tr,
    UploadFile,
)
from fastlite import database
from monsterui.all import (
    Alert,
    AlertT,
    Button,
    ButtonT,
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

from app.components.layout import DashboardLayout
from app.components.ui import CreateAction, DeleteAction, EditAction, ViewAction
from app.utils import md5_hex, now_iso_utc, safe_upload_name, store_upload_bytes


DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "bimguard.sqlite"

IFC_UPLOAD_DIR = DB_DIR / "uploads" / "ifc"
IFC_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_db = database(str(DB_PATH))
_projects = _db["projects"]
_projects.create(
    {
        "id": int,
        "name": str,
        "description": str,
        "status": str,
        "ifc_file_path": str,
        "ifc_md5_hash": str,
        "created_at": str,
        "updated_at": str,
    },
    pk="id",
    if_not_exists=True,
)
# Add ifc_file_path to existing tables that predate this column
if "ifc_file_path" not in _projects.columns_dict:
    _projects.add_column("ifc_file_path", str)
if "ifc_md5_hash" not in _projects.columns_dict:
    _projects.add_column("ifc_md5_hash", str)


def _project_form(
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
                Button("Save Project", cls=ButtonT.primary),
                A(Button("Cancel", cls=ButtonT.secondary), href="/projects"),
                cls="gap-2",
            ),
            method="post",
            action=action,
            enctype="multipart/form-data" if include_ifc else None,
            cls="space-y-4",
        ),
        header=Div(H2(title), Subtitle("Manage your BIM compliance projects.")),
    )


def _projects_table_rows():
    rows = sorted(list(_projects.rows), key=lambda r: r["id"], reverse=True)
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


def _projects_page(message: str | None = None):
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
                    Tbody(*_projects_table_rows()),
                    cls=TableT.hover,
                ),
                header=H3("Project Registry"),
            ),
            cls="space-y-4",
        )
    )


def setup_routes(rt):
    @rt("/projects")
    def projects_list():
        return Title("Projects - BIM Guard"), _projects_page()

    @rt("/projects/new")
    def projects_new():
        return Title("New Project - BIM Guard"), DashboardLayout(
            Container(
                _project_form("Create Project", "/projects/create", include_ifc=True)
            )
        )

    @rt("/projects/create", methods=["POST"])
    async def projects_create(
        name: str,
        description: str = "",
        status: str = "Draft",
        ifc_file: UploadFile = None,
    ):
        ifc_path = ""
        ifc_md5_hash = ""
        if ifc_file and ifc_file.filename:
            filename = safe_upload_name(ifc_file.filename)
            if filename.lower().endswith(".ifc"):
                content = await ifc_file.read()
                if content:
                    ifc_md5_hash = md5_hex(content)
                    stored_path = store_upload_bytes(filename, content, IFC_UPLOAD_DIR)
                    ifc_path = str(stored_path)
        now = now_iso_utc()
        _projects.insert(
            {
                "name": name.strip(),
                "description": description.strip(),
                "status": status,
                "ifc_file_path": ifc_path,
                "ifc_md5_hash": ifc_md5_hash,
                "created_at": now,
                "updated_at": now,
            }
        )
        return RedirectResponse("/projects", status_code=303)

    @rt("/projects/{project_id}/edit")
    def projects_edit(project_id: int):
        project = _projects.get(project_id)
        return Title("Edit Project - BIM Guard"), DashboardLayout(
            Container(
                _project_form("Edit Project", f"/projects/{project_id}/update", project)
            )
        )

    @rt("/projects/{project_id}/update", methods=["POST"])
    def projects_update(
        project_id: int, name: str, description: str = "", status: str = "Draft"
    ):
        _projects.update(
            updates={
                "name": name.strip(),
                "description": description.strip(),
                "status": status,
                "updated_at": now_iso_utc(),
            },
            pk_values=project_id,
        )
        return RedirectResponse("/projects", status_code=303)

    @rt("/projects/{project_id}/delete", methods=["POST"])
    def projects_delete(project_id: int):
        _projects.delete(project_id)
        return RedirectResponse("/projects", status_code=303)

    @rt("/projects/{project_id}/ifc")
    def project_ifc_file(project_id: int):
        project = _projects.get(project_id)
        if project is None:
            return RedirectResponse("/projects", status_code=303)

        ifc_file_path = project.get("ifc_file_path") or ""
        if not ifc_file_path:
            return RedirectResponse("/projects", status_code=303)

        file_path = Path(ifc_file_path)
        if not file_path.exists() or not file_path.is_file():
            return RedirectResponse("/projects", status_code=303)

        return FileResponse(
            file_path, media_type="application/octet-stream", filename=file_path.name
        )
