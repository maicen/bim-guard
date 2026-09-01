"""Tests for the BCF 2.1 archive path of ``app.services.bcf_exporter``.

Covers the ``.bcfzip`` structure, multi-element viewpoint selection and the
``docs/bcf_exports`` output routing. The flat-markup format retains its own
coverage in ``tests/test_bcf_exporter.py``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile

import pytest

from app.modules.module4_comparator.issue_schema import Issue, RiskBand
from app.services.bcf_exporter import DEFAULT_EXPORT_DIR, BCFExporter, ElementRef


def galvanic_issue() -> Issue:
    """Build a GC-001 copper / carbon steel couple implicating three elements."""
    return Issue(
        id="BGR-0001",
        element_id="0FQ6pMwzXBJucYaRTqfuw2",
        rule_id="GC-001.02",
        title="Copper / carbon steel galvanic couple",
        band=RiskBand.CRITICAL,
        score=0.91,
        mechanism="GC-001 galvanic",
        mitigation="Install dielectric isolation gasket.",
        assignee_role="Mechanical Engineer",
        metadata={
            "anode_guid": "1AbcDEF2GhIjKlMnOpQrSt",
            "cathode_guid": "2XyZ98WvUtSrQpOnMlKjIh",
            "voltage_v": 0.78,
            "suitability_code": "S2",
            "cde_state": "SHARED",
        },
        citations=[{"standard": "ISO 9223", "clause": "Table 3"}],
    )


def crevice_issue() -> Issue:
    """Build a CC-001 finding carrying one related element via the generic list key."""
    return Issue(
        id="BGR-0002",
        element_id="3MnOpQrStUvWxYz01AbCd",
        rule_id="CC-001.07",
        title="Crevice at flange joint",
        band=RiskBand.HIGH,
        score=0.68,
        mechanism="CC-001 crevice",
        metadata={"related_element_ids": ["4EfGhIjKlMnOpQrStUvWx"], "joint_type": "JT-004"},
    )


@pytest.fixture
def archive(tmp_path) -> zipfile.ZipFile:
    """Write an archive containing both sample findings and open it."""
    path = BCFExporter(export_dir=tmp_path).export(
        [galvanic_issue(), crevice_issue()], "findings"
    )
    with zipfile.ZipFile(path) as zf:
        yield zf


class TestElementCollection:
    """``collect_elements`` resolves every implicated IFC GUID."""

    def test_primary_element_comes_first(self):
        elements = BCFExporter.collect_elements(galvanic_issue())
        assert elements[0] == ElementRef("0FQ6pMwzXBJucYaRTqfuw2", "primary")

    def test_anode_and_cathode_are_resolved_with_roles(self):
        roles = {e.ifc_guid: e.role for e in BCFExporter.collect_elements(galvanic_issue())}
        assert roles["1AbcDEF2GhIjKlMnOpQrSt"] == "anode"
        assert roles["2XyZ98WvUtSrQpOnMlKjIh"] == "cathode"

    def test_list_valued_key_is_expanded(self):
        guids = [e.ifc_guid for e in BCFExporter.collect_elements(crevice_issue())]
        assert guids == ["3MnOpQrStUvWxYz01AbCd", "4EfGhIjKlMnOpQrStUvWx"]

    def test_duplicate_guids_are_collapsed(self):
        issue = galvanic_issue()
        issue.metadata["anode_guid"] = issue.element_id
        guids = [e.ifc_guid for e in BCFExporter.collect_elements(issue)]
        assert len(guids) == len(set(guids))

    def test_issue_without_metadata_yields_only_primary(self):
        issue = crevice_issue()
        issue.metadata = {}
        assert len(BCFExporter.collect_elements(issue)) == 1


class TestArchiveStructure:
    """The archive matches the BCF 2.1 on-disk layout."""

    def test_contains_version_and_project_descriptors(self, archive):
        names = archive.namelist()
        assert "bcf.version" in names
        assert "project.bcfp" in names

    def test_one_folder_per_topic(self, archive):
        for topic_id in ("BGR-0001", "BGR-0002"):
            for part in ("markup.bcf", "viewpoint.bcfv", "snapshot.png"):
                assert f"{topic_id}/{part}" in archive.namelist()

    def test_every_xml_part_is_well_formed(self, archive):
        for name in archive.namelist():
            if name.endswith((".bcf", ".bcfv", ".bcfp", ".version")):
                ET.fromstring(archive.read(name).decode("utf-8"))

    def test_snapshot_is_a_valid_png(self, archive):
        assert archive.read("BGR-0001/snapshot.png").startswith(b"\x89PNG\r\n\x1a\n")

    def test_version_is_declared_as_2_1(self, archive):
        assert ET.fromstring(archive.read("bcf.version").decode()).get("VersionId") == "2.1"


class TestViewpoint:
    """The viewpoint selects and colours every implicated element."""

    def _components(self, archive, topic_id: str, parent: str) -> list[str]:
        root = ET.fromstring(archive.read(f"{topic_id}/viewpoint.bcfv").decode())
        node = root.find(f"./Components/{parent}")
        return [c.get("IfcGuid") for c in node.iter("Component")]

    def test_all_three_galvanic_elements_are_selected(self, archive):
        assert set(self._components(archive, "BGR-0001", "Selection")) == {
            "0FQ6pMwzXBJucYaRTqfuw2",
            "1AbcDEF2GhIjKlMnOpQrSt",
            "2XyZ98WvUtSrQpOnMlKjIh",
        }

    def test_all_selected_elements_are_coloured(self, archive):
        assert set(self._components(archive, "BGR-0001", "Coloring")) == set(
            self._components(archive, "BGR-0001", "Selection")
        )

    def test_colour_reflects_risk_band(self, archive):
        root = ET.fromstring(archive.read("BGR-0001/viewpoint.bcfv").decode())
        assert root.find("./Components/Coloring/Color").get("Color") == "FFC00000"

    def test_components_children_follow_schema_order(self, archive):
        root = ET.fromstring(archive.read("BGR-0002/viewpoint.bcfv").decode())
        order = [child.tag for child in root.find("./Components")]
        assert order == ["ViewSetupHints", "Selection", "Visibility", "Coloring"]

    def test_camera_is_present(self, archive):
        root = ET.fromstring(archive.read("BGR-0001/viewpoint.bcfv").decode())
        assert root.find("./PerspectiveCamera/CameraViewPoint/X") is not None


class TestMarkup:
    """Per-topic markup carries the audit trail reviewers need."""

    def _topic(self, archive, topic_id: str) -> ET.Element:
        root = ET.fromstring(archive.read(f"{topic_id}/markup.bcf").decode())
        return root.find("Topic")

    def test_topic_guid_matches_issue_id(self, archive):
        assert self._topic(archive, "BGR-0001").get("Guid") == "BGR-0001"

    def test_priority_maps_from_risk_band(self, archive):
        assert self._topic(archive, "BGR-0001").find("Priority").text == "Critical"
        assert self._topic(archive, "BGR-0002").find("Priority").text == "High"

    def test_iso_19650_governance_labels_are_emitted(self, archive):
        labels = {el.text for el in self._topic(archive, "BGR-0001").findall("Labels")}
        assert "Suitability:S2" in labels
        assert "CDE:SHARED" in labels

    def test_description_lists_related_elements(self, archive):
        description = self._topic(archive, "BGR-0001").find("Description").text
        assert "1AbcDEF2GhIjKlMnOpQrSt (anode)" in description

    def test_markup_links_its_viewpoint_and_snapshot(self, archive):
        root = ET.fromstring(archive.read("BGR-0001/markup.bcf").decode())
        viewpoints = root.find("Viewpoints")
        assert viewpoints.find("Viewpoint").text == "viewpoint.bcfv"
        assert viewpoints.find("Snapshot").text == "snapshot.png"

    def test_citations_reach_the_comment_body(self, archive):
        root = ET.fromstring(archive.read("BGR-0001/markup.bcf").decode())
        assert "ISO 9223" in root.find("./Comment/Comment").text


class TestOutputRouting:
    """Archives land where the caller asked for them."""

    def test_default_export_dir_is_docs_bcf_exports(self):
        assert DEFAULT_EXPORT_DIR.as_posix().endswith("docs/bcf_exports")

    def test_bcfzip_suffix_is_appended(self, tmp_path):
        assert BCFExporter(export_dir=tmp_path).export([crevice_issue()], "review").name == (
            "review.bcfzip"
        )

    def test_generated_name_is_used_when_omitted(self, tmp_path):
        path = BCFExporter(export_dir=tmp_path).export([crevice_issue()])
        assert path.name.startswith("bimguard_findings_")
        assert path.suffix == ".bcfzip"

    def test_export_dir_is_created_on_demand(self, tmp_path):
        target = tmp_path / "nested" / "dir"
        assert BCFExporter(export_dir=target).export([crevice_issue()], "x").exists()

    def test_generate_bcf_zip_writes_a_real_archive(self, tmp_path):
        out = tmp_path / "legacy.bcfzip"
        BCFExporter().generate_bcf_zip([crevice_issue()], str(out))
        assert zipfile.is_zipfile(out)

    def test_empty_issue_list_still_yields_a_valid_archive(self, tmp_path):
        path = BCFExporter(export_dir=tmp_path).export([], "empty")
        with zipfile.ZipFile(path) as zf:
            assert zf.namelist() == ["bcf.version", "project.bcfp"]
