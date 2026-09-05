"""One analysis, many reads: cache reuse, export defaults and finding provenance.

The 2026-09-06 audit found the demo path re-running the engines for every read.
``POST /analyze/corrosion`` passed ``use_cache=False`` unconditionally, the
export forked the cache key by passing the caller's ``include_low`` into the
run, and the store expired after 30 minutes. These tests pin the behaviour that
replaces it: analyse once, then results, exports and chip toggles are served
from the stored result.
"""

from __future__ import annotations

import io
import zipfile
from unittest.mock import patch
from xml.etree import ElementTree as ET

from starlette.testclient import TestClient

from app.main import app
from app.modules.comparator.issue_schema import Issue, RiskBand
from app.services.analysis_cache import ANALYSIS_CACHE, AnalysisCache, CacheKey

client = TestClient(app)

PROJECT_ID = 4242
MODEL_BYTES = b"ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"


def _issues() -> list[Issue]:
    """Two Medium verdicts, three Low verdicts and two data-quality notes."""
    issues = [
        Issue(
            id=f"MED-{i}",
            element_id=f"elem_med_{i}",
            rule_id="CC-001.01",
            title=f"Medium finding {i}",
            band=RiskBand.MEDIUM,
            score=0.5,
            mechanism="CC-001 crevice corrosion",
            metadata={"mechanism_code": "CC-001"},
        )
        for i in range(2)
    ]
    issues += [
        Issue(
            id=f"LOW-{i}",
            element_id=f"elem_low_{i}",
            rule_id="GC-001.01",
            title=f"Low finding {i}",
            band=RiskBand.LOW,
            score=0.1,
            mechanism="GC-001 galvanic corrosion",
            metadata={"mechanism_code": "GC-001"},
        )
        for i in range(3)
    ]
    issues += [
        Issue(
            id=f"DQ-{i}",
            element_id=f"elem_dq_{i}",
            rule_id="MC-001.DATA",
            title=f"Data quality note {i}",
            band=RiskBand.LOW,
            score=0.1,
            mechanism="data_quality",
            metadata={"check": "hydraulics_unavailable", "mechanism_code": "MC-001"},
        )
        for i in range(2)
    ]
    return issues


def _result() -> dict:
    """An ``AnalysisResult`` shaped like the corrosion runner's."""
    return {
        "pipeline": "audit",
        "project_id": PROJECT_ID,
        "slug": "corrosion",
        "element_count": 7,
        "audit_issues": _issues(),
        "issue_stats": {
            "total": 2,
            "critical": 0,
            "high": 0,
            "medium": 2,
            "low": 3,
            "data_quality": 2,
        },
        "compliance_error": None,
        "compliance_is_demo": False,
    }


def _topics(archive: bytes) -> int:
    """Count Topic elements across every markup file in a BCF archive."""
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        return sum(
            len(ET.fromstring(bundle.read(name).decode("utf-8")).findall(".//Topic"))
            for name in bundle.namelist()
            if name.endswith("markup.bcf")
        )


# ── The cache serves the second read ─────────────────────────────────────────


def test_second_run_with_identical_arguments_is_served_from_the_cache():
    """run_analysis runs the engines once; the identical second call is a hit.

    The engines are counted rather than timed: a hit is defined by not running
    them again, and a timing assertion would be a flake on a loaded machine.
    """
    from app.services import analysis_runner

    ANALYSIS_CACHE.clear()
    runs = []

    def fake_corrosion(content, project_id, engines, *, include_low=True):
        runs.append(engines)
        return _result()

    with (
        patch.object(analysis_runner, "model_bytes", return_value=(MODEL_BYTES, None)),
        patch.object(analysis_runner, "_run_corrosion_tracked", side_effect=fake_corrosion),
    ):
        first = analysis_runner.run_analysis(
            "corrosion", PROJECT_ID, engines=["GC-001", "CC-001"], include_low=True
        )
        second = analysis_runner.run_analysis(
            "corrosion", PROJECT_ID, engines=["GC-001", "CC-001"], include_low=True
        )

    assert first["cached"] is False
    assert second["cached"] is True
    assert len(runs) == 1, "the engines ran twice for one unchanged model"
    assert len(second["audit_issues"]) == len(first["audit_issues"])
    assert second["issue_stats"] == first["issue_stats"]


def test_a_different_engine_selection_is_a_different_result():
    """Toggling a chip must miss rather than serve another selection's answer."""
    from app.services import analysis_runner

    ANALYSIS_CACHE.clear()
    runs = []

    def fake_corrosion(content, project_id, engines, *, include_low=True):
        runs.append(engines)
        return _result()

    with (
        patch.object(analysis_runner, "model_bytes", return_value=(MODEL_BYTES, None)),
        patch.object(analysis_runner, "_run_corrosion_tracked", side_effect=fake_corrosion),
    ):
        analysis_runner.run_analysis("corrosion", PROJECT_ID, engines=["GC-001", "CC-001"])
        narrowed = analysis_runner.run_analysis("corrosion", PROJECT_ID, engines=["GC-001"])

    assert narrowed["cached"] is False
    assert len(runs) == 2


