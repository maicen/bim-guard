from datetime import datetime, timezone

from starlette.responses import RedirectResponse


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def redirect_see_other(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def rows_desc_by_id(table) -> list[dict]:
    return sorted(list(table.rows), key=lambda row: row["id"], reverse=True)


from app.services.cache import (  # noqa: E402
    cache_db_query,
    cache_stats,
    clear_cache,
    get_cache,
    invalidate_cache,
    local_cache,
)

__all__ = [
    "cache_db_query",
    "cache_stats",
    "clear_cache",
    "get_cache",
    "invalidate_cache",
    "local_cache",
    "now_iso_utc",
    "redirect_see_other",
    "rows_desc_by_id",
]
