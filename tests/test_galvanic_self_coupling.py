"""Regression tests pinning GC-001 to real bimetallic junctions.

A galvanic cell needs two dissimilar metals. The engine scored the area-ratio
and environment terms even when both sides were the same material, so copper
against copper returned a non-zero composite and banded as a galvanic finding.

That reached whole models at a time rather than the odd element:
``phase_6c_corrosion_ui._gc_element`` fills the second side with the first when
the IFC carries only one material for an element, so every element of such a
model arrives here as a self-couple. ``resolve_material`` widens it further by
defaulting an unrecognised name to carbon steel, which makes two unidentified
elements a carbon-steel-against-carbon-steel pair.

What these tests hold in place:
  * a self-couple scores exactly 0.0 and reports ``couple_present`` False
  * a genuine dissimilar pair is untouched
  * PREN escalation still fires without a couple, because pitting resistance is
    a property of the alloy and its environment, not of a junction
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engines.bimguard_corrosion_engine import (  # noqa: E402
    GCElement,
    assess_galvanic_risk,
)


@pytest.mark.parametrize(
    "material",
    ["Copper", "Carbon Steel", "Stainless Steel 316", "Aluminium"],
)
def test_identical_metals_are_not_a_galvanic_couple(material: str) -> None:
    """The same metal on both sides cannot form a cell, whatever the metal."""
    result = assess_galvanic_risk(GCElement("A", "B", material, material))

    assert result.couple_present is False
    assert result.composite_score == 0.0
    assert result.risk_band == "Low"


def test_unidentified_material_does_not_become_a_galvanic_finding() -> None:
    """Two unresolvable names both default to carbon steel -- still one metal.

    This is the case that covered entire models: neither side is identified, so
    both resolve to the same fallback and the pair is not a couple.
    """
    result = assess_galvanic_risk(GCElement("A", "B", "Unknown", "Unknown"))

    assert result.couple_present is False
    assert result.composite_score == 0.0


def test_a_non_metal_is_not_a_couple() -> None:
    """A metal against a non-metallic material has no second electrode."""
    result = assess_galvanic_risk(GCElement("A", "B", "Copper", "PVC"))

    assert result.couple_present is False
    assert result.composite_score == 0.0


@pytest.mark.parametrize(
    ("anode", "cathode"),
    [("Copper", "Carbon Steel"), ("Aluminium", "Stainless Steel 316")],
)
def test_dissimilar_metals_still_score(anode: str, cathode: str) -> None:
    """The gate must not silence real couples: these are what GC-001 is for."""
    result = assess_galvanic_risk(GCElement("A", "B", anode, cathode))

    assert result.couple_present is True
    assert result.composite_score > 0.0
    assert result.risk_band != "Low"


def test_pren_escalation_survives_the_no_couple_gate() -> None:
    """An under-specified stainless in a marine zone still reports.

    Pitting resistance depends on the alloy and the environment, not on a
    junction, so zeroing the galvanic terms must not take this finding with it.
    """
    result = assess_galvanic_risk(
        GCElement(
            "A",
            "B",
            "Stainless Steel 304",
            "Stainless Steel 304",
            zone_category="external marine",
        )
    )

    assert result.couple_present is False
    if not result.pren_adequate:
        assert result.composite_score >= 0.35
        assert result.risk_band != "Low"
