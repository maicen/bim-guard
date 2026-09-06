"""Schema-conformance tests for the BCF 2.1 generator.

These tests validate generated archives against the *official* buildingSMART
schemas vendored under ``tests/schemas/bcf21/`` (see the NOTICE there), rather
than asserting on substrings. That distinction matters: the suite that existed
before this module checked only XML well-formedness and substring presence, and
passed happily while every topic violated the schema in six separate ways.

The regression tests below name each of those six violations individually, so a
reintroduction points at the specific rule that broke instead of dumping a wall
of validator output.
"""

import io
import re
import zipfile
from pathlib import Path

import pytest

xmlschema = pytest.importorskip(
    "xmlschema", reason="xmlschema is required for BCF schema validation (dev dependency group)"
)

from app.modules.reporter.bcf_generator import (  # noqa: E402
    BCFIssue,
    bcf_topic_guid,
    generate_bcf,
    is_ifc_guid,
    issues_from_results,
)

SCHEMA_DIR = Path(__file__).parent / "schemas" / "bcf21"

# BCF 2.1 visinfo.xsd IfcGuid: exactly 22 chars from this set. The commas are
# in the upstream pattern verbatim (a known quirk of the published schema).
IFC_GUID_RE = re.compile(r"[0-9,A-Z,a-z,_$]{22}")


@pytest.fixture(scope="module")
def markup_schema():
    """Official buildingSMART BCF 2.1 markup schema."""
    return xmlschema.XMLSchema(SCHEMA_DIR / "markup.xsd")


@pytest.fixture(scope="module")
def visinfo_schema():
    """Official buildingSMART BCF 2.1 visualization-info schema."""
    return xmlschema.XMLSchema(SCHEMA_DIR / "visinfo.xsd")


def create_test_bcf_issue(**overrides) -> BCFIssue:
    """Build one BCFIssue with realistic, schema-legal field values."""
    defaults = dict(
        guid="7A0E74E1-3CC3-46E8-B94E-516D2A12AD47",
        title="[BIMGUARD-AI] HIGH corrosion risk — CHW Supply Pipe",
        description="Galvanic couple between SS 316 and galvanized steel.",
        priority="Major",
        status="Open",
        assigned_to="Lead Engineer",
        due_date="2026-09-15",
        labels=["BIMGUARD-AI", "Risk-HIGH", "interior_conditioned", "Galvanic"],
        component_guid="2O2Fr$t4X7Zf8NOew3FLOH",  # a real 22-char IfcGuid
        component_name="CHW Supply Pipe",
        service_type="Pipework",
        floor="B1 Plant Room",
        risk_band="HIGH",
        mechanism="galvanic",
        risk_score=0.69,
        mitigation="Specify PTFE isolation sleeve at all contact points.",
        camera_x=1.0,
        camera_y=2.0,
        camera_z=3.0,
        target_x=1.0,
        target_y=2.0,
        target_z=3.0,
    )
    defaults.update(overrides)
    return BCFIssue(**defaults)


def _entries(bcf_bytes: bytes, suffix: str) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(bcf_bytes)) as z:
        return [n for n in z.namelist() if n.endswith(suffix)]


def _read(bcf_bytes: bytes, name: str) -> str:
    with zipfile.ZipFile(io.BytesIO(bcf_bytes)) as z:
        return z.read(name).decode("utf-8")


def _errors(schema, xml: str) -> list[str]:
    return [str(e.reason or e) for e in schema.iter_errors(xml)]


# --------------------------------------------------------------------------
# Schema conformance
# --------------------------------------------------------------------------


def test_bcf_markup_xsd_compliant(markup_schema):
    """Validate generated markup.bcf against the buildingSMART 2.1 XSD."""
    bcf_bytes = generate_bcf([create_test_bcf_issue()])
    markup_xml = _read(bcf_bytes, _entries(bcf_bytes, "markup.bcf")[0])

    errors = _errors(markup_schema, markup_xml)
    assert not errors, "markup.bcf schema violations:\n  " + "\n  ".join(errors)


def test_bcf_viewpoint_xsd_compliant(visinfo_schema):
    """Validate generated viewpoint.bcfv against the buildingSMART 2.1 XSD."""
    bcf_bytes = generate_bcf([create_test_bcf_issue()])
    viewpoint_xml = _read(bcf_bytes, _entries(bcf_bytes, "viewpoint.bcfv")[0])

    errors = _errors(visinfo_schema, viewpoint_xml)
    assert not errors, "viewpoint.bcfv schema violations:\n  " + "\n  ".join(errors)


