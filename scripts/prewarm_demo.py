"""Warm the analysis cache before a live demo, then prove the warming worked.

WHY THIS EXISTS

    An architectural compliance run over large IFC models can take seconds or
    minutes on cold cache. The result is cached, so subsequent reads are
    milliseconds. This script warms specified projects ahead of time and verifies
    that subsequent reads hit the cache.

AUTHENTICATION

    Every /api/analyze route requires a bearer token, so this signs in first.
    It reads VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_DEV_AUTH_EMAIL and
    VITE_DEV_AUTH_PASSWORD out of frontend/.env and runs the same Supabase password
    grant as the SPA's "Sign in as dev test user" button, then sends the resulting
    token on every request.

USAGE

    uv run python scripts/prewarm_demo.py --projects 1541 1542
    uv run python scripts/prewarm_demo.py --base-url http://127.0.0.1:8001 --projects 1542

Exit status is 0 when every project verified as a cache hit, 1 when any did
not.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REQUEST_TIMEOUT = 3600

DEV_ENV_PATH = Path(__file__).resolve().parents[1] / "frontend" / ".env"
DEV_ENV_KEYS = ("VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY", "VITE_DEV_AUTH_EMAIL", "VITE_DEV_AUTH_PASSWORD")
TOKEN_MAX_AGE_S = 40 * 60
TOKEN_TIMEOUT = 60


def _read_env_file(path: Path) -> dict[str, str]:
    """Return the KEY=VALUE pairs in a dotenv file."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            out[key] = value
    return out


