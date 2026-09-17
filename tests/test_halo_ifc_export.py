"""The SB-001 clearance-zone IFC export must be a file another tool can open.

The zones are BIMGUARD's assertion about space, delivered as geometry so a
coordinator can load them beside the federated model. That promise only holds
if the file parses, carries the boxes where the findings said, and keeps the
property set the rest of the Blue Halo path writes. So these tests do not
inspect the exporter's internals: they write the file, open it again with
ifcopenshell, and read back what a receiving tool would read.

Run: uv run pytest tests/test_halo_ifc_export.py -v
"""

from __future__ import annotations

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell", reason="the IFC export needs ifcopenshell")

from app.modules.blue_halo.halo_volume_generator import (  # noqa: E402
    PSET_HALO_RESERVATION,
    SCHEMA_VERSION,
)
from app.modules.phase_6 import phase_6e_export  # noqa: E402
from app.modules.reporter.halo_ifc_exporter import (  # noqa: E402
    PSET_HALO_FINDING,
    build_clearance_zone_ifc,
    count_clearance_zones,
    issue_has_clearance_zone,
)


def _finding(
    issue_id: str,
    element_id: str,
    *,
    lo: tuple[float, float, float],
    hi: tuple[float, float, float],
    band: str = "critical",
    clashing: str = "2BEAM000000000000000000",
) -> dict:
    """One SB-001 finding shaped as phase_6d_seismic writes it."""
    return {
        "id": issue_id,
        "element_id": element_id,
        "rule_id": "SB-001.02",
        "band": band,
        "metadata": {
            "mechanism_code": "SB-001",
            "halo_id": f"halo-{issue_id}",
            "clashing_element_id": clashing,
            "clashing_element_class": "IfcBeam",
            "overlap_volume_mm3": 125000.0,
            "clearance_mm": 200.0,
            "brace_type": "cable",
            "rule_variant": "cable",
            "source_ifc_class": "IfcPipeSegment",
            "source_model": "Services.ifc",
            "clashing_source_model": "Structure.ifc",
            "halo_generated_at": "2026-09-16T10:00:00+00:00",
            "halo_bbox": {
                "min_mm": list(lo),
                "max_mm": list(hi),
                "size_mm": [hi[i] - lo[i] for i in range(3)],
            },
            "element_bbox": {
                "min_mm": [lo[0] + 200, lo[1] + 200, lo[2] + 200],
                "max_mm": [hi[0] - 200, hi[1] - 200, hi[2] - 200],
            },
        },
    }


#: Two zones with different boxes, plus a data-quality note that has none.
FINDINGS = [
    _finding("SB-0001", "1PIPE00000000000000000", lo=(0.0, 0.0, 2500.0), hi=(2000.0, 400.0, 2900.0)),
    _finding(
        "SB-0002",
        "3DUCT00000000000000000",
        lo=(5000.0, 1000.0, 3000.0),
        hi=(6000.0, 1600.0, 3600.0),
        band="medium",
    ),
    {
        "id": "SB-0003",
        "element_id": "4NOGEOM0000000000000000",
        "rule_id": "SB-001.01",
        "band": "low",
        "metadata": {"mechanism_code": "SB-001", "check": "geometry_unavailable"},
    },
]


def _open(data: bytes, tmp_path):
    """Write the bytes out and open them as a receiving tool would."""
    path = tmp_path / "zones.ifc"
    path.write_bytes(data)
    return ifcopenshell.open(str(path))


@pytest.fixture(scope="module")
def exported() -> bytes:
    return build_clearance_zone_ifc(FINDINGS, project_name="Test project")


def test_only_findings_with_geometry_become_zones():
    """A finding with no envelope is skipped, not guessed at."""
    assert issue_has_clearance_zone(FINDINGS[0]) is True
    assert issue_has_clearance_zone(FINDINGS[2]) is False
    assert count_clearance_zones(FINDINGS) == 2


def test_a_degenerate_box_is_not_exported():
    """A zero-extent envelope cannot be extruded, so it is not written."""
    flat = _finding("SB-0004", "5FLAT0000000000000000", lo=(0.0, 0.0, 0.0), hi=(0.0, 500.0, 500.0))
    assert issue_has_clearance_zone(flat) is False