def test_every_topic_in_a_multi_issue_archive_validates(markup_schema, visinfo_schema):
    """Validate all topics, not just the first — folders are generated in a loop."""
    issues = [
        create_test_bcf_issue(guid="11111111-1111-4111-8111-111111111111", labels=[]),
        create_test_bcf_issue(guid="22222222-2222-4222-8222-222222222222", risk_band="CRITICAL"),
        create_test_bcf_issue(guid="33333333-3333-4333-8333-333333333333", due_date=""),
    ]
    bcf_bytes = generate_bcf(issues)

    with zipfile.ZipFile(io.BytesIO(bcf_bytes)) as z:
        for name in z.namelist():
            schema = (
                markup_schema
                if name.endswith("markup.bcf")
                else visinfo_schema
                if name.endswith("viewpoint.bcfv")
                else None
            )
            if schema is None:
                continue
            errors = _errors(schema, z.read(name).decode("utf-8"))
            assert not errors, f"{name} schema violations:\n  " + "\n  ".join(errors)


def test_bcf_from_engine_results_validates(markup_schema):
    """Validate the real production path: engine results → issues → archive."""
    results = [
        {
            "overall_band": "HIGH",
            "name": "CHW Supply Pipe",
            "guid": "2O2Fr$t4X7Zf8NOew3FLOH",
            "description": "Pipework",
            "floor": "B1 Plant Room",
            "material_a": "SS_316_passive",
            "material_b": "Galvanized_steel",
            "environment": "interior_conditioned",
            "galvanic_score": 0.69,
            "crevice_score": 0.5375,
            "overall_score": 0.69,
            "galvanic_band": "HIGH",
            "crevice_band": "MEDIUM",
            "dominant_mechanism": "galvanic",
            "action": "BLOCK",
            "mitigation": "PTFE isolation sleeve",
            "position": (1.0, 2.0, 3.0),
        }
    ]
    issues = issues_from_results(results)
    assert issues, "a HIGH-band result must produce a BCF topic"

    bcf_bytes = generate_bcf(issues)
    for name in _entries(bcf_bytes, "markup.bcf"):
        errors = _errors(markup_schema, _read(bcf_bytes, name))
        assert not errors, f"{name} schema violations:\n  " + "\n  ".join(errors)


# --------------------------------------------------------------------------
# Named regressions — one per violation fixed
# --------------------------------------------------------------------------


def test_labels_are_direct_children_of_topic():
    """Regression 1: no <Labels> wrapper around the <Labels> elements."""
    import xml.etree.ElementTree as ET

    bcf_bytes = generate_bcf([create_test_bcf_issue(labels=["BIMGUARD-AI", "Risk-HIGH"])])
    root = ET.fromstring(_read(bcf_bytes, _entries(bcf_bytes, "markup.bcf")[0]))

    labels = root.find("Topic").findall("Labels")
    assert [label.text for label in labels] == ["BIMGUARD-AI", "Risk-HIGH"]
    for label in labels:
        assert len(label) == 0, "a <Labels> element must not contain child elements"


def test_header_precedes_topic():
    """Regression 2: Markup sequence is Header, Topic, Comment, Viewpoints."""
    import xml.etree.ElementTree as ET

    bcf_bytes = generate_bcf([create_test_bcf_issue()])
    root = ET.fromstring(_read(bcf_bytes, _entries(bcf_bytes, "markup.bcf")[0]))

    assert [child.tag for child in root] == ["Header", "Topic", "Comment", "Viewpoints"]


def test_due_date_precedes_assigned_to():
    """Regression 3: Topic sequence puts DueDate ahead of AssignedTo."""
    import xml.etree.ElementTree as ET

    bcf_bytes = generate_bcf([create_test_bcf_issue()])
    root = ET.fromstring(_read(bcf_bytes, _entries(bcf_bytes, "markup.bcf")[0]))

    tags = [child.tag for child in root.find("Topic")]
    assert tags.index("DueDate") < tags.index("AssignedTo")


def test_empty_due_date_is_omitted_not_malformed():
    """A missing due date must not become the invalid dateTime 'T00:00:00Z'."""
    import xml.etree.ElementTree as ET

    bcf_bytes = generate_bcf([create_test_bcf_issue(due_date="")])
    markup = _read(bcf_bytes, _entries(bcf_bytes, "markup.bcf")[0])

    assert "T00:00:00Z" not in markup
    assert ET.fromstring(markup).find("Topic/DueDate") is None


