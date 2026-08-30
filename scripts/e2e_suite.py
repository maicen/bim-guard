"""Drive every analysis the API exposes over HTTP and report what happened.

Covers the six categories the E2E plan calls for: engine gating, cache
separation, seismic, architecture, schema robustness (IFC2x3 against IFC4),
geometry robustness and a timing baseline, plus export validation for each
analysis that produced a result.

A model the manifest names but the disk does not hold is reported SKIP, never
PASS: a test that did not run has not passed. Run against a server started by
``scripts/e2e_server.py`` with the same manifest.

USAGE

    uv run python scripts/e2e_suite.py --manifest tests/e2e/e2e-models.json
        --base-url http://127.0.0.1:8010 --out docs/validation/data/test-results.json
"""

from __future__ import annotations

import argparse
import io
import json
import time
import zipfile
from pathlib import Path

import httpx

#: Every engine the Piping audit can run, in report order.
ALL_ENGINES = ["GC", "CC", "MC", "MM", "XM"]

#: The two halves of the corrosion run: per element, and once over the network.
ELEMENT_ENGINES = ["GC", "CC", "MC"]
NETWORK_ENGINES = ["MM", "XM"]


class Suite:
    """Runs the checks and records one row per check."""

    def __init__(self, client: httpx.Client, manifest: dict):
        """Bind the suite to a live API and the project-id-to-file manifest."""
        self.client = client
        self.manifest = manifest
        self.rows: list[dict] = []

    # -- recording ---------------------------------------------------------

    def record(self, test: str, status: str, detail: str, data: dict | None = None) -> None:
        """Record one check. ``status`` is PASS, FAIL or SKIP."""
        self.rows.append({"test": test, "status": status, "detail": detail, "data": data or {}})
        print(f"[{status:4}] {test}: {detail}")

    def available(self, project_id: int) -> bool:
        """Whether the model this project maps to is actually on disk."""
        path = self.manifest.get(str(project_id))
        return bool(path and Path(path).is_file())

    # -- API calls ---------------------------------------------------------

    def run_analysis(self, project_id: int, slug: str, engines=None, use_cache=False):
        """POST /api/analyze/run, returning ``(payload, seconds, status_code)``."""
        body = {"project_id": project_id, "slug": slug, "use_cache": use_cache}
        if engines is not None:
            body["engines"] = engines
        started = time.perf_counter()
        response = self.client.post("/api/analyze/run", json=body)
        elapsed = time.perf_counter() - started
        try:
            payload = response.json()
        except ValueError:
            payload = {"detail": response.text[:200]}
        return payload, elapsed, response.status_code

    def export(self, project_id: int, slug: str, fmt: str, engines=None):
        """GET /api/analyze/export for one format."""
        params = [("project_id", project_id), ("slug", slug), ("fmt", fmt)]
        params += [("engines", e) for e in (engines or [])]
        return self.client.get("/api/analyze/export", params=params)

    @staticmethod
    def rulesets(payload: dict) -> dict[str, int]:
        """Count findings by the ruleset each one cites."""
        counts: dict[str, int] = {}
        for issue in payload.get("audit_issues", []):
            code = str(issue.get("rule_id", "")).split(".")[0]
            counts[code] = counts.get(code, 0) + 1
        return dict(sorted(counts.items()))

    # -- categories --------------------------------------------------------

    def piping_gating(self, project_id: int, label: str, deep: bool = True) -> None:
        """TEST 1: only the selected engines execute.

        Args:
            project_id: The project whose model to assess.
            label: Name this model appears under in the report.
            deep: Also check a single-engine and an empty selection. Each
                variant costs a full parse, so the two that re-prove what the
                three-way split already shows run on a subset of models.
        """
        name = f"piping/{label}"
        if not self.available(project_id):
            self.record(f"{name}/gating", "SKIP", "model file not present")
            return

        full, seconds, code = self.run_analysis(project_id, "corrosion", ALL_ENGINES)
        if code != 200:
            self.record(f"{name}/1a-all-engines", "FAIL", f"HTTP {code}: {full.get('detail')}")
            return
        all_counts = self.rulesets(full)
        self.record(f"{name}/1a-all-engines", "PASS", f"{all_counts} in {seconds:.2f}s", all_counts)

        element, _, _ = self.run_analysis(project_id, "corrosion", ELEMENT_ENGINES)
        counts = self.rulesets(element)
        leaked = [c for c in counts if c.startswith(("MM", "XM"))]
        self.record(
            f"{name}/1b-element-only",
            "FAIL" if leaked else "PASS",
            f"{counts}" + (f" leaked {leaked}" if leaked else " (no MM/XM)"),
            counts,
        )

        network, _, _ = self.run_analysis(project_id, "corrosion", NETWORK_ENGINES)
        counts = self.rulesets(network)
        leaked = [c for c in counts if c.startswith(("GC", "CC", "MC"))]
        self.record(
            f"{name}/1c-network-only",
            "FAIL" if leaked else "PASS",
            f"{counts}" + (f" leaked {leaked}" if leaked else " (no GC/CC/MC)"),
            counts,
        )

        if not deep:
            return

        single, _, _ = self.run_analysis(project_id, "corrosion", ["GC"])
        counts = self.rulesets(single)
        others = [c for c in counts if c != "GC-001"]
        self.record(
            f"{name}/1d-single-engine",
            "FAIL" if others else "PASS",
            f"{counts}" + (f" leaked {others}" if others else " (GC-001 only)"),
            counts,
        )

        none, _, _ = self.run_analysis(project_id, "corrosion", [])
        counts = self.rulesets(none)
        self.record(
            f"{name}/1d2-no-engine",
            "FAIL" if counts else "PASS",
            f"{counts or 'no findings, as selected'}",
            counts,
        )

    def piping_cache(self, project_id: int, label: str) -> None:
        """TEST 1e: a selection is part of the cache key."""
        name = f"piping/{label}/1e-cache"
        if not self.available(project_id):
            self.record(name, "SKIP", "model file not present")
            return

        miss_all, t_miss, _ = self.run_analysis(project_id, "corrosion", ALL_ENGINES, use_cache=False)
        _, t_gc, _ = self.run_analysis(project_id, "corrosion", ["GC"], use_cache=True)
        hit_all, t_hit, _ = self.run_analysis(project_id, "corrosion", ALL_ENGINES, use_cache=True)

        same = self.rulesets(miss_all) == self.rulesets(hit_all)
        faster = t_hit < t_miss
        self.record(
            name,
            "PASS" if same and faster else "FAIL",
            f"miss {t_miss:.2f}s, other-selection {t_gc:.2f}s, hit {t_hit:.2f}s, "
            f"identical={same}, faster={faster}",
            {"miss_s": round(t_miss, 3), "hit_s": round(t_hit, 3),
             "speedup": round(t_miss / t_hit, 1) if t_hit else None},
        )

    def exports(self, project_id: int, slug: str, label: str, engines=None) -> None:
        """Validate the three export formats for one analysis."""
        name = f"export/{label}/{slug}"
        if not self.available(project_id):
            self.record(name, "SKIP", "model file not present")
            return

        payload, _, code = self.run_analysis(project_id, slug, engines, use_cache=True)
        if code != 200:
            self.record(name, "SKIP", f"analysis unavailable (HTTP {code})")
            return
        findings = len(payload.get("audit_issues", []))

        csv = self.export(project_id, slug, "csv", engines)
        rows = [r for r in csv.text.strip().splitlines()[1:] if r.strip()]
        self.record(
            f"{name}/csv",
            "PASS" if csv.status_code == 200 and len(rows) == findings else "FAIL",
            f"HTTP {csv.status_code}, {len(rows)} rows vs {findings} findings",
        )

        js = self.export(project_id, slug, "json", engines)
        try:
            parsed = json.loads(js.text)
            ok = js.status_code == 200 and isinstance(parsed, (dict, list))
        except ValueError:
            ok = False
        self.record(f"{name}/json", "PASS" if ok else "FAIL", f"HTTP {js.status_code}, parseable={ok}")

        bcf = self.export(project_id, slug, "bcf", engines)
        try:
            archive = zipfile.ZipFile(io.BytesIO(bcf.content))
            names = archive.namelist()
            markup = [n for n in names if n.endswith("markup.bcf")]
            viewpoints = [n for n in names if n.endswith(".bcfv")]
            # One topic per finding -- including none, which is the correct
            # archive for an analysis that found nothing rather than a failure.
            ok = bcf.status_code == 200 and len(markup) == findings
            detail = f"HTTP {bcf.status_code}, {len(names)} entries, {len(markup)} markup, {len(viewpoints)} viewpoints"
        except zipfile.BadZipFile:
            ok, detail = False, f"HTTP {bcf.status_code}, not a zip"
        self.record(f"{name}/bcf", "PASS" if ok else "FAIL", detail)

    def simple_analysis(self, project_id: int, slug: str, label: str) -> dict | None:
        """TEST 2/3: run one non-corrosion analysis and report what came back."""
        name = f"{slug}/{label}"
        if not self.available(project_id):
            self.record(name, "SKIP", "model file not present")
            return None
        payload, seconds, code = self.run_analysis(project_id, slug, use_cache=False)
        if code != 200:
            self.record(name, "FAIL", f"HTTP {code}: {payload.get('detail')}")
            return None
        stats = payload.get("issue_stats", {})
        self.record(
            name,
            "PASS" if payload.get("audit_issues") else "WARN",
            f"{len(payload.get('audit_issues', []))} findings in {seconds:.2f}s, stats={stats}",
            {"stats": stats, "rulesets": self.rulesets(payload), "seconds": round(seconds, 3)},
        )
        return payload

    def schema_twins(self, ifc4_id: int, ifc2x3_id: int, label: str) -> None:
        """TEST 4: one building in two schemas must produce one answer."""
        name = f"schema/{label}"
        if not (self.available(ifc4_id) and self.available(ifc2x3_id)):
            self.record(name, "SKIP", "one or both twin models not present")
            return
        a, _, _ = self.run_analysis(ifc4_id, "corrosion", ALL_ENGINES)
        b, _, _ = self.run_analysis(ifc2x3_id, "corrosion", ALL_ENGINES)
        ca, cb = self.rulesets(a), self.rulesets(b)
        self.record(
            name,
            "PASS" if ca == cb else "FAIL",
            f"IFC4 {ca} vs IFC2x3 {cb}",
            {"ifc4": ca, "ifc2x3": cb},
        )

    def timing(self, project_id: int, label: str, engines=None) -> None:
        """TEST 6: first run against cached run for one model."""
        name = f"perf/{label}"
        if not self.available(project_id):
            self.record(name, "SKIP", "model file not present")
            return
        size_mb = Path(self.manifest[str(project_id)]).stat().st_size / 1_048_576
        _, cold, code = self.run_analysis(project_id, "corrosion", engines, use_cache=False)
        if code != 200:
            self.record(name, "FAIL", f"HTTP {code}")
            return
        _, warm, _ = self.run_analysis(project_id, "corrosion", engines, use_cache=True)
        self.record(
            name,
            "PASS",
            f"{size_mb:.2f} MB: cold {cold:.2f}s, cached {warm:.2f}s "
            f"({cold / warm:.0f}x)" if warm else f"cold {cold:.2f}s",
            {"size_mb": round(size_mb, 2), "cold_s": round(cold, 3), "warm_s": round(warm, 3)},
        )


