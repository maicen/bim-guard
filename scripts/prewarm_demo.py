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

AUTHENTICATION

    Every /api/analyze route has required a bearer token since 47cf29b, so this
    signs in first. It reads VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY,
    VITE_DEV_AUTH_EMAIL and VITE_DEV_AUTH_PASSWORD out of frontend/.env and runs
    the same Supabase password grant as the SPA's "Sign in as dev test user"
    button, then sends the resulting token on every request. No credential and
    no token is ever printed.

    Supabase issues a one-hour token; a full 63-entry warm runs longer than
    that. The token is therefore re-minted every 40 minutes, and again on any
    401 -- that request is retried once with the fresh token.

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
from pathlib import Path

#: Engine chip ids, in the order ``AnalyzeView.svelte`` lists them. The short
#: form is deliberate: it is what the page sends.
PIPING_ENGINES: tuple[str, ...] = ("GC", "CC", "MC", "MM", "XM")

#: Seconds any single analysis is allowed to take. A federated seismic run over
#: West Riverside measured 577 s, so the ceiling is well clear of a real run and
#: still bounded enough that a hung backend fails the script rather than the demo.
REQUEST_TIMEOUT = 3600


#: Where the dev account's credentials live. The SPA's "Sign in as dev test
#: user" button reads exactly these four keys out of the same file, so the
#: script signs in as the same account by the same password grant rather than
#: inventing a second way in. No value from this file is ever logged.
DEV_ENV_PATH = Path(__file__).resolve().parents[1] / "frontend" / ".env"
DEV_ENV_KEYS = ("VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY", "VITE_DEV_AUTH_EMAIL", "VITE_DEV_AUTH_PASSWORD")

#: Re-mint after this much wall-clock. Supabase issues a one-hour token and a
#: full 63-entry warm outlasts that, so a warm started on a fresh token would
#: still be answering 401 by the time it reached the last combinations.
TOKEN_MAX_AGE_S = 40 * 60

#: Seconds the password grant itself is allowed to take.
TOKEN_TIMEOUT = 60


