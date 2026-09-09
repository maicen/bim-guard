"""Every path in the e2e manifest must resolve, when the corpus is on this machine.

The corpus is not in git. ``test-models`` is a nested clone of
maicen/bimguard-test-models ignored at ``.gitignore:78``, and
``data/test_models/*`` is ignored at ``.gitignore:100`` -- so both exist only
where someone has fetched them, which in practice is the main working tree and
not a ``git worktree``. This therefore skips rather than fails when the models
are absent: a manifest typo should break the build, a missing 365 MB download
should not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "tests" / "e2e" / "e2e-models.json"


#: The two ignored corpus roots. Presence is tested by looking for an actual
#: ``.ifc`` inside them, not by the directory existing: ``data/test_models``
#: holds a committed README, so the directory is there in every worktree while
#: the 365 MB of models is not. Nor can this key on "does any manifest path
#: resolve" -- ``data/test_hospital_mep_scenario.ifc`` is committed too.
CORPUS_ROOTS = (REPO_ROOT / "test-models" / "models", REPO_ROOT / "data" / "test_models")


def test_every_manifest_path_exists() -> None:
    """Each model id must name a file that is really there."""
    if not any(any(root.rglob("*.ifc")) for root in CORPUS_ROOTS if root.is_dir()):
        pytest.skip("IFC corpus not present on this machine; nothing to resolve")
    models = json.loads(MANIFEST.read_text(encoding="utf-8"))["models"]
    missing = {k: v for k, v in models.items() if not (REPO_ROOT / v).exists()}
    assert not missing, f"manifest paths that do not exist: {missing}"