def test_comment_guid_is_an_attribute():
    """Regression 4: Comment/@Guid is a required attribute, not a child element."""
    import xml.etree.ElementTree as ET

    bcf_bytes = generate_bcf([create_test_bcf_issue()])
    root = ET.fromstring(_read(bcf_bytes, _entries(bcf_bytes, "markup.bcf")[0]))

    comment = root.find("Comment")
    assert comment.get("Guid"), "Comment must carry a Guid attribute"
    assert comment.find("Guid") is None, "Guid must not also appear as a child element"
    assert [child.tag for child in comment] == ["Date", "Author", "Comment"]


def test_visibility_precedes_coloring():
    """Regression 5: Components follows the visinfo.xsd sequence.

    The schema orders it ViewSetupHints, Selection, Visibility, Coloring
    (visinfo.xsd:98-105). ViewSetupHints joined the output when the exporter
    began declaring SpacesVisible="false"; the ordering invariant this test
    exists to protect is unchanged, and Visibility still precedes Coloring.
    """
    import xml.etree.ElementTree as ET

    bcf_bytes = generate_bcf([create_test_bcf_issue()])
    root = ET.fromstring(_read(bcf_bytes, _entries(bcf_bytes, "viewpoint.bcfv")[0]))

    tags = [child.tag for child in root.find("Components")]
    assert tags == ["ViewSetupHints", "Selection", "Visibility", "Coloring"]
    assert tags.index("Visibility") < tags.index("Coloring")


def test_synthetic_element_guids_are_valid_ifc_guids():
    """Regression 6: demo elements must carry real IfcGuids, not sliced UUIDs."""
    from app.modules.ifc_reader.ifc_parser import generate_synthetic_elements

    guids = [element.guid for element in generate_synthetic_elements(10)]
    assert guids
    for guid in guids:
        assert IFC_GUID_RE.fullmatch(guid), f"{guid!r} is not a valid BCF IfcGuid"


def test_synthetic_element_guids_survive_into_a_valid_viewpoint(visinfo_schema):
    """The demo GUID fix must hold end-to-end, not just at the parser."""
    from app.modules.ifc_reader.ifc_parser import generate_synthetic_elements

    element = generate_synthetic_elements(1)[0]
    bcf_bytes = generate_bcf([create_test_bcf_issue(component_guid=element.guid)])

    errors = _errors(visinfo_schema, _read(bcf_bytes, _entries(bcf_bytes, "viewpoint.bcfv")[0]))
    assert not errors, "viewpoint.bcfv schema violations:\n  " + "\n  ".join(errors)


# --------------------------------------------------------------------------
# Named regressions — GUID typing (violations 7–10)
#
# markup.xsd types Topic/@Guid as a hyphenated UUID, and File/@IfcProject and
# Component/@IfcGuid as 22-character IFC GlobalIds. Production callers hand the
# generator ISO 19650 project codes, blank or UUID-shaped element ids and
# "BGR-0007" finding ids, none of which satisfy those facets.
# --------------------------------------------------------------------------

BCF_GUID_RE = re.compile(
    r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
)


def test_iso19650_project_code_is_not_written_as_ifcproject(markup_schema):
    """Regression 7: File/@IfcProject is an IfcGuid, not a project code."""
    import xml.etree.ElementTree as ET

    issue = create_test_bcf_issue(
        project_code="PRJ1", originator="BIMG", suitability_code="S1", cde_state="WIP"
    )
    bcf_bytes = generate_bcf([issue])
    markup = _read(bcf_bytes, _entries(bcf_bytes, "markup.bcf")[0])

    errors = _errors(markup_schema, markup)
    assert not errors, "markup.bcf schema violations:\n  " + "\n  ".join(errors)
    assert ET.fromstring(markup).find("./Header/File").get("IfcProject") is None
    # The ISO 19650 container identity is still delivered to the reviewer.
    assert "ISO 19650 Container: PRJ1-BIMG" in markup
    assert "<Labels>Suitability:S1</Labels>" in markup


def test_real_ifcproject_guid_is_written_as_ifcproject(markup_schema):
    import xml.etree.ElementTree as ET

    bcf_bytes = generate_bcf([create_test_bcf_issue(project_code="0YvctVUKr0kugbFTf53O9L")])
    markup = _read(bcf_bytes, _entries(bcf_bytes, "markup.bcf")[0])

    assert not _errors(markup_schema, markup)
    header_file = ET.fromstring(markup).find("./Header/File")
    assert header_file.get("IfcProject") == "0YvctVUKr0kugbFTf53O9L"


