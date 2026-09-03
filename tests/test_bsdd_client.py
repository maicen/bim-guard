"""Tests for buildingSMART Data Dictionary (bSDD) Client & Semantic Validation."""

from app.modules.comparator.compliance_runner import run_bsdd_semantic_verification
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


def test_bsdd_list_dictionaries_parses_live_v1_response_shape():
    """Verify a wrapped, real-schema Dictionary/v1 response parses correctly.

    GET /api/Dictionary/v1 wraps the list in {"dictionaries": [...]} with
    dictionaryCode/dictionaryName/dictionaryVersion/classCount fields -- not
    the bare-array, code/name/version/classesCount shape this client used to
    assume. See DictionaryResponseContract.v1 in buildingSMART/bSDD's OpenAPI spec.
    """
    client = BSDDClient(enable_network=False)
    client._http_get = lambda *a, **k: {
        "totalCount": 1,
        "offset": 0,
        "count": 1,
        "dictionaries": [
            {
                "uri": "https://identifier.buildingsmart.org/uri/bs-ag/uniclass-2015",
                "organizationCodeOwner": "NBS",
                "dictionaryCode": "uniclass_2015",
                "dictionaryVersion": "2024.1",
                "dictionaryName": "Uniclass 2015 Classification System",
                "languageIsoCode": "en-GB",
                "classCount": 5,
            }
        ],
    }
    dicts = client.list_dictionaries()
    assert len(dicts) == 1
    assert dicts[0].code == "uniclass_2015"
    assert dicts[0].name == "Uniclass 2015 Classification System"
    assert dicts[0].version == "2024.1"
    assert dicts[0].classes_count == 5


def test_bsdd_get_class_parses_live_v1_response_shape():
    """Verify a real-schema Class/v1 response parses correctly.

    GET /api/Class/v1 takes a full `Uri`, and nests properties under
    `classProperties` (ClassPropertyContract.v1: propertyUri/name/propertySet/
    dataType/units[]/allowedValues[{value}]) -- not the flat `properties`
    shape with a bare uri/units string this client used to assume.
    """
    client = BSDDClient(enable_network=False)
    calls = []

    def fake_get(endpoint, params=None):
        calls.append((endpoint, params))
        return {
            "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/class/IfcPipeSegment",
            "code": "IfcPipeSegment",
            "name": "Pipe Segment",
            "dictionaryUri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3",
            "classProperties": [
                {
                    "propertyUri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/prop/Material",
                    "name": "Material",
                    "propertySet": "Pset_PipeSegmentCommon",
                    "dataType": "IfcLabel",
                    "units": ["mm"],
                    "allowedValues": [{"value": "Copper"}, {"value": "PVC"}],
                    "description": "Material classification.",
                }
            ],
        }

    client._http_get = fake_get
    result = client.get_class(
        "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3", "IfcPipeSegment"
    )
    assert result is not None
    assert result.code == "IfcPipeSegment"
    assert len(result.properties) == 1
    prop = result.properties[0]
    assert prop.name == "Material"
    assert prop.property_set == "Pset_PipeSegmentCommon"
    assert prop.units == "mm"
    assert prop.allowed_values == ["Copper", "PVC"]

    # Looked up by full Uri (there is no separate dictionaryUri+code param).
    endpoint, params = calls[0]
    assert endpoint == "/api/Class/v1"
    assert params["Uri"].endswith("/class/IfcPipeSegment")


def test_bsdd_search_classes_parses_live_v2_response_shape():
    """GET /api/TextSearch/v2 (v1 is retired) takes SearchText/DictionaryUris."""
    client = BSDDClient(enable_network=False)
    calls = []

    def fake_get(endpoint, params=None):
        calls.append((endpoint, params))
        return {
            "classes": [
                {
                    "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/class/IfcPipeSegment",
                    "code": "IfcPipeSegment",
                    "name": "Pipe Segment",
                    "dictionaryUri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3",
                }
            ],
            "properties": [],
        }

    client._http_get = fake_get
    result = client.search_classes("pipe")
    assert result.total == 1
    assert result.classes[0].code == "IfcPipeSegment"

    endpoint, params = calls[0]
    assert endpoint == "/api/TextSearch/v2"
    assert params["SearchText"] == "pipe"


def test_bsdd_search_properties():
    client = BSDDClient(enable_network=False)
    props = client.search_properties("Material")
    assert len(props) >= 1
    assert all("material" in p.name.lower() or "material" in (p.description or "").lower() for p in props)


def test_bsdd_search_properties_empty_query_returns_nothing():
    client = BSDDClient(enable_network=False)
    assert client.search_properties("   ") == []


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
