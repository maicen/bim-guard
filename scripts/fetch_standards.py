"""Scrape a standards page into Markdown for the NotebookLM corpora.

Fetches content through Firecrawl and writes it into ``docs/scraped_standards/``
with a provenance header. Two modes:

* default -- the first argument is a URL, fetched via the ``scrape`` endpoint.
* ``--search`` -- the first argument is a query, run through the ``search``
  endpoint; the top web result's Markdown is saved.

The ``--seismic`` / ``--corrosion`` flag decides which NotebookLM workspace the
file belongs to; because ``compile_for_notebooklm.py`` routes purely on the
repository-relative path, the category keyword is baked into the saved filename
so the compiler picks it up without further wiring.

Usage::

    python scripts/fetch_standards.py https://example.com/iso-code iso_9223_tables --corrosion
    python scripts/fetch_standards.py https://example.com/en1998 en_1998_1_bracing --seismic
    python scripts/fetch_standards.py "MBIE B2/AS1 durability tables" mbie_b2 --corrosion --search

Exit codes: ``0`` success, ``1`` scrape/write failure, ``2`` usage or
configuration error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Where scraped Markdown lands. Kept in sync with the ``docs/scraped_standards``
#: routing rules in ``compile_for_notebooklm.py``.
OUTPUT_DIR = REPO_ROOT / "docs" / "scraped_standards"

SEISMIC = "seismic"
CORROSION = "corrosion"

#: Environment variable holding the Firecrawl API key (read from ``.env``).
API_KEY_VAR = "FIRECRAWL_API_KEY"

#: Rejects path separators, drive letters and traversal in the output name.
SAFE_STEM = re.compile(r"^[A-Za-z0-9._-]+$")

#: Default per-request scrape timeout, in seconds.
DEFAULT_TIMEOUT = 120

#: How many search hits to request. Only the best usable one is saved; the
#: spares let the script fall past a result that returns nothing scrapable.
SEARCH_LIMIT = 5


class FetchError(RuntimeError):
    """Raised when a scrape cannot be completed or its result is unusable."""


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


def load_api_key() -> str:
    """Return the Firecrawl API key, loading the project .env first."""
    try:
        from app.environment import load_env_file

        load_env_file()
    except Exception:  # pragma: no cover - fallback when app/ is unavailable
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=REPO_ROOT / ".env", override=False)
        except ImportError:
            pass

    key = (os.environ.get(API_KEY_VAR) or "").strip()
    if not key:
        raise FetchError(
            f"{API_KEY_VAR} is not set. Add it to {REPO_ROOT / '.env'} "
            f"as {API_KEY_VAR}=fc-... or export it in the environment."
        )
    return key


def build_client(api_key: str, timeout: int):
    """Instantiate the Firecrawl client, with a clear error if it is missing."""
    try:
        from firecrawl import Firecrawl
    except ImportError as exc:
        raise FetchError(
            "The firecrawl-py package is not installed. Run 'uv sync' "
            "(it is declared in pyproject.toml) or 'uv add firecrawl-py'."
        ) from exc

    try:
        return Firecrawl(api_key=api_key, timeout=float(timeout))
    except Exception as exc:
        raise FetchError(f"Could not initialise the Firecrawl client: {exc}") from exc


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate_url(url: str) -> str:
    """Return *url* if it is a well-formed http(s) URL, else raise."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise FetchError(f"Not a valid http(s) URL: {url!r}")
    return url


def resolve_output_path(name: str, category: str, force: bool) -> Path:
    """Map the requested output name onto a safe, correctly routed file path.

    The category keyword is prefixed onto the stem unless it is already
    present, so ``compile_for_notebooklm.py`` routes the file to the intended
    NotebookLM workspace.
    """
    stem = name[:-3] if name.lower().endswith(".md") else name
    if not stem or stem.startswith(".") or ".." in stem or not SAFE_STEM.match(stem):
        raise FetchError(
            f"Unsafe output name {name!r}. Use letters, digits, dots, dashes "
            "and underscores only, with no directory components."
        )

    if category not in stem.lower():
        stem = f"{category}_{stem}"

    path = OUTPUT_DIR / f"{stem}.md"
    if path.exists() and not force:
        raise FetchError(
            f"{path.relative_to(REPO_ROOT).as_posix()} already exists. Pass --force to overwrite."
        )
    return path


