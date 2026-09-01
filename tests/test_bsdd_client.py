"""Tests for buildingSMART Data Dictionary (bSDD) Client & Semantic Validation."""

from app.modules.module4_comparator.compliance_runner import run_bsdd_semantic_verification
from app.services.bsdd_client import BSDDClient


def test_bsdd_list_dictionaries_fallback():
    client = BSDDClient(enable_network=False)
    dicts = client.list_dictionaries()
    assert len(dicts) >= 3
    codes = {d.code for d in dicts}
    assert "ifc_4.3" in codes
    assert "uniclass_2015" in codes
    assert "omniclass_2020" in codes


def test_bsdd_get_class_and_properties():
    client = BSDDClient(enable_network=False)
    pipe_class = client.get_class("https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3", "IfcPipeSegment")
    assert pipe_class is not None
    assert pipe_class.code == "IfcPipeSegment"
    assert len(pipe_class.properties) >= 3

    prop_names = {p.name for p in pipe_class.properties}
    assert "NominalDiameter" in prop_names
    assert "CorrosionAllowance" in prop_names
    assert "Material" in prop_names

    material_prop = next(p for p in pipe_class.properties if p.name == "Material")
    assert "Stainless Steel 316" in material_prop.allowed_values


def test_bsdd_search_classes():
    client = BSDDClient(enable_network=False)
    res = client.search_classes("pipe")
    assert res.total >= 1
    codes = [c.code for c in res.classes]
    assert any("Pipe" in c or "65" in c for c in codes)


def test_bsdd_validate_element_semantics_compliant():
    client = BSDDClient(enable_network=False)
    element = {
        "GlobalId": "2O2Fr$t4X7Zf8NOew3FLOH",
        "element_type": "IfcPipeSegment",
        "NominalDiameter": 100.0,
        "CorrosionAllowance": 3.0,
        "Material": "Stainless Steel 316",
        "PressureRating": "PN16",
    }
    result = client.validate_element_semantics(element)
    assert result.passed is True
    assert result.compliance_score_pct == 100.0
    assert len(result.violations) == 0


def test_bsdd_validate_element_semantics_invalid_material_enumeration():
    client = BSDDClient(enable_network=False)
    element = {
        "GlobalId": "2O2Fr$t4X7Zf8NOew3FLOH",
        "element_type": "IfcPipeSegment",
        "NominalDiameter": 100.0,
        "CorrosionAllowance": 3.0,
        "Material": "Unobtanium_Super_Alloy_999",  # Invalid material enumeration
        "PressureRating": "PN16",
    }
    result = client.validate_element_semantics(element)
    assert result.passed is False
    assert any("violates bSDD allowed enumeration" in v.message for v in result.violations)


def test_bsdd_validate_element_missing_properties():
    client = BSDDClient(enable_network=False)
    element = {
        "GlobalId": "2O2Fr$t4X7Zf8NOew3FLOH",
        "element_type": "IfcPipeSegment",
        # Missing required bSDD properties
    }
    result = client.validate_element_semantics(element)
    assert result.passed is True  # missing property is warning, not fatal error
    assert result.violations_count > 0
    assert any(v.severity == "warning" for v in result.violations)


def test_run_bsdd_semantic_verification_runner():
    elements = [
        {
            "GlobalId": "2O2Fr$t4X7Zf8NOew3FL01",
            "element_type": "IfcPipeSegment",
            "NominalDiameter": 50.0,
            "Material": "Copper",
            "PressureRating": "PN10",
        },
        {
            "GlobalId": "2O2Fr$t4X7Zf8NOew3FL02",
            "element_type": "IfcValve",
            "ValveType": "BALL",
            "Material": "Bronze",
        },
    ]
    report = run_bsdd_semantic_verification(elements, bsdd_client=BSDDClient(enable_network=False))
    assert report["total_elements_checked"] == 2
    assert report["passed"] is True
    assert report["compliance_percent"] > 0