@pytest.mark.parametrize(
    "bad_guid",
    ["", "7A0E74E1-3CC3-46E8-B94E-516D2A12AD47", "COMP-001", "{2O2Fr$t4X7Zf8NOew3FLOH}"],
    ids=["blank", "uuid", "label", "braced"],
)
def test_non_ifc_component_guid_is_dropped_from_ifcguid_attribute(visinfo_schema, bad_guid):
    """Regression 8: Component/@IfcGuid is omitted rather than written malformed."""
    import xml.etree.ElementTree as ET

    bcf_bytes = generate_bcf([create_test_bcf_issue(component_guid=bad_guid)])
    viewpoint = _read(bcf_bytes, _entries(bcf_bytes, "viewpoint.bcfv")[0])

    errors = _errors(visinfo_schema, viewpoint)
    assert not errors, "viewpoint.bcfv schema violations:\n  " + "\n  ".join(errors)

    root = ET.fromstring(viewpoint)
    components = list(root.iter("Component"))
    assert components, "the selection and colouring components must still be emitted"
    assert all(c.get("IfcGuid") is None for c in components)
    # The raw id is preserved for the reader in AuthoringToolId.
    tool_id = root.find("./Components/Selection/Component/AuthoringToolId").text
    assert tool_id == (bad_guid or None)


def test_valid_ifc_component_guid_is_kept():
    import xml.etree.ElementTree as ET

    bcf_bytes = generate_bcf([create_test_bcf_issue(component_guid="2O2Fr$t4X7Zf8NOew3FLOH")])
    root = ET.fromstring(_read(bcf_bytes, _entries(bcf_bytes, "viewpoint.bcfv")[0]))
    guids = {c.get("IfcGuid") for c in root.iter("Component")}
    assert guids == {"2O2Fr$t4X7Zf8NOew3FLOH"}


def test_engine_result_without_guid_still_validates(visinfo_schema):
    """issues_from_results used to invent a random UUID as the IfcGuid."""
    issues = issues_from_results([{"overall_band": "HIGH", "name": "Riser"}])
    assert issues[0].component_guid == ""

    bcf_bytes = generate_bcf(issues)
    errors = _errors(visinfo_schema, _read(bcf_bytes, _entries(bcf_bytes, "viewpoint.bcfv")[0]))
    assert not errors, "viewpoint.bcfv schema violations:\n  " + "\n  ".join(errors)


def test_non_uuid_issue_id_maps_to_a_stable_topic_guid_and_folder(markup_schema):
    """Regression 9: a "BGR-0007" finding id becomes a deterministic UUID5 topic."""
    import xml.etree.ElementTree as ET

    first = generate_bcf([create_test_bcf_issue(guid="BGR-0007")])
    second = generate_bcf([create_test_bcf_issue(guid="BGR-0007")])

    folders = {n.split("/")[0] for n in _entries(first, "markup.bcf")}
    assert folders == {bcf_topic_guid("BGR-0007")}
    assert folders == {n.split("/")[0] for n in _entries(second, "markup.bcf")}, (
        "the same finding must export to the same topic GUID every time"
    )

    markup = _read(first, _entries(first, "markup.bcf")[0])
    errors = _errors(markup_schema, markup)
    assert not errors, "markup.bcf schema violations:\n  " + "\n  ".join(errors)

    root = ET.fromstring(markup)
    topic_guid = root.find("Topic").get("Guid")
    assert BCF_GUID_RE.match(topic_guid)
    assert topic_guid == bcf_topic_guid("BGR-0007")
    assert "Source finding id: BGR-0007" in root.find("./Comment/Comment").text


def test_uuid_issue_ids_pass_through_unchanged():
    """Regression 10: a real UUID keeps its identity verbatim (only braces are stripped).

    Case is preserved on purpose: the pipeline mints lower-case UUID5 topic
    ids and the BCF sync service compares them as strings.
    """
    canonical = "7A0E74E1-3CC3-46E8-B94E-516D2A12AD47"
    assert bcf_topic_guid(canonical) == canonical
    assert bcf_topic_guid(canonical.lower()) == canonical.lower()
    assert bcf_topic_guid("{" + canonical + "}") == canonical
    assert bcf_topic_guid("BGR-0007") == bcf_topic_guid("BGR-0007")
    assert bcf_topic_guid("BGR-0007") != bcf_topic_guid("BGR-0008")
    assert bcf_topic_guid("") != bcf_topic_guid(""), "blank ids must not collapse into one topic"


