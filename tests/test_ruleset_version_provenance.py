"""Every XM-001 and SB-001 finding must name the ruleset revision behind it.

Audit F4 (``docs/validation/final-godmode-audit-2026-09-07.md``, trace table A5):
``ruleset_version`` was present on all 1,196 GC/CC/MC/MM findings of the 1917
export and absent from all 510 XM-001 findings and all 2,937 SB-001 findings of
the 1542 export. A consumer could not tell which ruleset revision scored those
rows. MM-001 was given the same stamp in commit 1ec7a76; these two follow it.

The stamp is set in orchestration -- phase_6c for XM-001, phase_6d for SB-001 --
and is read from the ruleset the run actually loaded, never written inline.

Run: uv run pytest tests/test_ruleset_version_provenance.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.comparator.issue_adapter import IssueIdAllocator
from app.modules.ifc_reader.piping_schema import (
    EnvironmentClass,
    JointType,
    PipingElement,
    PipingSystem,
)
from app.modules.phase_6 import phase_6c_corrosion_ui as phase_6c

# TEST DATA ONLY, matching tests/test_cross_material.py: an anodic index, not a
# published series. Injected so this file needs no database.
TEST_SERIES = {
    "GalvanisedSteel": {"potential_v": 0.82, "noble": False, "label": "Galvanised steel"},
    "Copper_C12200": {"potential_v": 0.28, "noble": True, "label": "Copper"},
}

TEST_THRESHOLDS = {
    "controlled": {"max_safe_voltage_v": 0.50},
    "normal": {"max_safe_voltage_v": 0.25},
    "harsh": {"max_safe_voltage_v": 0.15},
}

#: What both stamps must read. Not a literal chosen here: XM-001's comes from
#: data/rulesets/xm_001_cross_material.json and SB-001's from
#: data/rulesets/config_en_1998_1_din_4149.json, and the two tests at the end of
#: this file assert that those files are where the strings came from.
XM_STAMP = "BIMGUARD-XM-001 v1.0.0"
SB_STAMP = "BIMGUARD-SB-001 v1.0.0"


def _element(element_id: str, material: str) -> PipingElement:
    return PipingElement(
        id=element_id,
        ifc_class="IfcPipeSegment",
        subtype="pipe_segment",
        material=material,
        system=PipingSystem.DOMESTIC_HOT_WATER,
        environment_class=EnvironmentClass.T1_INDOOR_DAMP,
        joint_type=JointType.JT003_THREADED,
        properties={"connectivity_source": "centerline"},
    )


@pytest.fixture
def xm_issues(monkeypatch) -> list:
    """Every Issue XM-001 raises over one dissimilar-metal couple."""
    monkeypatch.setattr(phase_6c, "_xm_galvanic_series", lambda: TEST_SERIES)
    monkeypatch.setattr(phase_6c, "_xm_compatibility_thresholds", lambda: TEST_THRESHOLDS)

    left = _element("pipe-galv", "GalvanisedSteel")
    right = _element("pipe-copper", "Copper_C12200")
    left.joined_to.append(right.id)
    right.joined_to.append(left.id)

    issues, error = phase_6c._assess_xm001(
        [left, right], phase_6c.XM, IssueIdAllocator("test-run")
    )
    assert error is None, error
    assert issues, "the couple should have produced at least one XM-001 Issue"
    return issues


def test_an_xm001_finding_names_its_ruleset_revision(xm_issues):
    """One XM-001 finding carries ruleset_version, and it is the pack's own."""
    finding = xm_issues[0]
    assert finding.metadata["ruleset_version"] == XM_STAMP


def test_every_xm001_issue_carries_the_stamp(xm_issues):
    """None of the 510 findings the audit counted may go out unstamped."""
    assert [i for i in xm_issues if not i.metadata.get("ruleset_version")] == []


def test_the_xm_stamp_is_read_from_the_pack_not_written_inline():
    """The version comes from the file. A version the code invents is not provenance."""
    pack = json.loads(
        Path("data/rulesets/xm_001_cross_material.json").read_text(encoding="utf-8")
    )
    assert pack["ruleset_id"] == "BIMGUARD-XM-001"
    assert pack["schema_version"] == "1.0.0"
    assert phase_6c._pack_ruleset_version(pack, "XM-001") == XM_STAMP


def test_the_xm_stamp_falls_back_to_the_mechanism_rather_than_nothing():
    """A pack naming neither field still yields a stamp: unstamped is worse."""
    assert phase_6c._pack_ruleset_version({}, "XM-001") == "XM-001"


# ---------------------------------------------------------------------------
# SB-001
# ---------------------------------------------------------------------------

ifcopenshell = pytest.importorskip("ifcopenshell", reason="Blue Halo needs ifcopenshell")

from app.modules.phase_6.phase_6d_seismic import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    _ruleset_version,
    run_seismic_analysis,
)
from app.modules.blue_halo.halo_volume_generator import load_clearance_config  # noqa: E402


def _minimal_ifc() -> bytes:
    """Two elements with no geometry: enough to reach the Issue builders."""
    model = ifcopenshell.file(schema="IFC4")
    model.create_entity("IfcPipeSegment", GlobalId=ifcopenshell.guid.new(), Name="CHW-01")
    model.create_entity("IfcDuctSegment", GlobalId=ifcopenshell.guid.new(), Name="SA-01")
    return model.to_string().encode("utf-8")


@pytest.fixture(scope="module")
def sb_issues() -> list:
    result = run_seismic_analysis(_minimal_ifc())
    issues = result["audit_issues"]
    assert issues, "the minimal model should have produced data-quality Issues"
    return issues


def test_an_sb001_finding_names_its_ruleset_revision(sb_issues):
    """One SB-001 finding carries ruleset_version, and it is the config's own."""
    assert sb_issues[0].metadata["ruleset_version"] == SB_STAMP


def test_every_sb001_issue_carries_the_stamp(sb_issues):
    """None of the 2,937 findings the audit counted may go out unstamped."""
    assert [i for i in sb_issues if not i.metadata.get("ruleset_version")] == []


def test_the_sb_stamp_is_read_from_the_config_not_written_inline():
    """The version comes from the jurisdiction config the run loaded."""
    raw = json.loads(Path(DEFAULT_CONFIG_PATH).read_text(encoding="utf-8"))
    assert raw["metadata"]["ruleset_id"] == "BIMGUARD-SB-001"
    assert raw["metadata"]["schema_version"] == "1.0.0"
    assert _ruleset_version(load_clearance_config(DEFAULT_CONFIG_PATH)) == SB_STAMP
