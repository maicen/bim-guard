"""The viewer deep link's slug must agree with what the API will run.

A findings deep link carries ``analysis_slug`` so the viewer's export fallback
asks for the archive of the run that raised the finding. ``RUNNABLE_SLUGS``
names only one slug, so this just pins that the frontend's fallback constant
and the backend's runnable slug are the same string.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.analysis_runner import RUNNABLE_SLUGS

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DOMAIN_TS = REPO_ROOT / "frontend" / "src" / "lib" / "analysisDomain.ts"


def test_only_architecture_is_runnable():
    assert RUNNABLE_SLUGS == ("architecture",)


def test_the_frontend_fallback_slug_matches_the_backend():
    source = ANALYSIS_DOMAIN_TS.read_text(encoding="utf-8")
    fallbacks = set(re.findall(r'fallback:\s*string\s*=\s*"([^"]+)"', source))
    assert fallbacks == {"architecture"}
    assert fallbacks <= set(RUNNABLE_SLUGS)
