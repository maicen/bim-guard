"""Warm the analysis cache before a live demo, then prove the warming worked.

WHY THIS EXISTS

    A corrosion run over West Riverside takes minutes; a federated seismic run
    over two models takes about ten. The result is cached, so the second read is
    milliseconds -- but only for the exact key that was warmed. Warming "the
    project" is not enough: every engine chip combination the analyse page can
    produce is its own cache entry, so a presenter who unticks XM-001 mid-demo
    lands on a miss and waits for five engines to run again.

    This runs each combination once, ahead of time, and then verifies each one
    is a hit. A silent warm-up nobody checked is worth nothing on demo day.

MATCHING THE UI'S CACHE KEYS

    The key is ``project_id + slug + model digest + canonicalised engines +
    include_low`` (see ``app/services/analysis_cache.py``). Two of those come
    from how the request is spelled, so this replicates the page exactly:

    * ``frontend/src/routes/AnalyzeView.svelte`` seeds ``selectedEngines`` with
      the short ids ``GC CC MC MM XM`` and sends them as ``requestedEngines``.
      The backend canonicalises them, so ``GC`` and ``GC-001`` share an entry --
      but the short ids are what the page sends, so they are what this sends.
    * The page's results fetch omits ``include_low``, taking the endpoint's
      ``True`` default, so the warm-up posts ``include_low=true``.
    * ``toggleEngine`` cannot empty the selection: the Run button is disabled
      when it would, so the empty set is not a reachable combination.

    Seismic sends no engine selection at all -- it is one kernel with nothing to
    select between -- so it has exactly one entry per project.

USAGE

    uv run python scripts/prewarm_demo.py --piping 1541 --seismic 1542
    uv run python scripts/prewarm_demo.py --piping 1540 1541 --combinations full-only
    uv run python scripts/prewarm_demo.py --base-url http://127.0.0.1:8001 --seismic 1542

Exit status is 0 when every combination verified as a cache hit, 1 when any did
not, so this can gate a demo-day checklist rather than merely inform it.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

#: Engine chip ids, in the order ``AnalyzeView.svelte`` lists them. The short
#: form is deliberate: it is what the page sends.
PIPING_ENGINES: tuple[str, ...] = ("GC", "CC", "MC", "MM", "XM")

#: Seconds any single analysis is allowed to take. A federated seismic run over
#: West Riverside measured 577 s, so the ceiling is well clear of a real run and
#: still bounded enough that a hung backend fails the script rather than the demo.
REQUEST_TIMEOUT = 3600


def engine_combinations(engines: tuple[str, ...] = PIPING_ENGINES, *, full_only: bool = False) -> list[tuple[str, ...]]:
    """Return every engine selection the analyse page can produce.

    Args:
        engines: The chip ids, in page order.
        full_only: Return just the all-engines selection, for a short warm-up
            when only the default view will be shown.

    Returns:
        Selections ordered largest first, so the full run -- the one the page
        opens on, and the slowest -- is warmed before any subset. Each preserves
        the page's chip order. The empty selection is excluded: the page
        disables Run rather than sending it.

    For five engines this is 31 selections: 2**5 - 1.
    """
    full = tuple(engines)
    if full_only:
        return [full]
    combinations: list[tuple[str, ...]] = []
    for size in range(len(full), 0, -1):
        combinations.extend(itertools.combinations(full, size))
    return combinations


@dataclass
class Warmed:
    """One analysis this script asked for, and what came back."""

    project_id: int
    slug: str
    engines: tuple[str, ...]
    duration_s: float
    cached: bool
    issues: int
    error: str = ""


@dataclass
class Verification:
    """Whether a warmed entry actually reads back as a cache hit."""

    project_id: int
    slug: str
    engines: tuple[str, ...]
    cached: bool
    issues: int
    duration_s: float
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.cached and not self.error


@dataclass
class Report:
    """Everything one invocation did, for the exit status and the summary."""

    warmed: list[Warmed] = field(default_factory=list)
    verified: list[Verification] = field(default_factory=list)

    @property
    def warnings(self) -> list[Verification]:
        return [v for v in self.verified if not v.ok]


def _post(base_url: str, path: str, fields: list[tuple[str, str]]) -> tuple[dict, float]:
    """POST form-encoded ``fields``; return the decoded body and elapsed seconds."""
    data = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        body = json.load(response)
    return body, time.monotonic() - started


def _get(base_url: str, path: str, params: list[tuple[str, str]]) -> tuple[dict, float]:
    """GET with repeated query parameters; return the decoded body and elapsed seconds."""
    url = f"{base_url.rstrip('/')}{path}?{urllib.parse.urlencode(params)}"
    started = time.monotonic()
    with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
        body = json.load(response)
    return body, time.monotonic() - started


def warm_corrosion(base_url: str, project_id: int, engines: tuple[str, ...]) -> Warmed:
    """Run one corrosion selection and record what it cost."""
    fields = [("project_id", str(project_id))]
    fields += [("engines", code) for code in engines]
    fields += [("include_low", "true"), ("use_cache", "true")]
    try:
        body, elapsed = _post(base_url, "/api/analyze/corrosion", fields)
    except (urllib.error.URLError, TimeoutError) as exc:
        return Warmed(project_id, "corrosion", engines, 0.0, False, 0, error=str(exc))
    return Warmed(
        project_id=project_id,
        slug="corrosion",
        engines=engines,
        duration_s=elapsed,
        cached=bool(body.get("cached")),
        issues=len(body.get("audit_issues") or []),
    )


def warm_seismic(base_url: str, project_id: int) -> Warmed:
    """Run the seismic kernel for one project. No engine selection exists."""
    try:
        body, elapsed = _post(base_url, "/api/analyze/seismic", [("project_id", str(project_id)), ("use_cache", "true")])
    except (urllib.error.URLError, TimeoutError) as exc:
        return Warmed(project_id, "seismic", (), 0.0, False, 0, error=str(exc))
    return Warmed(
        project_id=project_id,
        slug="seismic",
        engines=(),
        duration_s=elapsed,
        cached=bool(body.get("cached")),
        issues=len(body.get("audit_issues") or []),
    )


def verify(base_url: str, project_id: int, slug: str, engines: tuple[str, ...]) -> Verification:
    """Read the result back the way the page does and report whether it hit.

    ``limit=1`` because this asks a question about the cache, not about the
    findings: paging is applied after the lookup, so one row is enough to learn
    whether the engines ran again.
    """
    params = [("use_cache", "true")]
    params += [("engines", code) for code in engines]
    params += [("limit", "1"), ("offset", "0")]
    try:
        body, elapsed = _get(base_url, f"/api/analyze/results/{project_id}/{slug}", params)
    except (urllib.error.URLError, TimeoutError) as exc:
        return Verification(project_id, slug, engines, False, 0, 0.0, error=str(exc))
    stats = body.get("issue_stats") or {}
    return Verification(
        project_id=project_id,
        slug=slug,
        engines=engines,
        cached=bool(body.get("cached")),
        issues=sum(int(stats.get(k, 0)) for k in ("critical", "high", "medium", "low", "data_quality")),
        duration_s=elapsed,
    )


def _label(engines: tuple[str, ...]) -> str:
    """Render an engine selection for the log, or the seismic placeholder."""
    return ",".join(engines) if engines else "-"


def prewarm(
    base_url: str,
    piping: list[int],
    seismic: list[int],
    *,
    combinations: str = "all",
    log=print,
) -> Report:
    """Warm every entry a demo will read, then verify each one is a hit."""
    report = Report()
    selections = engine_combinations(full_only=combinations == "full-only")

    if piping:
        log(f"Piping: {len(piping)} project(s) x {len(selections)} engine combination(s)")
    for project_id in piping:
        for engines in selections:
            warmed = warm_corrosion(base_url, project_id, engines)
            report.warmed.append(warmed)
            if warmed.error:
                log(f"  project={project_id} slug=corrosion engines={_label(engines)} ERROR {warmed.error}")
                continue
            log(
                f"  project={project_id} slug=corrosion engines={_label(engines)} "
                f"duration={warmed.duration_s:.2f}s cached={str(warmed.cached).lower()} issues={warmed.issues}"
            )

    if seismic:
        log(f"Seismic: {len(seismic)} project(s)")
    for project_id in seismic:
        warmed = warm_seismic(base_url, project_id)
        report.warmed.append(warmed)
        if warmed.error:
            log(f"  project={project_id} slug=seismic engines=- ERROR {warmed.error}")
            continue
        log(
            f"  project={project_id} slug=seismic engines=- "
            f"duration={warmed.duration_s:.2f}s cached={str(warmed.cached).lower()} issues={warmed.issues}"
        )

    log("Verifying (second read of each entry must report cached=true)")
    for project_id in piping:
        for engines in selections:
            result = verify(base_url, project_id, "corrosion", engines)
            report.verified.append(result)
            prefix = "  " if result.ok else "  WARN "
            log(
                f"{prefix}project={project_id} slug=corrosion engines={_label(engines)} "
                f"cached={str(result.cached).lower()} duration={result.duration_s:.2f}s issues={result.issues}"
                + (f" error={result.error}" if result.error else "")
            )
    for project_id in seismic:
        result = verify(base_url, project_id, "seismic", ())
        report.verified.append(result)
        prefix = "  " if result.ok else "  WARN "
        log(
            f"{prefix}project={project_id} slug=seismic engines=- "
            f"cached={str(result.cached).lower()} duration={result.duration_s:.2f}s issues={result.issues}"
            + (f" error={result.error}" if result.error else "")
        )

    return report


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Warm the analysis cache for a live demo and verify every entry is a hit.",
        epilog="Example: uv run python scripts/prewarm_demo.py --piping 1541 --seismic 1542",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Running backend, default http://127.0.0.1:8000")
    parser.add_argument("--piping", nargs="*", type=int, default=[], metavar="ID", help="Piping project ids to warm")
    parser.add_argument("--seismic", nargs="*", type=int, default=[], metavar="ID", help="Seismic project ids to warm")
    parser.add_argument(
        "--combinations",
        choices=("all", "full-only"),
        default="all",
        help="'all' warms every chip combination (31 for five engines); 'full-only' warms just the default view",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Warm, verify, and return a shell exit status."""
    args = build_parser().parse_args(argv)
    if not args.piping and not args.seismic:
        print("Nothing to warm: pass --piping and/or --seismic with project ids.", file=sys.stderr)
        return 2

    started = time.monotonic()
    report = prewarm(
        args.base_url,
        args.piping,
        args.seismic,
        combinations=args.combinations,
    )
    elapsed = time.monotonic() - started

    failed_warms = [w for w in report.warmed if w.error]
    print(
        f"\nWarmed {len(report.warmed)} entr(ies) in {elapsed:.1f}s; "
        f"verified {len(report.verified)}; warnings {len(report.warnings)}; errors {len(failed_warms)}"
    )
    if report.warnings:
        print("Not served from cache on the second read:")
        for warning in report.warnings:
            print(f"  project={warning.project_id} slug={warning.slug} engines={_label(warning.engines)}")
    return 1 if report.warnings or failed_warms else 0


if __name__ == "__main__":
    raise SystemExit(main())