# --------------------------------------------------------------------------
# Scraping
# --------------------------------------------------------------------------


def _field(source: object, key: str) -> object:
    """Read *key* off a Firecrawl result that may be a model or a plain dict."""
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _metadata_dict(source: object) -> dict:
    """Return a result's ``metadata`` as a plain dict, whatever shape it has."""
    metadata = _field(source, "metadata")
    if isinstance(metadata, dict):
        return metadata
    if metadata is None:
        return {}
    return dict(getattr(metadata, "__dict__", {}) or {})


def _result_url(hit: object, metadata: dict) -> str:
    """Find a search hit's source URL across the shapes the SDK returns.

    A plain ``SearchResultWeb`` carries ``url``; a scraped ``Document`` reports
    it in metadata instead, where the key is ``source_url`` on the typed model
    but ``sourceURL`` when the payload passes through untyped.
    """
    candidates = [_field(hit, "url")]
    candidates += [metadata.get(key) for key in ("source_url", "sourceURL", "url", "og_url")]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def scrape_markdown(client, url: str, timeout: int) -> tuple[str, dict]:
    """Scrape *url* and return its Markdown body plus any result metadata."""
    try:
        document = client.scrape(
            url,
            formats=["markdown"],
            only_main_content=True,
            timeout=timeout * 1000,
        )
    except Exception as exc:
        raise FetchError(
            f"Firecrawl scrape of {url} failed: {type(exc).__name__}: {exc}"
        ) from exc

    if document is None:
        raise FetchError(f"Firecrawl returned no document for {url}.")

    markdown = _field(document, "markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise FetchError(
            f"Firecrawl returned no Markdown for {url}. The page may be empty, "
            "JavaScript-gated or blocked by the site."
        )

    return markdown, _metadata_dict(document)


def search_top_markdown(client, query: str, timeout: int) -> tuple[str, dict, str]:
    """Search for *query* and return the best web hit as (markdown, metadata, url).

    Results are requested with Markdown scraping enabled, so the top hit
    normally arrives already converted. A hit that comes back without a body is
    retried through the scrape endpoint, and only then skipped in favour of the
    next hit.
    """
    try:
        from firecrawl.v2.types import ScrapeOptions
    except ImportError as exc:  # pragma: no cover - SDK layout change
        raise FetchError(f"This firecrawl-py build has no search options type: {exc}") from exc

    try:
        results = client.search(
            query,
            sources=["web"],
            limit=SEARCH_LIMIT,
            scrape_options=ScrapeOptions(formats=["markdown"], only_main_content=True),
            timeout=timeout * 1000,
        )
    except Exception as exc:
        raise FetchError(
            f"Firecrawl search for {query!r} failed: {type(exc).__name__}: {exc}"
        ) from exc

    hits = _field(results, "web") or []
    if not hits:
        raise FetchError(f"Firecrawl search returned no web results for {query!r}.")

    failures: list[str] = []
    for rank, hit in enumerate(hits, start=1):
        metadata = _metadata_dict(hit)
        url = _result_url(hit, metadata)
        markdown = _field(hit, "markdown")

        if isinstance(markdown, str) and markdown.strip():
            if rank > 1:
                print(f"note: results 1-{rank - 1} had no usable body", file=sys.stderr)
            print(f"Using result {rank}: {url or '(no url)'}", file=sys.stderr)
            if not metadata.get("title"):
                metadata["title"] = _field(hit, "title") or ""
            return markdown, metadata, url

        if not url:
            failures.append(f"result {rank}: no URL and no body")
            continue

        try:
            markdown, metadata = scrape_markdown(client, url, timeout)
        except FetchError as exc:
            failures.append(f"result {rank} ({url}): {exc}")
            continue
        if rank > 1:
            print(f"note: results 1-{rank - 1} had no usable body", file=sys.stderr)
        print(f"Using result {rank}: {url}", file=sys.stderr)
        return markdown, metadata, url

    detail = "; ".join(failures) or "no result carried a body"
    raise FetchError(f"No search result for {query!r} yielded Markdown. Tried: {detail}")


