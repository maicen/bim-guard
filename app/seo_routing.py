"""Pure helpers for crawler- and agent-facing routing decisions.

Kept free of FastAPI/Starlette so the rules are unit-testable without a built
``frontend/dist``; ``app/main.py`` (``serve_spa`` and the discovery middleware)
applies them.
"""

from __future__ import annotations

# Path-routed SPA entry points (everything else in the app is hash-routed under "/").
# Source of truth: frontend/src/main.ts (CONSENT_PATH) and App.svelte ("/viewer").
SPA_PATHS = frozenset({"", "viewer", "oauth/consent"})

# API paths that should stay crawlable/fetchable by agents. Everything else under
# /api/ is authenticated data and is kept out of search indexes via X-Robots-Tag.
# WHY a header and not only robots.txt: a robots.txt Disallow stops crawlers from
# ever seeing a noindex signal, so blocked URLs can still be indexed from links.
API_INDEXABLE_PATHS = frozenset({"/api/openapi.json", "/api/docs", "/api/redoc"})

# Content types for extensionless or ambiguous well-known files.
WELL_KNOWN_MEDIA_TYPES = {
    ".well-known/api-catalog": 'application/linkset+json; profile="https://www.rfc-editor.org/info/rfc9727"',
    ".well-known/security.txt": "text/plain; charset=utf-8",
}
SUFFIX_MEDIA_TYPES = {
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


def is_spa_path(full_path: str) -> bool:
    """Return True if *full_path* (no leading slash) is a real SPA entry point."""
    return full_path.strip("/") in SPA_PATHS


def x_robots_for_api(path: str) -> str | None:
    """Return the X-Robots-Tag value for *path*, or None if it should be indexable."""
    if path.startswith("/api/") and path not in API_INDEXABLE_PATHS:
        return "noindex, nofollow"
    return None


def prefers_markdown(accept: str) -> bool:
    """Return True if an ``Accept`` header ranks ``text/markdown`` above ``text/html``.

    A browser sending ``text/html,...,*/*;q=0.8`` therefore never gets markdown; an
    agent sending ``text/markdown`` (or ``text/markdown, text/html;q=0.5``) does.
    """
    quality: dict[str, float] = {}
    for part in accept.split(","):
        media, _, params = part.strip().partition(";")
        media = media.strip().lower()
        if not media:
            continue
        q = 1.0
        for param in params.split(";"):
            key, _, value = param.strip().partition("=")
            if key.strip() == "q":
                try:
                    q = float(value)
                except ValueError:
                    q = 0.0
        quality[media] = q
    md = quality.get("text/markdown", 0.0)
    return md > 0 and md > quality.get("text/html", 0.0)


def canonical_redirect(full_path: str) -> str | None:
    """Return the canonical clean path to 301 to, or None when *full_path* is canonical.

    ``/features.html`` and ``/features/`` are duplicates of ``/features``; the
    canonical tag only mitigates that, a redirect removes it.
    """
    if full_path.endswith(".html") and full_path != "index.html":
        return "/" + full_path[: -len(".html")]
    if full_path.endswith("/") and full_path.strip("/"):
        return "/" + full_path.rstrip("/")
    return None