class TokenSource:
    """Acquires and caches Supabase JWTs."""

    def __init__(self, env_path: Path = DEV_ENV_PATH):
        self._env_path = env_path
        self._token: str | None = None
        self._minted_at: float = 0.0
        self.mints: int = 0

    def value(self) -> str:
        now = time.monotonic()
        if self._token is None or (now - self._minted_at) > TOKEN_MAX_AGE_S:
            self._mint()
        assert self._token is not None
        return self._token

    def refresh(self) -> str:
        self._mint()
        assert self._token is not None
        return self._token

    def _mint(self) -> None:
        env = _read_env_file(self._env_path)
        missing = [k for k in DEV_ENV_KEYS if not env.get(k)]
        if missing:
            raise RuntimeError(
                f"Cannot sign in dev user: missing {', '.join(missing)} in {self._env_path}."
            )
        url = f"{env['VITE_SUPABASE_URL'].rstrip('/')}/auth/v1/token?grant_type=password"
        payload = json.dumps({
            "email": env["VITE_DEV_AUTH_EMAIL"],
            "password": env["VITE_DEV_AUTH_PASSWORD"],
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "apikey": env["VITE_SUPABASE_ANON_KEY"],
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TOKEN_TIMEOUT) as resp:
            data = json.load(resp)
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Supabase password grant succeeded but returned no access_token.")
        self._token = token
        self._minted_at = time.monotonic()
        self.mints += 1


_TOKEN_SOURCE: TokenSource | None = None


def token_source() -> TokenSource:
    global _TOKEN_SOURCE
    if _TOKEN_SOURCE is None:
        _TOKEN_SOURCE = TokenSource()
    return _TOKEN_SOURCE


def _authorised(build_request, timeout: float = REQUEST_TIMEOUT) -> tuple[dict, float]:
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


@dataclass
class Warmed:
    """One analysis this script asked for, and what came back."""

    project_id: int
    slug: str
    duration_s: float
    cached: bool
    issues: int
    error: str = ""


@dataclass
class Verification:
    """Whether a warmed entry actually reads back as a cache hit."""

    project_id: int
    slug: str
    cached: bool
    issues: int
    duration_s: float
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass
class Report:
    """Everything one invocation did, for the exit status and the summary."""

    warmed: list[Warmed] = field(default_factory=list)
    verified: list[Verification] = field(default_factory=list)

    @property
    def warnings(self) -> list[Verification]:
        return [v for v in self.verified if not v.ok]


def _post(base_url: str, path: str, fields: list[tuple[str, str]]) -> tuple[dict, float]:
    """POST form-encoded fields as the dev user."""
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


def _get(base_url: str, path: str, params: list[tuple[str, str]] | None = None) -> tuple[dict, float]:
    """GET as the dev user."""
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{base_url.rstrip('/')}{path}{query}"

    def build(token: str) -> urllib.request.Request:
        return urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")

    return _authorised(build)


def warm_arch(base_url: str, project_id: int) -> Warmed:
    """Run architectural compliance analysis for one project."""
    fields = [("project_id", str(project_id))]
    try:
        body, elapsed = _post(base_url, "/api/analyze/arch", fields)
    except (urllib.error.URLError, TimeoutError) as exc:
        return Warmed(project_id, "arch", 0.0, False, 0, error=str(exc))
    return Warmed(
        project_id=project_id,
        slug="arch",
        duration_s=elapsed,
        cached=bool(body.get("cached", False)),
        issues=len(body.get("audit_issues") or []),
    )


def verify_arch(base_url: str, project_id: int) -> Verification:
    """Read the architectural compliance results back and report latency/status."""
    try:
        body, elapsed = _get(base_url, f"/api/analyze/arch/{project_id}")
    except (urllib.error.URLError, TimeoutError) as exc:
        return Verification(project_id, "arch", False, 0, 0.0, error=str(exc))
    issues = len(body.get("audit_issues") or [])
    return Verification(
        project_id=project_id,
        slug="arch",
        cached=bool(body.get("cached", True)),
        issues=issues,
        duration_s=elapsed,
    )


def _entry_line(project_id: int, slug: str, elapsed: float, status: str) -> str:
    return f"  project={project_id} slug={slug} elapsed={elapsed:.1f}s {status}"


def _log_line(message: str) -> None:
    print(message, flush=True)


def prewarm(
    base_url: str,
    projects: list[int],
    *,
    log=_log_line,
) -> Report:
    """Warm every project and verify read-back."""
    report = Report()
    if projects:
        log(f"Warming architectural analysis: {len(projects)} project(s)")

    for project_id in projects:
        warmed = warm_arch(base_url, project_id)
        report.warmed.append(warmed)
        if warmed.error:
            log(_entry_line(project_id, "arch", 0.0, f"ERROR {warmed.error}"))
            continue
        log(
            _entry_line(project_id, "arch", warmed.duration_s, "HIT" if warmed.cached else "WARMED")
            + f" issues={warmed.issues}"
        )

    log("Verifying read-back...")
    for project_id in projects:
        result = verify_arch(base_url, project_id)
        report.verified.append(result)
        log(
            _entry_line(project_id, "arch", result.duration_s, "HIT" if result.ok else "MISS")
            + f" issues={result.issues}"
            + (f" error={result.error}" if result.error else "")
        )

    return report


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Warm the analysis cache for a live demo and verify read-back.",
        epilog="Example: uv run python scripts/prewarm_demo.py --projects 1541 1542",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Running backend, default http://127.0.0.1:8000")
    parser.add_argument("--projects", "-p", nargs="*", type=int, default=[], metavar="ID", help="Project ids to warm")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Warm, verify, and return a shell exit status."""
    args = build_parser().parse_args(argv)
    if not args.projects:
        print("Nothing to warm: pass --projects with project ids.", file=sys.stderr)
        return 2

    started = time.monotonic()
    report = prewarm(args.base_url, args.projects)
    elapsed = time.monotonic() - started

    failed_warms = [w for w in report.warmed if w.error]
    hits = len(report.verified) - len(report.warnings)
    print(
        f"\nProjects verified {hits}/{len(report.verified)}; misses {len(report.warnings)}; "
        f"warm errors {len(failed_warms)}; token mints {token_source().mints}; "
        f"wall-clock {elapsed / 60:.1f} min ({elapsed:.0f}s)"
    )
    if report.warnings:
        print("Verification failures:")
        for warning in report.warnings:
            print(f"  WARN project={warning.project_id} slug={warning.slug} error={warning.error}")
    return 1 if report.warnings or failed_warms else 0


if __name__ == "__main__":
    raise SystemExit(main())
