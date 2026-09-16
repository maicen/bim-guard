"""The viewer deep link's slug map must agree with what the API will run.

A findings deep link carries ``analysis_slug`` so the viewer's export fallback
asks for the archive of the run that raised the finding. The frontend derives
that slug from the finding's rule id (``frontend/src/lib/analysisDomain.ts``),
and ``/api/analyze/export`` re-runs exactly the slug it is given. The two sides
are a contract with no shared source, so these tests read the TypeScript map and
hold it against the backend's own constants: a renamed slug or a new engine code
that only lands on one side fails here rather than in the browser, where it
looks like "element could not be located in this model".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.analysis_runner import RUNNABLE_SLUGS

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DOMAIN_TS = REPO_ROOT / "frontend" / "src" / "lib" / "analysisDomain.ts"

#: Engine code -> the slug whose run produces its findings. The five corrosion
#: engines are seeded by app/services/ruleset_seeder.py; SB-001 is Blue Halo.
EXPECTED_ENGINE_SLUGS = {
    "GC": "corrosion",
    "CC": "corrosion",
    "MC": "corrosion",
    "MM": "corrosion",
    "XM": "corrosion",
    "SB": "seismic",
}


def _rule_prefix_slugs() -> dict[str, str]:
    """Parse ``RULE_PREFIX_SLUGS`` out of the frontend's analysisDomain.ts."""
    source = ANALYSIS_DOMAIN_TS.read_text(encoding="utf-8")
    block = re.search(
        r"const RULE_PREFIX_SLUGS: Record<string, string> = \{(.*?)\};",
        source,
        re.DOTALL,
    )
    assert block, "RULE_PREFIX_SLUGS not found in analysisDomain.ts"
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r'(\w+):\s*"([^"]+)"', block.group(1))
    }


@pytest.mark.parametrize(("engine", "slug"), sorted(EXPECTED_ENGINE_SLUGS.items()))
def test_every_engine_maps_to_a_runnable_slug(engine: str, slug: str):
    """Each engine's findings route to a slug the analysis runner accepts."""
    assert _rule_prefix_slugs().get(engine) == slug
    assert slug in RUNNABLE_SLUGS


def test_the_frontend_never_names_a_slug_the_backend_cannot_run():
    """A typo in the map would send /analyze/export a 400 instead of an archive."""
    for engine, slug in _rule_prefix_slugs().items():
        assert slug in RUNNABLE_SLUGS, f"{engine} -> {slug!r} is not runnable"


def test_seismic_findings_do_not_route_to_the_corrosion_archive():
    """The defect this map exists to prevent, stated as a test."""
    assert _rule_prefix_slugs()["SB"] != "corrosion"
    assert _rule_prefix_slugs()["SB"] == "seismic"
