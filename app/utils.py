from datetime import datetime, timezone
import hashlib
from pathlib import Path
import uuid


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
