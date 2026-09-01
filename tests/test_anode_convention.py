"""
Regression tests pinning the galvanic anode direction.

Two engines read the same GC-001 series and, until this was settled, applied
opposite conventions for which end corrodes. The series is an anodic-index
table: values ascend from platinum (0.00) to magnesium (0.95), and the payload
carries its own note, "Higher potential = more active (anodic) — corrodes
preferentially". Both checks in scripts/verify_anode_convention.py agree —
zinc +0.800 V against copper +0.280 V, and zinc is what galvanising sacrifices.

See docs/defects/defect_report_anode_convention.md.

The physics anchor is the point of these tests: zinc must come out as the
anode. Galvanising exists because it does. If a future edit to the series or
to either engine reverses that, these fail.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.module2_ifc_read.piping_schema import (  # noqa: E402
    BoundingBox,
    EnvironmentClass,
    PipingElement,
    PipingSystem,
    Point3D,
)
from app.modules.module4_comparator import galvanic  # noqa: E402

# Potentials as they appear in the seeded GC-001 payload. Higher is more anodic.
ZINC_V = 0.80
GALV_STEEL_V = 0.82
COPPER_V = 0.28
SS316_V = 0.08


def _rule_pack() -> dict:
    """Build a minimal GC-001 pack carrying only what _assess_pair reads."""
    return {
        "ruleset_id": "BIMGUARD-GC-001",
        "parameters": {
            "galvanic_series": {
                "GalvanisedSteel": GALV_STEEL_V,
                "Copper_C12200": COPPER_V,
                "StainlessSteel_316": SS316_V,
            },
            "environment_voltage_thresholds": {
                EnvironmentClass.UNCLASSIFIED.value: {
                    "max_safe_voltage_v": 0.25,
                    "severity_multiplier": 0.5,
                },
            },
            "area_ratio_bands": [
                {"max_ratio": 0.05, "risk_value": 1.00},
                {"max_ratio": 0.20, "risk_value": 0.75},
                {"max_ratio": 1.00, "risk_value": 0.25},
                {"max_ratio": 999.0, "risk_value": 0.10},
            ],
            "weights": {"voltage": 0.50, "area_ratio": 0.30, "environment": 0.20},
            "risk_band_thresholds": {"medium": 0.35, "high": 0.65, "critical": 0.85},
        },
    }


def _element(element_id: str, material: str, area_m2: float = 1.0) -> PipingElement:
    """Build a minimal element carrying the fields _assess_pair reads."""
    return PipingElement(
        id=element_id,
        ifc_class="IfcPipeSegment",
        subtype="pipe_segment",
        name=f"{material} run",
        bbox=BoundingBox(min=Point3D(0.0, 0.0, 0.0), max=Point3D(1.0, 0.1, 0.1)),
        centroid=Point3D(0.5, 0.05, 0.05),
        material=material,
        system=PipingSystem.DOMESTIC_COLD_WATER,
        environment_class=EnvironmentClass.UNCLASSIFIED,
        wetted_surface_area_m2=area_m2,
        exposed_surface_area_m2=area_m2,
    )


# ---------------------------------------------------------------------------
# galvanic.py — the Path B comparator that carried the wrong convention
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("order", ["galv_first", "copper_first"])
def test_galvanised_steel_is_the_anode_against_copper(order: str) -> None:
    """Zinc sacrifices to copper — whichever order the pair arrives in."""
    galv = _element("GALV-1", "GalvanisedSteel")
    copper = _element("CU-1", "Copper_C12200")
    a, b = (galv, copper) if order == "galv_first" else (copper, galv)

    result = galvanic._assess_pair(a, b, _rule_pack()["parameters"])

    assert result is not None, "a 0.54 V couple should exceed the Medium threshold"
    assert result["anode"].id == "GALV-1", (
        "galvanised steel must be named the anode: it holds the higher anodic "
        f"index ({GALV_STEEL_V} against copper's {COPPER_V}) and galvanising "
        "works by sacrificing the zinc coating"
    )
    assert result["cathode"].id == "CU-1"


def test_copper_is_the_anode_against_stainless() -> None:
    """A second pair, so the test cannot pass by always picking one material."""
    copper = _element("CU-1", "Copper_C12200")
    ss316 = _element("SS-1", "StainlessSteel_316")

    result = galvanic._assess_pair(copper, ss316, _rule_pack()["parameters"])

    assert result is not None
    assert result["anode"].id == "CU-1", (
        f"copper ({COPPER_V}) is anodic to passive 316 ({SS316_V}) in this series"
    )


def test_voltage_gap_is_direction_independent() -> None:
    """The magnitude must not depend on argument order."""
    galv = _element("GALV-1", "GalvanisedSteel")
    copper = _element("CU-1", "Copper_C12200")
    params = _rule_pack()["parameters"]

    forward = galvanic._assess_pair(galv, copper, params)
    reverse = galvanic._assess_pair(copper, galv, params)

    assert forward is not None and reverse is not None
    assert forward["voltage_v"] == pytest.approx(reverse["voltage_v"])
    assert forward["voltage_v"] == pytest.approx(GALV_STEEL_V - COPPER_V)


def test_area_ratio_follows_the_resolved_anode() -> None:
    """
    The area ratio is anode-area over cathode-area, not argument-order over.

    A small anode against a large cathode is the dangerous case. If the
    direction fix did not carry the areas with it, this ratio would invert.
    """
    small_galv = _element("GALV-1", "GalvanisedSteel", area_m2=0.1)
    large_copper = _element("CU-1", "Copper_C12200", area_m2=10.0)
    params = _rule_pack()["parameters"]

    forward = galvanic._assess_pair(small_galv, large_copper, params)
    reverse = galvanic._assess_pair(large_copper, small_galv, params)

    assert forward is not None and reverse is not None
    assert forward["area_ratio"] == pytest.approx(0.01)
    assert reverse["area_ratio"] == pytest.approx(0.01), (
        "argument order must not change which area is the numerator"
    )


# ---------------------------------------------------------------------------
# The series itself
# ---------------------------------------------------------------------------


def _seeded_series() -> dict | None:
    """Recover the seeded GC-001 series, or None when it cannot be reached."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    try:
        from verify_anode_convention import load_series_from_seeder_source
    except ImportError:
        return None
    try:
        materials, _ = load_series_from_seeder_source()
    except RuntimeError:
        return None  # shallow clone, or the payload is genuinely gone
    return materials


