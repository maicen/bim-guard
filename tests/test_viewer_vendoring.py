"""Guards the contract between ifc-viewer.js and scripts/vendor_viewer.mjs (air-gapped viewer build)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "static" / "js" / "viewer"
SOURCES = [VIEWER / "ifc-viewer.js", VIEWER / "bcf-filter.worker.js"]


def test_every_cdn_import_is_version_pinned():
    """vendor_viewer.mjs reads package versions from the esm.sh URLs, so each must carry one."""
    urls = [u for f in SOURCES for u in re.findall(r"https://esm\.sh/[^\"'\s]+", f.read_text(encoding="utf-8"))]
    assert urls, "expected esm.sh imports in the viewer sources"
    for url in urls:
        assert re.match(r"https://esm\.sh/(@[^/@]+/)?[^@/?]+@\d+\.\d+\.\d+", url), f"unpinned CDN import: {url}"


def test_runtime_cdn_fetches_honour_the_vendor_base():
    """The worker and WASM downloads must switch to local files in the vendored build."""
    src = (VIEWER / "ifc-viewer.js").read_text(encoding="utf-8")
    assert 'typeof __VIEWER_VENDOR_BASE__ === "string"' in src
    assert "VENDOR_BASE ? `${VENDOR_BASE}fragments-worker.mjs`" in src
    assert 'path: VENDOR_BASE ??' in src
    # The only unpkg reference left is the default used when not vendored.
    assert src.count("unpkg.com") == 1


def test_vendor_script_and_docker_stage_exist():
    script = (ROOT / "scripts" / "vendor_viewer.mjs").read_text(encoding="utf-8")
    assert "keepNames: true" in script  # minifying without it broke @thatopen/ui animations
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG VENDOR_VIEWER=false" in docker and "FROM viewer-${VENDOR_VIEWER} AS viewer" in docker
    assert "!scripts/vendor_viewer.mjs" in (ROOT / ".dockerignore").read_text(encoding="utf-8")