def test_the_file_parses_and_is_ifc4(exported, tmp_path):
    """The round trip: what we wrote, ifcopenshell opens."""
    model = _open(exported, tmp_path)
    assert model.schema == "IFC4"


def test_one_proxy_per_finding_with_geometry(exported, tmp_path):
    model = _open(exported, tmp_path)
    proxies = model.by_type("IfcBuildingElementProxy")
    assert len(proxies) == 2
    tags = sorted(p.Tag for p in proxies)
    assert tags == ["SB-0001", "SB-0002"]


def test_a_zone_is_named_for_its_rule_band_and_counterpart(exported, tmp_path):
    model = _open(exported, tmp_path)
    names = sorted(p.Name for p in model.by_type("IfcBuildingElementProxy"))
    assert names[0] == "Seismic clearance zone [SB-001.02] CRITICAL vs 2BEAM000000000000000000"
    assert "MEDIUM" in names[1]
    descriptions = [p.Description or "" for p in model.by_type("IfcBuildingElementProxy")]
    assert all("not a bracing design" in text for text in descriptions)


def test_the_box_is_the_size_and_place_the_finding_said(exported, tmp_path):
    """Geometry in metres, matching the millimetre bbox it came from."""
    model = _open(exported, tmp_path)
    proxy = next(p for p in model.by_type("IfcBuildingElementProxy") if p.Tag == "SB-0001")

    representation = proxy.Representation.Representations[0]
    assert representation.RepresentationIdentifier == "Body"
    assert representation.RepresentationType == "SweptSolid"

    solid = representation.Items[0]
    assert solid.is_a("IfcExtrudedAreaSolid")
    # 2000 x 400 x 400 mm
    assert solid.SweptArea.XDim == pytest.approx(2.0)
    assert solid.SweptArea.YDim == pytest.approx(0.4)
    assert solid.Depth == pytest.approx(0.4)

    # The profile is centred, so the placement sits at the box centre in x/y
    # and at its base in z: (1000, 200, 2500) mm.
    location = proxy.ObjectPlacement.RelativePlacement.Location.Coordinates
    assert location == pytest.approx((1.0, 0.2, 2.5))


def test_every_zone_carries_pset_halo_reservation(exported, tmp_path):
    """The property set the BCF path writes, with the same names and values."""
    model = _open(exported, tmp_path)
    proxy = next(p for p in model.by_type("IfcBuildingElementProxy") if p.Tag == "SB-0001")
    psets = {
        rel.RelatingPropertyDefinition.Name: rel.RelatingPropertyDefinition
        for rel in proxy.IsDefinedBy
    }
    assert PSET_HALO_RESERVATION in psets
    assert PSET_HALO_FINDING in psets

    values = _properties(psets[PSET_HALO_RESERVATION])
    assert values["SchemaVersion"] == SCHEMA_VERSION
    assert values["SourceElementGlobalId"] == "1PIPE00000000000000000"
    assert values["SourceIfcClass"] == "IfcPipeSegment"
    assert values["BraceType"] == "cable"
    assert values["ClearanceMm"] == pytest.approx(200.0)
    assert values["HaloBBoxMinMm"] == pytest.approx([0.0, 0.0, 2500.0])
    assert values["HaloBBoxMaxMm"] == pytest.approx([2000.0, 400.0, 2900.0])
    assert values["ElementBBoxMinMm"] == pytest.approx([200.0, 200.0, 2700.0])
    # 2000 x 400 x 400 mm
    assert values["HaloVolumeMm3"] == pytest.approx(320_000_000.0)
    assert values["GeneratedAt"] == "2026-09-16T10:00:00+00:00"


def test_finding_context_rides_in_its_own_pset(exported, tmp_path):
    """Rule, band and counterpart, kept out of the shared reservation pset."""
    model = _open(exported, tmp_path)
    proxy = next(p for p in model.by_type("IfcBuildingElementProxy") if p.Tag == "SB-0001")
    pset = next(
        rel.RelatingPropertyDefinition
        for rel in proxy.IsDefinedBy
        if rel.RelatingPropertyDefinition.Name == PSET_HALO_FINDING
    )
    values = _properties(pset)
    assert values["RuleId"] == "SB-001.02"
    assert values["RiskBand"] == "critical"
    assert values["ClashingElementGlobalId"] == "2BEAM000000000000000000"
    assert values["ClashingElementIfcClass"] == "IfcBeam"
    assert values["OverlapVolumeMm3"] == pytest.approx(125000.0)
    assert values["SourceModel"] == "Services.ifc"