def test_seeded_series_still_says_higher_is_anodic() -> None:
    """
    Guard the convention at its source.

    If someone re-authors the series in the other convention, both engines
    silently start naming the wrong victim. This catches that at the data.
    """
    materials = _seeded_series()
    if materials is None:
        pytest.skip("seeded GC-001 payload not recoverable in this checkout")

    zinc = materials.get("zinc") or materials.get("galv_steel")
    copper = materials.get("copper")
    assert zinc and copper, "the series must carry both physics-anchor materials"

    assert zinc["potential_v"] > copper["potential_v"], (
        f"zinc {zinc['potential_v']} must sit above copper {copper['potential_v']}: "
        "this series is an anodic index, where higher is more anodic"
    )
    assert zinc["noble"] is False
    assert copper["noble"] is True


def test_verify_script_runs_and_reports_the_expected_convention() -> None:
    """The verification script is itself pinned, so its verdict cannot drift."""
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "scripts/verify_anode_convention.py", "--from-seeder"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        # The script prints the payload's provenance note, whose smart
        # punctuation is non-ASCII. Without this, text=True decodes with the
        # locale codec and Windows (cp1252) raises on the UTF-8 bytes.
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    if result.returncode == 2:
        pytest.skip("seeded GC-001 payload not recoverable in this checkout")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONVENTION: more_positive_is_anodic" in result.stdout
    assert "bimguard_corrosion_engine.py:353 CORRECT" in result.stdout


# ---------------------------------------------------------------------------
# The live engine — needs the database, so it skips without one
# ---------------------------------------------------------------------------


def test_live_engine_swaps_areas_with_materials() -> None:
    """
    A caller that labels the couple backwards must get both swapped.

    assess_galvanic_risk() reorders anode and cathode when the caller's
    labelling disagrees with the series. Every per-side attribute has to move
    together; leaving the areas behind pairs swapped materials with the
    original side's areas and inverts the area ratio.
    """
    # importorskip() only catches ImportError, and this module raises
    # ValueError("SUPABASE_URL is required") from load_gc_catalog() at import
    # time, so the skip has to be written by hand.
    try:
        import app.engines.bimguard_corrosion_engine as engine
    except Exception as exc:  # noqa: BLE001 - any failure here means no database
        pytest.skip(f"the live engine needs its catalogue at import: {type(exc).__name__}: {exc}")

    # Deliberately mislabelled: copper is named the anode, but the series makes
    # galvanised steel anodic. A tiny anode against a large cathode is the
    # dangerous case, so after the swap the ratio must be 0.1 / 10.0.
    element = engine.GCElement(
        global_id_anode="CU-1",
        global_id_cathode="GALV-1",
        material_anode="copper",
        material_cathode="galvanised steel",
        anode_area_m2=10.0,
        cathode_area_m2=0.1,
    )
    result = engine.assess_galvanic_risk(element)

    assert result.global_id_anode == "GALV-1", "the swap must name the real anode"
    assert result.area_ratio == pytest.approx(0.01, rel=1e-3), (
        "after the swap the ratio is the galvanised area over the copper area; "
        "a value of 100 means the areas did not follow the materials"
    )