def test_is_ifc_guid_matches_the_schema_facets():
    assert is_ifc_guid("2O2Fr$t4X7Zf8NOew3FLOH")
    assert not is_ifc_guid("")
    assert not is_ifc_guid("2O2Fr$t4X7Zf8NOew3FLO")  # 21 chars
    assert not is_ifc_guid("7A0E74E1-3CC3-46E8-B94E-516D2A12AD47")
    assert not is_ifc_guid("{2O2Fr$t4X7Zf8NOew3FLOH}")


def test_related_component_guids_are_selected_and_coloured(visinfo_schema):
    """A galvanic couple selects both the anode (primary) and the cathode."""
    import xml.etree.ElementTree as ET

    issue = create_test_bcf_issue(
        component_guid="2O2Fr$t4X7Zf8NOew3FLOH",
        related_component_guids=["0FQ6pMwzXBJucYaRTqfuw2", "2O2Fr$t4X7Zf8NOew3FLOH", "", "GC-VAL-001B"],
    )
    bcf_bytes = generate_bcf([issue])
    viewpoint = _read(bcf_bytes, _entries(bcf_bytes, "viewpoint.bcfv")[0])

    errors = _errors(visinfo_schema, viewpoint)
    assert not errors, "viewpoint.bcfv schema violations:\n  " + "\n  ".join(errors)

    root = ET.fromstring(viewpoint)
    selection = root.findall("./Components/Selection/Component")
    coloured = root.findall("./Components/Coloring/Color/Component")
    # Duplicates and blanks collapse; the label keeps a Component but no IfcGuid.
    assert [c.get("IfcGuid") for c in selection] == [
        "2O2Fr$t4X7Zf8NOew3FLOH",
        "0FQ6pMwzXBJucYaRTqfuw2",
        None,
    ]
    assert [c.find("AuthoringToolId").text for c in selection] == [
        "2O2Fr$t4X7Zf8NOew3FLOH",
        "0FQ6pMwzXBJucYaRTqfuw2",
        "GC-VAL-001B",
    ]
    assert [c.get("IfcGuid") for c in coloured] == [c.get("IfcGuid") for c in selection]

    markup = _read(bcf_bytes, _entries(bcf_bytes, "markup.bcf")[0])
    assert "Related components: 0FQ6pMwzXBJucYaRTqfuw2, GC-VAL-001B" in markup


# --------------------------------------------------------------------------
# Archive structure
# --------------------------------------------------------------------------


def test_archive_has_required_root_files():
    """A BCF-ZIP needs bcf.version and one folder per topic."""
    issue = create_test_bcf_issue()
    bcf_bytes = generate_bcf([issue])

    with zipfile.ZipFile(io.BytesIO(bcf_bytes)) as z:
        names = z.namelist()

    assert "bcf.version" in names
    assert "project.bcfp" in names
    assert f"{issue.guid}/markup.bcf" in names
    assert f"{issue.guid}/viewpoint.bcfv" in names
    assert f"{issue.guid}/snapshot.png" in names


def test_snapshot_is_a_valid_png():
    """The snapshot placeholder must at least be a decodable PNG."""
    bcf_bytes = generate_bcf([create_test_bcf_issue()])
    with zipfile.ZipFile(io.BytesIO(bcf_bytes)) as z:
        blob = z.read(_entries(bcf_bytes, "snapshot.png")[0])

    assert blob.startswith(b"\x89PNG\r\n\x1a\n")


def test_xml_special_characters_are_escaped(markup_schema):
    """Ampersands and angle brackets in issue text must not break the document."""
    issue = create_test_bcf_issue(
        title="Pipe A & B <clash>",
        description='Materials "SS316" & <galvanized> steel',
        component_name="A & B",
    )
    bcf_bytes = generate_bcf([issue])
    markup_xml = _read(bcf_bytes, _entries(bcf_bytes, "markup.bcf")[0])

    errors = _errors(markup_schema, markup_xml)
    assert not errors, "markup.bcf schema violations:\n  " + "\n  ".join(errors)
    assert "Pipe A &amp; B &lt;clash&gt;" in markup_xml
