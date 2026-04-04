from pathlib import Path

from app.services.persistence import PersistenceService
from app.utils import (
    md5_hex,
    now_iso_utc,
    rows_desc_by_id,
    safe_upload_name,
    store_upload_bytes,
)


class ProjectsService:
    """Encapsulates projects persistence and IFC file operations."""

    def __init__(self):
        self._ifc_upload_dir = PersistenceService.uploads_dir("ifc")
        self._projects = PersistenceService.get_table(
            "projects",
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
            required_columns={"ifc_file_path": str, "ifc_md5_hash": str},
        )

    def list_projects(self):
        return rows_desc_by_id(self._projects)

    def total_projects(self) -> int:
        return len(self.list_projects())

    def get_project(self, project_id: int):
        return self._projects.get(project_id)

    async def prepare_ifc_upload(self, ifc_file) -> tuple[str, str]:
        if not ifc_file or not getattr(ifc_file, "filename", None):
            return "", ""

        filename = safe_upload_name(ifc_file.filename)
        if not filename.lower().endswith(".ifc"):
            return "", ""

        content = await ifc_file.read()
        if not content:
            return "", ""

        ifc_md5_hash = md5_hex(content)
        stored_path = store_upload_bytes(filename, content, self._ifc_upload_dir)
        return str(stored_path), ifc_md5_hash

    def create_project(
        self,
        name: str,
        description: str = "",
        status: str = "Draft",
        ifc_file_path: str = "",
        ifc_md5_hash: str = "",
    ):
        now = now_iso_utc()
        return self._projects.insert(
            {
                "name": name.strip(),
                "description": description.strip(),
                "status": status,
                "ifc_file_path": ifc_file_path,
                "ifc_md5_hash": ifc_md5_hash,
                "created_at": now,
                "updated_at": now,
            }
        )

    def update_project(
        self, project_id: int, name: str, description: str = "", status: str = "Draft"
    ):
        self._projects.update(
            updates={
                "name": name.strip(),
                "description": description.strip(),
                "status": status,
                "updated_at": now_iso_utc(),
            },
            pk_values=project_id,
        )

    def delete_project(self, project_id: int):
        self._projects.delete(project_id)

    def resolve_ifc_file(self, project_id: int) -> Path | None:
        project = self.get_project(project_id)
        if project is None:
            return None

        ifc_file_path = project.get("ifc_file_path") or ""
        if not ifc_file_path:
            return None

        file_path = Path(ifc_file_path)
        if not file_path.exists() or not file_path.is_file():
            return None

        return file_path