def render_document(
    markdown: str, metadata: dict, url: str, category: str, query: str | None = None
) -> str:
    """Wrap the fetched Markdown in a provenance header for the corpora."""
    title = str(metadata.get("title") or "").strip() or urlparse(url).netloc or "Untitled"
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    endpoint = "search" if query else "scrape"
    header = [f"# {title}", ""]
    if query:
        header.append(f"- **Search query:** {query}")
    header += [
        f"- **Source URL:** {url or '(not reported)'}",
        f"- **Category:** {category}",
        f"- **Fetched:** {fetched} via Firecrawl {endpoint}",
    ]
    description = str(metadata.get("description") or "").strip()
    if description:
        header.append(f"- **Description:** {description}")
    header += ["", "---", "", markdown.strip(), ""]
    return "\n".join(header)


def write_atomically(path: Path, content: str) -> None:
    """Write *content* to *path* as UTF-8 via a temporary file in the same dir."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8", newline="\n")
        tmp.replace(path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise FetchError(f"Could not write {path}: {exc}") from exc


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line into url, output name, category and options."""
    parser = argparse.ArgumentParser(
        description="Fetch a standards page to Markdown in docs/scraped_standards/.",
        epilog=(
            "Examples: python scripts/fetch_standards.py https://example.com/iso "
            "iso_9223_tables --corrosion | python scripts/fetch_standards.py "
            '"MBIE B2/AS1 durability tables" mbie_b2 --corrosion --search'
        ),
    )
    parser.add_argument(
        "source",
        metavar="URL_OR_QUERY",
        help="http(s) URL to scrape, or -- with --search -- the search query",
    )
    parser.add_argument("output", help="output filename stem (no directory, .md optional)")
    category = parser.add_mutually_exclusive_group(required=True)
    category.add_argument(
        "--seismic",
        action="store_const",
        const=SEISMIC,
        dest="category",
        help="route the file into the Seismic NotebookLM corpus",
    )
    category.add_argument(
        "--corrosion",
        action="store_const",
        const=CORROSION,
        dest="category",
        help="route the file into the Corrosion NotebookLM corpus",
    )
    parser.add_argument(
        "--search",
        action="store_true",
        help="treat the first argument as a search query and save the top web result",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"scrape timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite the output file if it already exists",
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be a positive number of seconds")
    return args


def main(argv: list[str] | None = None) -> int:
    """Run the scrape and report the outcome; see module docstring for codes."""
    args = parse_args(argv)

    query = args.source.strip() if args.search else None
    try:
        if query is not None:
            if not query:
                raise FetchError("The search query is empty.")
            url = ""
        else:
            url = validate_url(args.source)
        path = resolve_output_path(args.output, args.category, args.force)
        api_key = load_api_key()
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        client = build_client(api_key, args.timeout)
        if query is not None:
            print(f"Searching for {query!r} ...", file=sys.stderr)
            markdown, metadata, url = search_top_markdown(client, query, args.timeout)
        else:
            print(f"Scraping {url} ...", file=sys.stderr)
            markdown, metadata = scrape_markdown(client, url, args.timeout)
        write_atomically(
            path, render_document(markdown, metadata, url, args.category, query)
        )
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 1

    relative = path.relative_to(REPO_ROOT).as_posix()
    print(f"Wrote {relative} ({len(markdown):,} chars of Markdown) -> {args.category} corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
