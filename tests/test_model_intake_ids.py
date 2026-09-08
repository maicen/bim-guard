"""Tests for the piping intake IDS and its checker script.

Two things are pinned here:

(a) ``data/ids/bimguard_piping_intake.ids`` parses with ifctester, validates
    against the IDS 1.0 schema, and holds the expected specifications with the
    expected required/optional split;
(b) ``scripts/check_model_intake.py`` measures the demo model's three headline
    counts, which the generator fixes by index rather than by random draw
    (``scripts/generate_demo_mep_model.py:124-141``) so they are exact.

The demo model is generated on demand if absent, because it is gitignored
build output rather than a committed fixture.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
IDS_PATH = REPO_ROOT / "data" / "ids" / "bimguard_piping_intake.ids"
DEMO_MODEL = REPO_ROOT / "data" / "test_hospital_mep_demo.ifc"
GENERATOR = REPO_ROOT / "scripts" / "generate_demo_mep_model.py"

#: Total piping elements the generator writes.
DEMO_TOTAL = 420
#: Elements carrying an IfcMaterial association — 18 of every 20.
DEMO_WITH_MATERIAL = 378
#: Elements carrying Pset_BimGuardHydraulics — 7 of every 10.
DEMO_WITH_HYDRAULICS = 294
#: Elements declaring a second material. Two of every five of the 378 that
#: carry a material, which is 151 — NOT 40% of 420. See the generator's
#: ``has_couple`` docstring: a bracket material on an element whose own
#: material is unknown would be a couple with one side missing.
DEMO_WITH_COUPLE = 151

#: Specification names, in the order the IDS declares them.
EXPECTED_SPECIFICATIONS = [
    "Material association",
    "System assignment",
    "Element name",
    "Material stated as a property",
    "Flow velocity",
    "Operating temperature",
    "Dead-leg length",
    "Dead-leg flag",
    "Environment class",
    "Declared couple — second material at the junction",
    "Nominal diameter",
    "Storey containment",
    "Space containment",
]

EXPECTED_SPECIFICATION_COUNT = 13
EXPECTED_REQUIRED = 3
EXPECTED_OPTIONAL = 10


@pytest.fixture(scope="module")
def demo_model() -> Path:
    """Return the demo model path, generating it if it is not present."""
    if not DEMO_MODEL.exists():
        subprocess.run(
            [sys.executable, str(GENERATOR)], cwd=REPO_ROOT, check=True,
        )
    assert DEMO_MODEL.exists(), f"demo model missing and could not be generated: {DEMO_MODEL}"
    return DEMO_MODEL


@pytest.fixture(scope="module")
def ids_document():
    """Return the parsed IDS, validated against the IDS 1.0 schema on open."""
    from ifctester import ids as ids_module

    return ids_module.open(str(IDS_PATH), validate=True)


# ---------------------------------------------------------------------------
# (a) The IDS itself
# ---------------------------------------------------------------------------


def test_ids_file_exists():
    """The IDS is committed where the checker's default path expects it."""
    assert IDS_PATH.exists(), IDS_PATH


def test_ids_parses_and_has_expected_specification_count(ids_document):
    """13 specifications, parsed by ifctester with schema validation on."""
    assert len(ids_document.specifications) == EXPECTED_SPECIFICATION_COUNT


def test_ids_specification_names(ids_document):
    """The specifications are the ones the checker and the note refer to."""
    assert [s.name for s in ids_document.specifications] == EXPECTED_SPECIFICATIONS


def test_ids_required_optional_split(ids_document):
    """Material, system and name are required; the other ten are optional.

    Optionality is carried by the specification's ``minOccurs``, because IDS
    1.0 permits ``cardinality="optional"`` on a property facet but not on a
    partOf, material or attribute facet.
    """
    usages = [s.get_usage() for s in ids_document.specifications]
    assert usages.count("required") == EXPECTED_REQUIRED
    assert usages.count("optional") == EXPECTED_OPTIONAL

    required_names = {
        s.name for s in ids_document.specifications if s.get_usage() == "required"
    }
    assert required_names == {"Material association", "System assignment", "Element name"}

    for specification in ids_document.specifications:
        if specification.get_usage() == "required":
            assert specification.minOccurs == 1
        else:
            assert specification.minOccurs == 0
        assert specification.maxOccurs == "unbounded"


def test_ids_declares_both_ifc_versions(ids_document):
    """Real models arrive as IFC4 and as IFC2X3, so both are listed."""
    for specification in ids_document.specifications:
        assert set(specification.ifcVersion) == {"IFC4", "IFC2X3"}


def test_every_specification_states_a_consequence(ids_document):
    """A requirement without a stated consequence is not actionable."""
    for specification in ids_document.specifications:
        assert specification.description
        assert "ENGINES:" in specification.description


# ---------------------------------------------------------------------------
# (b) The checker against the demo model
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def demo_results(demo_model):
    """Run the checker's audit over the demo model once, for all count tests."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import check_model_intake

    _document, results = check_model_intake.audit(demo_model, IDS_PATH)
    return results


def test_checker_sees_every_piping_element(demo_results):
    """All 420 generated elements are applicable to every specification."""
    for name, row in demo_results.items():
        assert row["applicable"] == DEMO_TOTAL, name


def test_material_count_matches_the_generator(demo_results):
    """378 of 420 carry a material association — 90%, by generator design."""
    assert demo_results["Material association"]["passed"] == DEMO_WITH_MATERIAL
    assert demo_results["Material association"]["failed"] == DEMO_TOTAL - DEMO_WITH_MATERIAL


def test_hydraulics_count_matches_the_generator(demo_results):
    """294 of 420 carry the hydraulic property set — 70%, by generator design.

    All three hydraulic properties are written together, so velocity, dead-leg
    length and the dead-leg flag each land on the same 294 elements.
    """
    for name in ("Flow velocity", "Dead-leg length", "Dead-leg flag"):
        assert demo_results[name]["passed"] == DEMO_WITH_HYDRAULICS, name


def test_declared_couple_count_matches_the_generator(demo_results):
    """151 of 420 declare a second material, not 168.

    Two of every five, taken over the 378 elements that carry a material of
    their own rather than over all 420.
    """
    assert (
        demo_results["Declared couple — second material at the junction"]["passed"]
        == DEMO_WITH_COUPLE
    )


def test_required_specifications_behave_as_expected_on_the_demo(demo_results):
    """System and name pass outright; material is the one required gap."""
    assert demo_results["System assignment"]["passed"] == DEMO_TOTAL
    assert demo_results["Element name"]["passed"] == DEMO_TOTAL
    assert demo_results["Material association"]["passed"] < DEMO_TOTAL


def test_checker_runs_as_a_script_and_always_exits_zero(demo_model):
    """The checker is a report, not a gate, on a model that fails specs."""
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_model_intake.py"), str(demo_model)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "Per specification" in completed.stdout
    assert "GC-001:" in completed.stdout
    assert f"{DEMO_WITH_MATERIAL} of {DEMO_TOTAL}" in completed.stdout


def test_checker_exits_zero_on_a_missing_model():
    """A path that does not exist is reported, not raised."""
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "check_model_intake.py"),
            str(REPO_ROOT / "data" / "no_such_model.ifc"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