def _read_env_file(path: Path) -> dict[str, str]:
    """Return the ``KEY=VALUE`` pairs in a dotenv file.

    Leading whitespace and surrounding quotes are stripped, matching what
    ``python-dotenv`` and Vite both accept. The caller must not log the values.
    """
    values: dict[str, str] = {}
    with open(path, encoding="utf-8-sig") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def mint_dev_token(env_path: Path = DEV_ENV_PATH) -> str:
    """Sign in as the dev account and return its Supabase access token.

    This is the password grant behind ``signInAsDevUser`` in
    ``frontend/src/lib/auth.svelte.ts`` -- a real Supabase session, which the
    backend still verifies against the JWKS. Nothing about authentication is
    bypassed; the script simply holds a token the way the browser does.

    Raises:
        RuntimeError: if the credentials file is missing a key, or the grant
            returns no token. Neither message quotes a credential.
    """
    try:
        env = _read_env_file(env_path)
    except OSError as exc:
        raise RuntimeError(f"cannot read {env_path}: {exc.strerror}") from exc
    missing = [key for key in DEV_ENV_KEYS if not env.get(key)]
    if missing:
        raise RuntimeError(f"{env_path} does not define {', '.join(missing)}")

    anon_key = env["VITE_SUPABASE_ANON_KEY"]
    request = urllib.request.Request(
        env["VITE_SUPABASE_URL"].rstrip("/") + "/auth/v1/token?grant_type=password",
        data=json.dumps({"email": env["VITE_DEV_AUTH_EMAIL"], "password": env["VITE_DEV_AUTH_PASSWORD"]}).encode(),
        headers={"Content-Type": "application/json", "apikey": anon_key, "Authorization": f"Bearer {anon_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TOKEN_TIMEOUT) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"password grant refused with HTTP {exc.code}") from exc
    token = body.get("access_token")
    if not token:
        raise RuntimeError("password grant returned no access_token")
    return token


class DevToken:
    """Holds one dev access token and re-mints it before Supabase expires it.

    ``value`` is what every request asks for; it mints on first use and again
    once the held token passes ``max_age_s``. ``refresh`` forces a new one --
    that is the 401 path, where the token died earlier than the clock said.
    """

    def __init__(self, mint=mint_dev_token, *, max_age_s: float = TOKEN_MAX_AGE_S, clock=time.monotonic):
        self._mint = mint
        self._max_age = max_age_s
        self._clock = clock
        self._token = ""
        self._minted_at = 0.0
        self.mints = 0

    def value(self) -> str:
        """Return a token, minting a fresh one if none is held or it has aged out."""
        if not self._token or self._clock() - self._minted_at >= self._max_age:
            return self.refresh()
        return self._token

    def refresh(self) -> str:
        """Mint a new token unconditionally and return it."""
        self._token = self._mint()
        self._minted_at = self._clock()
        self.mints += 1
        return self._token


_token_source: DevToken | None = None


def token_source() -> DevToken:
    """Return the process-wide token holder, creating it on first use."""
    global _token_source
    if _token_source is None:
        _token_source = DevToken()
    return _token_source


def _authorised(build_request, *, timeout: int = REQUEST_TIMEOUT) -> tuple[dict, float]:
    """Send a bearer-authenticated request, re-minting once on a 401.

    ``build_request`` takes a token and returns the ``Request`` to send, so the
    retry carries the new token rather than replaying the dead one. Exactly one
    re-mint and one retry: a second 401 is a real failure, not an expiry.
    """
    source = token_source()
    started = time.monotonic()
    try:
        with urllib.request.urlopen(build_request(source.value()), timeout=timeout) as response:
            return json.load(response), time.monotonic() - started
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise
    with urllib.request.urlopen(build_request(source.refresh()), timeout=timeout) as response:
        return json.load(response), time.monotonic() - started


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
    """POST form-encoded ``fields`` as the dev user; return the body and elapsed seconds."""
    data = urllib.parse.urlencode(fields).encode()
    url = base_url.rstrip("/") + path

    def build(token: str) -> urllib.request.Request:
        return urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )

    return _authorised(build)


def _get(base_url: str, path: str, params: list[tuple[str, str]]) -> tuple[dict, float]:
    """GET with repeated query parameters as the dev user; return body and elapsed seconds."""
    url = f"{base_url.rstrip('/')}{path}?{urllib.parse.urlencode(params)}"

    def build(token: str) -> urllib.request.Request:
        return urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")

    return _authorised(build)


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


def _entry_line(project_id: int, slug: str, index: int, total: int, engines: tuple[str, ...], elapsed: float, status: str) -> str:
    """One per-entry progress line.

    ``status`` is WARMED when the engines just ran, HIT when the backend served
    the entry from cache, MISS when a verification read did not.
    """
    return (
        f"  project={project_id} slug={slug} combo={index}/{total} "
        f"engines={_label(engines)} elapsed={elapsed:.1f}s {status}"
    )


def _log_line(message: str) -> None:
    """Print a progress line and flush, so a long warm shows movement."""
    print(message, flush=True)


def prewarm(
    base_url: str,
    piping: list[int],
    seismic: list[int],
    *,
    combinations: str = "all",
    log=_log_line,
) -> Report:
    """Warm every entry a demo will read, then verify each one is a hit."""
    report = Report()
    selections = engine_combinations(full_only=combinations == "full-only")

    total = len(selections)

    if piping:
        log(f"Warming piping: {len(piping)} project(s) x {total} engine combination(s)")
    for project_id in piping:
        for index, engines in enumerate(selections, start=1):
            warmed = warm_corrosion(base_url, project_id, engines)
            report.warmed.append(warmed)
            if warmed.error:
                log(_entry_line(project_id, "corrosion", index, total, engines, 0.0, f"ERROR {warmed.error}"))
                continue
            log(
                _entry_line(
                    project_id, "corrosion", index, total, engines,
                    warmed.duration_s, "HIT" if warmed.cached else "WARMED",
                )
                + f" issues={warmed.issues}"
            )

    if seismic:
        log(f"Warming seismic: {len(seismic)} project(s)")
    for project_id in seismic:
        warmed = warm_seismic(base_url, project_id)
        report.warmed.append(warmed)
        if warmed.error:
            log(_entry_line(project_id, "seismic", 1, 1, (), 0.0, f"ERROR {warmed.error}"))
            continue
        log(
            _entry_line(project_id, "seismic", 1, 1, (), warmed.duration_s, "HIT" if warmed.cached else "WARMED")
            + f" issues={warmed.issues}"
        )

    log("Verifying (second read of each entry must report cached=true)")
    for project_id in piping:
        for index, engines in enumerate(selections, start=1):
            result = verify(base_url, project_id, "corrosion", engines)
            report.verified.append(result)
            log(
                _entry_line(project_id, "corrosion", index, total, engines, result.duration_s, "HIT" if result.ok else "MISS")
                + f" issues={result.issues}"
                + (f" error={result.error}" if result.error else "")
            )
    for project_id in seismic:
        result = verify(base_url, project_id, "seismic", ())
        report.verified.append(result)
        log(
            _entry_line(project_id, "seismic", 1, 1, (), result.duration_s, "HIT" if result.ok else "MISS")
            + f" issues={result.issues}"
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
    hits = len(report.verified) - len(report.warnings)
    print(
        f"\nEntries verified {hits}/{len(report.verified)}; misses {len(report.warnings)}; "
        f"warm errors {len(failed_warms)}; token mints {token_source().mints}; "
        f"wall-clock {elapsed / 60:.1f} min ({elapsed:.0f}s)"
    )
    if report.warnings:
        print("Not served from cache on the second read:")
        for warning in report.warnings:
            print(f"  WARN project={warning.project_id} slug={warning.slug} engines={_label(warning.engines)}")
    return 1 if report.warnings or failed_warms else 0


if __name__ == "__main__":
    raise SystemExit(main())
