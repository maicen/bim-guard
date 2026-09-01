"""Scrape a standards page into Markdown for the NotebookLM corpora.

Fetches content through Firecrawl and writes it into ``docs/scraped_standards/``
with a provenance header. Two modes:

* default -- the first argument is a URL, fetched via the ``scrape`` endpoint.
* ``--search`` -- the first argument is a query, run through the ``search``
  endpoint; the top web result's Markdown is saved.
* ``--local-pdf`` -- the first argument is a URL to a PDF, downloaded with
  ``curl`` and extracted locally with ``pypdf``. Firecrawl rejects any file
  over 50 MiB, which most full standards PDFs exceed, so this path trades the
  hosted converter for a local one while keeping the same output contract.
  ``--section`` narrows the extraction to one numbered section.

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
import subprocess
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

#: Where ``--local-pdf`` caches downloaded source PDFs. Kept out of the corpus
#: directory so a multi-megabyte binary never lands in a NotebookLM workspace.
PDF_CACHE_DIR = REPO_ROOT / "data" / "cache" / "standards-pdf"

#: Titles that mark a soft 404: a page served with 200 that is really an error.
SOFT_ERROR_TITLES = re.compile(
    r"page\s+not\s+found|not\s+found|404|error|access\s+denied|forbidden",
    re.IGNORECASE,
)


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


def assert_successful_response(
    metadata: dict, url: str, allow_suspect_title: bool = False
) -> None:
    """Reject an error page before it can be written into the corpus.

    Firecrawl reports the origin's HTTP status in ``metadata['status_code']``
    and any transport error in ``metadata['error']``, but it still returns the
    rendered error page as Markdown. Without this check a 404 is written to
    ``docs/scraped_standards/`` as though it were the standard, and the
    NotebookLM corpus silently ingests "We're sorry, we can't find the page
    you're looking for" as source material.

    A soft 404 -- an error page served with status 200 -- is caught by title,
    which is weaker evidence, so the message says which test failed.
    """
    status = metadata.get("status_code", metadata.get("statusCode"))
    if status is not None:
        try:
            code = int(status)
        except (TypeError, ValueError):
            code = None
        if code is not None and not (200 <= code < 300):
            error = str(metadata.get("error") or "").strip()
            detail = f" ({error})" if error else ""
            raise FetchError(
                f"{url} returned HTTP {code}{detail}. Refusing to write an "
                "error page into the corpus."
            )

    title = str(metadata.get("title") or "").strip()
    if title and not allow_suspect_title and SOFT_ERROR_TITLES.search(title):
        raise FetchError(
            f"{url} returned HTTP 200 but its title reads as an error page "
            f"({title.splitlines()[0]!r}). Refusing to write it into the "
            "corpus; pass --allow-suspect-title if this is a false positive."
        )


def scrape_markdown(
    client, url: str, timeout: int, allow_suspect_title: bool = False
) -> tuple[str, dict]:
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

    metadata = _metadata_dict(document)
    assert_successful_response(metadata, url, allow_suspect_title)

    markdown = _field(document, "markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise FetchError(
            f"Firecrawl returned no Markdown for {url}. The page may be empty, "
            "JavaScript-gated or blocked by the site."
        )

    return markdown, metadata


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
            # An error page carries a body like any other; skip past it to the
            # next hit rather than failing the whole search.
            try:
                assert_successful_response(metadata, url or f"result {rank}")
            except FetchError as exc:
                failures.append(f"result {rank}: {exc}")
                continue
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


# --------------------------------------------------------------------------
# Local PDF ingestion
# --------------------------------------------------------------------------


def download_pdf(url: str, timeout: int) -> Path:
    """Download *url* to the PDF cache with curl and return the local path.

    Firecrawl refuses any file over 50 MiB, which most complete standards
    PDFs exceed, so the download is done locally instead. curl follows
    redirects and fails loudly on an HTTP error rather than saving the error
    body as a .pdf.
    """
    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(urlparse(url).path).name) or "download"
    if not stem.lower().endswith(".pdf"):
        stem += ".pdf"
    target = PDF_CACHE_DIR / stem

    if target.exists() and target.stat().st_size > 0:
        print(f"Using cached PDF {target.name} ({target.stat().st_size:,} bytes)", file=sys.stderr)
        return target

    print(f"Downloading {url} ...", file=sys.stderr)
    try:
        completed = subprocess.run(
            [
                "curl", "-sSL", "--fail",
                "--max-time", str(timeout),
                "-o", str(target),
                url,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FetchError("curl is not available on PATH; --local-pdf needs it.") from exc

    if completed.returncode != 0:
        target.unlink(missing_ok=True)
        detail = (completed.stderr or "").strip() or f"curl exit {completed.returncode}"
        raise FetchError(f"Download of {url} failed: {detail}")

    if not target.exists() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise FetchError(f"Download of {url} produced no data.")

    header = target.open("rb").read(5)
    if not header.startswith(b"%PDF"):
        target.unlink(missing_ok=True)
        raise FetchError(
            f"{url} did not return a PDF (magic bytes {header!r}). "
            "The server may have served an HTML error page."
        )

    print(f"Downloaded {target.name} ({target.stat().st_size:,} bytes)", file=sys.stderr)
    return target


def extract_pdf_pages(path: Path) -> list[str]:
    """Return the text of every page in *path* using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise FetchError(
            "pypdf is not installed. Run 'uv sync' or 'uv add pypdf'."
        ) from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise FetchError(f"Could not open {path.name} as a PDF: {exc}") from exc

    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:  # a single unreadable page must not abort
            print(f"note: page {index} could not be extracted ({exc})", file=sys.stderr)
            pages.append("")
    return pages