def test_export_is_served_from_the_run_the_page_already_computed():
    """Analysing once then exporting three formats runs the engines once.

    This is the audit's F7: the export recomputed, and produced a total two
    issues different from the run it was meant to be exporting.
    """
    from app.services import analysis_runner

    ANALYSIS_CACHE.clear()
    runs = []

    def fake_corrosion(content, project_id, engines, *, include_low=True):
        runs.append(engines)
        return _result()

    with (
        patch.object(analysis_runner, "model_bytes", return_value=(MODEL_BYTES, None)),
        patch.object(analysis_runner, "_run_corrosion_tracked", side_effect=fake_corrosion),
    ):
        analysis_runner.run_analysis("corrosion", PROJECT_ID, engines=["GC-001", "CC-001"])
        for fmt in ("csv", "json", "bcf"):
            response = client.get(
                f"/api/analyze/export?project_id={PROJECT_ID}&slug=corrosion&fmt={fmt}"
                "&engines=GC-001&engines=CC-001"
            )
            assert response.status_code == 200, fmt

    assert len(runs) == 1, f"the engines ran {len(runs)} times for one analysis plus three exports"


def test_export_asking_to_drop_low_reuses_the_full_run():
    """``include_low=false`` filters the cached superset instead of re-running.

    Passing it into the run forked the cache key, which is how a Medium-only
    download came to recompute a page's whole analysis.
    """
    from app.services import analysis_runner

    ANALYSIS_CACHE.clear()
    runs = []

    def fake_corrosion(content, project_id, engines, *, include_low=True):
        runs.append(include_low)
        return _result()

    with (
        patch.object(analysis_runner, "model_bytes", return_value=(MODEL_BYTES, None)),
        patch.object(analysis_runner, "_run_corrosion_tracked", side_effect=fake_corrosion),
    ):
        analysis_runner.run_analysis("corrosion", PROJECT_ID, include_low=True)
        response = client.get(
            f"/api/analyze/export?project_id={PROJECT_ID}&slug=corrosion&fmt=csv&include_low=false"
        )

    assert response.status_code == 200
    assert len(runs) == 1, "include_low forked the cache key and forced a recompute"
    # 2 Medium + 2 data-quality notes survive; the 3 Low verdicts do not.
    assert len(response.text.strip().splitlines()) == 5


def test_cache_capacity_and_ttl_come_from_the_environment():
    """A results page revisited an hour later must still be a hit."""
    from app.services import analysis_cache

    assert analysis_cache.MAX_ENTRIES == 64
    assert analysis_cache.TTL_SECONDS == 86400.0

    store = AnalysisCache(max_entries=analysis_cache.MAX_ENTRIES, ttl_seconds=analysis_cache.TTL_SECONDS)
    key = CacheKey(project_id=PROJECT_ID, slug="corrosion", source_sha256="abc", engines=("GC-001",))
    store.put(key, {"audit_issues": []})

    with patch("app.services.analysis_cache.time.monotonic", return_value=3600.0):
        assert store.get(key) is not None, "an entry expired within the hour"


def test_env_override_is_read_and_a_bad_value_falls_back():
    """The knobs are configurable, and a typo must not stop the server booting."""
    from app.services.analysis_cache import _env_number

    with patch.dict("os.environ", {"BIMGUARD_CACHE_TTL_SECONDS": "120"}):
        assert _env_number("BIMGUARD_CACHE_TTL_SECONDS", 86400.0) == 120.0
    for bad in ("", "soon", "-5", "0"):
        with patch.dict("os.environ", {"BIMGUARD_CACHE_ENTRIES": bad}):
            assert _env_number("BIMGUARD_CACHE_ENTRIES", 64) == 64


# ── Export defaults follow the ruleset's band contract ───────────────────────


def test_bcf_default_carries_only_medium_and_above():
    """Low verdicts and data-quality notes stay out of the coordination archive."""
    with patch("app.api.analyze.run_analysis", return_value=_result()):
        response = client.get(f"/api/analyze/export?project_id={PROJECT_ID}&slug=corrosion&fmt=bcf")

    assert response.status_code == 200
    assert _topics(response.content) == 2


def test_bcf_still_carries_low_and_notes_when_asked_explicitly():
    """Both remain available as opt-ins; only the default changed."""
    with patch("app.api.analyze.run_analysis", return_value=_result()):
        response = client.get(
            f"/api/analyze/export?project_id={PROJECT_ID}&slug=corrosion&fmt=bcf"
            "&include_low=true&include_data_quality=true"
        )

    assert response.status_code == 200
    assert _topics(response.content) == 7


def test_csv_default_stays_the_asset_register():
    """CSV keeps every assessed element and every note: 7 rows plus a header."""
    with patch("app.api.analyze.run_analysis", return_value=_result()):
        response = client.get(f"/api/analyze/export?project_id={PROJECT_ID}&slug=corrosion&fmt=csv")

    assert response.status_code == 200
    assert len(response.text.strip().splitlines()) == 8


def test_json_default_stays_the_asset_register():
    """JSON keeps the same set as CSV, verdicts and notes together."""
    with patch("app.api.analyze.run_analysis", return_value=_result()):
        response = client.get(f"/api/analyze/export?project_id={PROJECT_ID}&slug=corrosion&fmt=json")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["findings"]) + len(payload["data_quality"]) == 7
