from datetime import datetime
from pathlib import Path

from fasthtml.common import (
    A,
    Div,
    Option,
    RedirectResponse,
    Tbody,
    Td,
    Th,
    Thead,
    Title,
    Tr,
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
)

from app.components.layout import DashboardLayout


DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "bimguard.sqlite"

_db = database(str(DB_PATH))
_projects = _db["projects"]
_projects.create(
    {
        "id": int,
        "name": str,
        "description": str,
        "status": str,
        "created_at": str,
        "updated_at": str,
    },
    pk="id",
    if_not_exists=True,
)


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _project_form(title: str, action: str, project: dict | None = None):
    project = project or {}
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
            DivLAligned(
                Button("Save Project", cls=ButtonT.primary),
                A(Button("Cancel", cls=ButtonT.ghost), href="/projects"),
                cls="gap-2",
            ),
            method="post",
            action=action,
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
                    colspan="6",
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
                Td(row.get("created_at", "-")),
                Td(row.get("updated_at", "-")),
                Td(
                    DivLAligned(
                        A(
                            Button("Edit", cls=ButtonT.ghost),
                            href=f"/projects/{row['id']}/edit",
                        ),
                        Form(
                            Button("Delete", cls=ButtonT.destructive),
                            method="post",
                            action=f"/projects/{row['id']}/delete",
                        ),
                        cls="gap-2",
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
                A(Button("New Project", cls=ButtonT.primary), href="/projects/new"),
            ),
            *msg_block,
            Card(
                Table(
                    Thead(
                        Tr(
                            Th("ID"),
                            Th("Name"),
                            Th("Status"),
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
            Container(_project_form("Create Project", "/projects/create"))
        )

    @rt("/projects/create", methods=["POST"])
    def projects_create(name: str, description: str = "", status: str = "Draft"):
        now = _now_iso()
        _projects.insert(
            {
                "name": name.strip(),
                "description": description.strip(),
                "status": status,
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
                "updated_at": _now_iso(),
            },
            pk_values=project_id,
        )
        return RedirectResponse("/projects", status_code=303)

    @rt("/projects/{project_id}/delete", methods=["POST"])
    def projects_delete(project_id: int):
        _projects.delete(project_id)
        return RedirectResponse("/projects", status_code=303)
