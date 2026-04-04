from datetime import datetime, timezone
import hashlib
from pathlib import Path
import uuid

from fasthtml.common import RedirectResponse


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def md5_hex(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def safe_upload_name(filename: str | None) -> str:
    return Path(filename or "").name


def store_upload_bytes(filename: str, content: bytes, destination_dir: Path) -> Path:
    stored_name = f"{uuid.uuid4().hex}_{filename}"
    stored_path = destination_dir / stored_name
    stored_path.write_bytes(content)
    return stored_path


def redirect_see_other(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def rows_desc_by_id(table) -> list[dict]:
    return sorted(list(table.rows), key=lambda row: row["id"], reverse=True)


def find_row_by_field(table, field_name: str, value):
    for row in table.rows:
        if row.get(field_name) == value:
            return row
    return None