def select_section(pages: list[str], section: str) -> tuple[str, dict]:
    """Return the text of a numbered *section* plus a report on the selection.

    A section runs from its first heading occurrence to the start of the next
    section at the same or a shallower depth -- for ``6.4`` that is ``6.5`` or
    ``7``. Body pages are joined with page markers so a reader can cite the
    page a requirement came from.
    """
    def heading(number: str) -> re.Pattern[str]:
        r"""Return a pattern matching *number* used as a heading.

        The negative lookahead stops ``6.4`` matching the deeper ``6.4.1.4``,
        and requiring a capitalised title after the number stops it matching
        a bare cross-reference.
        """
        return re.compile(
            rf"^[ \t]*{re.escape(number)}(?!\.?\d)[ \t]+[A-Z][^\n]*$",
            re.MULTILINE,
        )

    start_pattern = heading(section)

    # The section ends at the next heading of the SAME depth (6.4 -> 6.5). A
    # shallower fallback (6.4 -> 7) is tried only when that sibling never
    # appears, because a bare chapter number matches far too readily: in
    # FEMA E-74, "7 Haiti Earthquake (Photos courtesy of ...)" is a figure
    # caption, not the start of chapter 7.
    parts = section.split(".")
    sibling = (
        ".".join(parts[:-1] + [str(int(parts[-1]) + 1)])
        if parts[-1].isdigit()
        else None
    )
    fallback = str(int(parts[0]) + 1) if len(parts) > 1 and parts[0].isdigit() else None

    def is_contents_page(text: str) -> bool:
        """Report whether *text* is a table-of-contents page.

        Dot leaders ("6.4 Mechanical .......... 6-162") are the giveaway; a
        contents page carries several, a body page essentially none.
        """
        return len(re.findall(r"\.{5,}", text)) >= 3

    candidates = [
        i
        for i, text in enumerate(pages)
        if text and start_pattern.search(text) and not is_contents_page(text)
    ]
    if not candidates:
        raise FetchError(
            f"Section {section} was not found in the extracted text (outside "
            "the table of contents). The PDF may be image-only, or the "
            "section may be numbered differently."
        )
    first = candidates[0]
    if len(candidates) > 1:
        print(
            f"note: section {section} heading appears on pages "
            f"{[c + 1 for c in candidates]}; using the first",
            file=sys.stderr,
        )

    def find_boundary(number: str) -> int | None:
        """Return the first body page after *first* that opens with *number*."""
        pattern = heading(number)
        for i in range(first + 1, len(pages)):
            text = pages[i]
            if text and not is_contents_page(text) and pattern.search(text):
                return i
        return None

    boundary_page = find_boundary(sibling) if sibling else None
    boundary_kind = f"section {sibling}" if boundary_page is not None else ""
    if boundary_page is None and fallback:
        boundary_page = find_boundary(fallback)
        boundary_kind = f"chapter {fallback}" if boundary_page is not None else ""

    if boundary_page is not None:
        last = max(first, boundary_page - 1)
    else:
        last = len(pages) - 1
        boundary_kind = "end of document"

    chunks = []
    for i in range(first, last + 1):
        if pages[i].strip():
            chunks.append(f"<!-- page {i + 1} -->\n\n{pages[i].strip()}")
    report = {
        "section": section,
        "first_page": first + 1,
        "last_page": last + 1,
        "page_count": last - first + 1,
        "boundary": boundary_kind,
    }
    return "\n\n".join(chunks), report