def test_millimetre_properties_are_not_typed_as_lengths(exported, tmp_path):
    """A length measure would be read in the project unit -- metres -- not mm."""
    model = _open(exported, tmp_path)
    proxy = model.by_type("IfcBuildingElementProxy")[0]
    pset = next(
        rel.RelatingPropertyDefinition
        for rel in proxy.IsDefinedBy
        if rel.RelatingPropertyDefinition.Name == PSET_HALO_RESERVATION
    )
    clearance = next(p for p in pset.HasProperties if p.Name == "ClearanceMm")
    assert clearance.NominalValue.is_a() == "IfcReal"


def test_zones_sit_in_a_spatial_container(exported, tmp_path):
    """A product outside the spatial tree is invalid IFC4 and some viewers hide it."""
    model = _open(exported, tmp_path)
    storeys = model.by_type("IfcBuildingStorey")
    assert len(storeys) == 1
    contained = [
        product
        for rel in model.by_type("IfcRelContainedInSpatialStructure")
        for product in rel.RelatedElements
    ]
    assert len(contained) == 2
    assert {p.is_a() for p in contained} == {"IfcBuildingElementProxy"}
    assert model.by_type("IfcProject") and model.by_type("IfcSite") and model.by_type("IfcBuilding")


def test_the_model_is_metric_and_says_who_made_it(exported, tmp_path):
    model = _open(exported, tmp_path)
    units = {u.UnitType: u for u in model.by_type("IfcSIUnit")}
    assert "LENGTHUNIT" in units
    assert units["LENGTHUNIT"].Name == "METRE"
    assert units["LENGTHUNIT"].Prefix is None

    header = model.header
    assert "BIMGUARD AI" in header.file_name.author
    assert header.file_name.originating_system == "BIMGUARD AI"
    assert any("SB-001" in line for line in header.file_description.description)
    assert model.by_type("IfcProject")[0].Name == "Test project"


def test_a_result_with_no_zones_still_produces_a_valid_model(tmp_path):
    """No clash is not an error: an empty model opens, it just has no boxes."""
    data = build_clearance_zone_ifc([FINDINGS[2]])
    model = _open(data, tmp_path)
    assert model.schema == "IFC4"
    assert model.by_type("IfcBuildingElementProxy") == []


def test_findings_may_arrive_as_objects_rather_than_dicts(tmp_path):
    """The exporter is handed dataclasses in-process and dicts after caching."""

    class _Issue:
        def __init__(self, payload: dict):
            self.id = payload["id"]
            self.element_id = payload["element_id"]
            self.rule_id = payload["rule_id"]
            self.band = payload["band"]
            self.metadata = payload["metadata"]

    data = build_clearance_zone_ifc([_Issue(FINDINGS[0])])
    model = _open(data, tmp_path)
    assert len(model.by_type("IfcBuildingElementProxy")) == 1


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def test_ifc_is_a_registered_export_format():
    assert "ifc" in phase_6e_export.FORMATS
    media_type, extension = phase_6e_export.FORMATS["ifc"]
    assert extension == "ifc"
    assert media_type == "application/x-step"


def test_export_dispatches_ifc_and_returns_bytes(tmp_path):
    """The route's one code path: export(result, 'ifc') -> downloadable bytes."""
    content, media_type, extension = phase_6e_export.export(
        {"audit_issues": FINDINGS, "project_name": "Hospital federated"}, "ifc"
    )
    assert isinstance(content, bytes)
    assert media_type == "application/x-step"
    assert extension == "ifc"
    model = _open(content, tmp_path)
    assert len(model.by_type("IfcBuildingElementProxy")) == 2
    assert "Hospital federated" in model.by_type("IfcProject")[0].Name


def _properties(pset) -> dict:
    """Read an IfcPropertySet back the way a receiving tool would."""
    values: dict = {}
    for prop in pset.HasProperties:
        if prop.is_a("IfcPropertyListValue"):
            values[prop.Name] = [item.wrappedValue for item in prop.ListValues]
        else:
            values[prop.Name] = prop.NominalValue.wrappedValue
    return values
