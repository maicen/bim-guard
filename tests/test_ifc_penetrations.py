"""Host resolution, annular clearance, and the PC-001 end-to-end verdict.

The last test in this file is the one that matters: it builds the NFPA 13 mock
model, runs the seeded BIMGUARD-PC-001 rule shape through Module 2 and Module 4,
and asserts that the pipe through the concrete wall FAILS while the otherwise
identical pipe through the gypsum wall is WAIVED. Everything above it exists so
that when that assertion breaks, the failure names which half broke.

The model is built into ``tmp_path`` by the same script that produces
``data/test_models/nfpa13_test.ifc``, so the fixture and the checked-in artefact
can never drift apart.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from app.modules.module4_comparator import Module4_Comparator

ifcopenshell = pytest.importorskip("ifcopenshell")

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = REPO_ROOT / "scripts" / "generate_mock_ifc_penetrations.py"

from app.modules.module2_ifc_read import ifc_penetrations  # noqa: E402


def _load_generator():
    """Import the mock-model generator by path (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("_nfpa13_mock", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mock_model_path(tmp_path_factory) -> Path:
    """Build the two-penetration NFPA 13 model once for this module."""
    if not GENERATOR.exists():
        pytest.skip("mock generator not present")
    generator = _load_generator()
    out = tmp_path_factory.mktemp("nfpa13") / "nfpa13_test.ifc"
    generator.build(out)
    return out


@pytest.fixture(scope="module")
def model(mock_model_path):
    return ifcopenshell.open(str(mock_model_path))


def _pipe(model, fragment: str):
    for pipe in model.by_type("IfcPipeSegment"):
        if fragment in (pipe.Name or ""):
            return pipe
    raise AssertionError(f"no pipe matching {fragment!r}")


class TestIsBreakaway:
    """Material classification is tri-state and requires every layer to match."""

    def test_gypsum_is_breakaway(self):
        assert ifc_penetrations.is_breakaway(["Gypsum Board"]) is True

    def test_matching_is_case_and_substring_insensitive(self):
        assert ifc_penetrations.is_breakaway(["5/8in TYPE X Gypsum Wallboard"]) is True

    def test_concrete_is_not_breakaway(self):
        assert ifc_penetrations.is_breakaway(["Concrete"]) is False

    def test_unknown_material_is_undetermined_not_false(self):
        # The distinction the whole design rests on: no data is not a negative.
        assert ifc_penetrations.is_breakaway([]) is None
        assert ifc_penetrations.is_breakaway(None) is None

    def test_every_layer_must_be_breakaway(self):
        # Gypsum facing on a concrete core is not frangible: the core still
        # restrains the pipe.
        assert ifc_penetrations.is_breakaway(["Gypsum Board", "Concrete"]) is False


class TestHostResolution:
    """The wall a pipe passes through, via the opening chain."""

    def test_pipe_resolves_its_opening(self, model):
        openings = ifc_penetrations.resolve_openings(_pipe(model, "Pipe A"))
        assert len(openings) == 1
        assert openings[0].is_a("IfcOpeningElement")

    def test_pipe_resolves_its_host_wall(self, model):
        hosts = ifc_penetrations.resolve_hosts(_pipe(model, "Pipe A"))
        assert [h.is_a() for h in hosts] == ["IfcWall"]
        assert "Concrete" in hosts[0].Name

    def test_gypsum_pipe_resolves_the_gypsum_wall(self, model):
        hosts = ifc_penetrations.resolve_hosts(_pipe(model, "Pipe B"))
        assert "Gypsum" in hosts[0].Name

    def test_interference_index_finds_the_same_wall(self, model):
        # The second, independent route: a model that declares interference but
        # writes no opening must still resolve a host.
        index = ifc_penetrations.build_interference_index(model)
        pipe = _pipe(model, "Pipe A")
        assert any(h.is_a("IfcWall") for h in index.get(pipe.id(), []))

    def test_wall_is_not_its_own_host(self, model):
        wall = model.by_type("IfcWall")[0]
        assert ifc_penetrations.resolve_hosts(wall) == []


class TestAnnularClearance:
    """The radial gap, measured from the pipe surface to the opening edge."""

    def test_clearance_is_radial_not_diametral(self, model):
        # 63.5 mm hole around a 50.8 mm pipe: 6.35 mm radially, not 12.7 mm.
        clearance, detail = ifc_penetrations.annular_clearance_mm(_pipe(model, "Pipe A"))
        assert clearance == pytest.approx(6.35, abs=0.01)
        assert detail["method"] == "profile_radius_difference"

    def test_both_penetrations_measure_the_same(self, model):
        a, _ = ifc_penetrations.annular_clearance_mm(_pipe(model, "Pipe A"))
        b, _ = ifc_penetrations.annular_clearance_mm(_pipe(model, "Pipe B"))
        assert a == b

    def test_element_with_no_opening_is_undetermined(self, model):
        wall = model.by_type("IfcWall")[0]
        clearance, detail = ifc_penetrations.annular_clearance_mm(wall)
        assert clearance is None
        assert "no IfcOpeningElement" in detail["reason"]


# ── End to end ────────────────────────────────────────────────────────────────

#: The seeded BIMGUARD-PC-001 requirement, in the shape RuleService stores it.
PC_001_01 = {
    "reference": "PC-001.01",
    "description": 'Annular clearance 50 mm, nominal 1" through 3-1/2"',
    "target_ifc_class": "IfcPipeSegment",
    "property_name": "AnnularClearance",
    "operator": ">=",
    "check_value": 50.0,
    "unit": "mm",
    "applies_when": {
        "target_ifc_class": "IfcPipeSegment",
        "penetrates": ["IfcWall", "IfcSlab", "IfcFooting", "IfcPlate"],
        "nominal_diameter_mm": {"min": 25.4, "max": 88.9},
    },
    "exceptions": ["PC-001.03"],
}

#: The breakaway exemption it cites, as its own rule row.
PC_001_03 = {
    "reference": "PC-001.03",
    "description": "Clearance exemption — Breakaway or frangible construction",
    "target_ifc_class": "IfcPipeSegment",
    "property_name": "AnnularClearance",
    "operator": "exempt",
    "applies_when": {
        "host_material_any_of": ["gypsum", "plasterboard", "drywall"],
        "host_is_breakaway": True,
    },
    "exceptions": [],
}


def _penetrating(extraction):
    """Return the two pipes that pass through a wall.

    The mock model also carries suspended runs used by the support tests, and
    those penetrate nothing. Selecting by name keeps these assertions about the
    penetration pair even as the shared model grows.
    """
    return [el for el in extraction[0]["elements"] if "through" in el["name"]]


@pytest.fixture(scope="module")
def pc001_result(mock_model_path):
    """Run the requirement plus its exemption through Modules 2 and 4."""
    from app.modules.module2_ifc_read import Module2_IFCRead

    extraction = Module2_IFCRead(mock_model_path).extract_for_compliance(
        [PC_001_01, PC_001_03]
    )
    return extraction, Module4_Comparator().validate_metadata(extraction)


class TestPC001EndToEnd:
    """Concrete fails, gypsum is waived — the result the mock model exists for."""

    def test_waiver_definition_is_not_evaluated_standalone(self, pc001_result):
        extraction, results = pc001_result
        assert [item["rule_ref"] for item in extraction] == ["PC-001.01"]
        assert [r["rule_ref"] for r in results] == ["PC-001.01"]

    def test_clearance_was_derived_from_geometry(self, pc001_result):
        extraction, _ = pc001_result
        for el in _penetrating(extraction):
            assert el["actual_value"] == pytest.approx(6.35, abs=0.01)

    def test_suspended_pipes_have_no_clearance_to_derive(self, pc001_result):
        # The model also carries suspended runs that pass through nothing.
        # They must report no clearance rather than a fabricated one.
        extraction, _ = pc001_result
        suspended = [
            el for el in extraction[0]["elements"] if "through" not in el["name"]
        ]
        assert suspended, "the mock model no longer carries suspended runs"
        assert all(el["actual_value"] is None for el in suspended)

    def test_rule_fails_overall(self, pc001_result):
        _, results = pc001_result
        assert results[0]["status"] == "FAIL"
        assert results[0]["fail_count"] == 1
        assert results[0]["waived_count"] == 1

    def test_concrete_penetration_fails(self, pc001_result):
        _, results = pc001_result
        entry = next(
            e for e in results[0]["all_elements"] if "concrete" in e["element_name"]
        )
        assert entry["status"] == "FAIL"

    def test_gypsum_penetration_is_waived(self, pc001_result):
        _, results = pc001_result
        entry = next(
            e for e in results[0]["all_elements"] if "gypsum" in e["element_name"]
        )
        assert entry["status"] == "WAIVED"
        assert "PC-001.03" in entry["reason"]

    def test_waiver_names_the_exemption_that_granted_it(self, pc001_result):
        _, results = pc001_result
        waivers = results[0]["waivers"]
        assert len(waivers) == 1
        assert waivers[0]["exemption_ref"] == "PC-001.03"
        assert "gypsum" in waivers[0]["element_name"]

    def test_only_the_wall_material_differs(self, pc001_result):
        # Guards the claim the model rests on: if the two pipes differed in
        # anything else, the verdict split would prove nothing.
        extraction, _ = pc001_result
        elements = _penetrating(extraction)
        assert len(elements) == 2
        assert {e["host_is_breakaway"] for e in elements} == {True, False}
        assert len({e["actual_value"] for e in elements}) == 1
        assert len({tuple(e["scope_values"].items()) for e in elements}) == 1