def local_pdf_markdown(
    url: str, timeout: int, section: str | None
) -> tuple[str, dict, dict]:
    """Download a PDF, extract its text and return (markdown, metadata, report)."""
    path = download_pdf(url, timeout)
    pages = extract_pdf_pages(path)
    non_empty = sum(1 for p in pages if p.strip())
    print(f"Extracted {len(pages)} pages ({non_empty} with text)", file=sys.stderr)

    if non_empty == 0:
        raise FetchError(
            f"{path.name} yielded no extractable text on any of its "
            f"{len(pages)} pages. It is probably a scanned, image-only PDF."
        )

    if section:
        body, report = select_section(pages, section)
        print(
            f"Section {section}: pages {report['first_page']}-{report['last_page']} "
            f"({report['page_count']} pages, bounded by {report['boundary']})",
            file=sys.stderr,
        )
    else:
        body = "\n\n".join(
            f"<!-- page {i + 1} -->\n\n{text.strip()}"
            for i, text in enumerate(pages)
            if text.strip()
        )
        report = {
            "section": None,
            "first_page": 1,
            "last_page": len(pages),
            "page_count": non_empty,
            "boundary": "whole document",
        }

    metadata = {
        "title": Path(urlparse(url).path).stem.replace("_", " ").replace("-", " ").strip(),
        "description": (
            f"Local pypdf extraction of {path.name}; "
            f"{report['page_count']} of {len(pages)} pages"
            + (f"; section {section}" if section else "")
        ),
        "total_pages": len(pages),
        "local_path": str(path.relative_to(REPO_ROOT).as_posix()),
    }
    return body, metadata, report


def render_document(
    markdown: str,
    metadata: dict,
    url: str,
    category: str,
    query: str | None = None,
    report: dict | None = None,
) -> str:
    """Wrap the fetched Markdown in a provenance header for the corpora."""
    title = str(metadata.get("title") or "").strip() or urlparse(url).netloc or "Untitled"
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if report is not None:
        via = "local curl download + pypdf extraction"
    else:
        via = f"Firecrawl {'search' if query else 'scrape'}"
    header = [f"# {title}", ""]
    if query:
        header.append(f"- **Search query:** {query}")
    header += [
        f"- **Source URL:** {url or '(not reported)'}",
        f"- **Category:** {category}",
        f"- **Fetched:** {fetched} via {via}",
    ]
    if report is not None:
        if report.get("section"):
            header.append(f"- **Section extracted:** {report['section']}")
        header += [
            f"- **Pages:** {report['first_page']}-{report['last_page']} "
            f"of {metadata.get('total_pages', '?')} "
            f"(bounded by {report['boundary']})",
            f"- **Cached source:** {metadata.get('local_path', '(not reported)')}",
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--search",
        action="store_true",
        help="treat the first argument as a search query and save the top web result",
    )
    mode.add_argument(
        "--local-pdf",
        action="store_true",
        dest="local_pdf",
        help=(
            "download the URL as a PDF with curl and extract it with pypdf, "
            "bypassing Firecrawl's 50 MiB limit"
        ),
    )
    parser.add_argument(
        "--section",
        default=None,
        help=(
            "with --local-pdf, extract only this numbered section "
            "(e.g. 6.4), bounded by the next sibling section"
        ),
    )
    parser.add_argument(
        "--allow-suspect-title",
        action="store_true",
        dest="allow_suspect_title",
        help="accept a page whose title reads like an error page (status 2xx only)",
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
    if args.section and not args.local_pdf:
        parser.error("--section only applies to --local-pdf")
    if args.section and not re.fullmatch(r"\d+(\.\d+)*", args.section.strip()):
        parser.error("--section must be a dotted section number, e.g. 6.4")
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
        # --local-pdf never calls Firecrawl, so it must not require a key.
        api_key = None if args.local_pdf else load_api_key()
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        report = None
        if args.local_pdf:
            markdown, metadata, report = local_pdf_markdown(
                url, args.timeout, args.section
            )
        else:
            client = build_client(api_key, args.timeout)
            if query is not None:
                print(f"Searching for {query!r} ...", file=sys.stderr)
                markdown, metadata, url = search_top_markdown(
                    client, query, args.timeout
                )
            else:
                print(f"Scraping {url} ...", file=sys.stderr)
                markdown, metadata = scrape_markdown(
                    client, url, args.timeout, args.allow_suspect_title
                )
        write_atomically(
            path,
            render_document(markdown, metadata, url, args.category, query, report),
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