def main() -> None:
    """Run every category the manifest has models for and write the results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="tests/e2e/e2e-models.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--out", default="docs/validation/data/test-results.json")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    models = manifest["models"]
    roles = manifest.get("roles", {})

    client = httpx.Client(base_url=args.base_url, timeout=900)
    suite = Suite(client, models)

    deep = roles.get("piping_deep", {})
    for label, project_id in roles.get("piping", {}).items():
        suite.piping_gating(project_id, label, deep=label in deep)
    for label, project_id in deep.items():
        suite.piping_cache(project_id, label)
    for label, project_id in roles.get("exports", {}).items():
        suite.exports(project_id, "corrosion", label, ALL_ENGINES)

    seismic_exports = roles.get("seismic_exports", {})
    for label, project_id in roles.get("seismic", {}).items():
        ran = suite.simple_analysis(project_id, "seismic", label)
        if ran and label in seismic_exports:
            suite.exports(project_id, "seismic", label)

    for label, project_id in roles.get("architecture", {}).items():
        if suite.simple_analysis(project_id, "architecture", label):
            suite.exports(project_id, "architecture", label)

    twins = roles.get("schema_twins", {})
    for label, pair in twins.items():
        suite.schema_twins(pair["ifc4"], pair["ifc2x3"], label)

    for label, project_id in roles.get("geometry", {}).items():
        suite.simple_analysis(project_id, "seismic", f"geometry/{label}")

    for label, project_id in roles.get("performance", {}).items():
        suite.timing(project_id, label, ALL_ENGINES)

    counts = {s: sum(1 for r in suite.rows if r["status"] == s) for s in ("PASS", "FAIL", "WARN", "SKIP")}
    print(f"\n{counts}")
    Path(args.out).write_text(
        json.dumps({"summary": counts, "checks": suite.rows}, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
