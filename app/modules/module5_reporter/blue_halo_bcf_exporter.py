"""
app/modules/module5_reporter/blue_halo_bcf_exporter.py

Blue Halo — Phase 4: BCF 2.1 and IFC Pset export.

Takes the HaloVolume / ClashReport dataclasses produced by Module 2's Blue
Halo producer (app/modules/module2_producer/halo_volume_generator.py) and
renders them into the two hand-off formats Module 5 owns:

  - A BCF 2.1 ZIP archive (one topic per clash) for coordination software
    (Solibri, Navisworks, BIMcollab, ...), following the same
    bcf.version / project.bcfp / {guid}/markup.bcf / {guid}/viewpoint.bcfv /
    {guid}/snapshot.png layout as bcf_generator.generate_bcf().
  - A Pset_HaloReservation property-set dict, in the same {pset_name:
    {prop: value}} shape used elsewhere in this codebase (see
    module2_ifc_read.__init__.extract_rich_properties), for round-tripping
    the halo reservation back onto the IFC model.

DEPENDENCY DIRECTION
    This module imports from module2_producer (Module 2 -> Module 5, the
    same direction every other stage of the pipeline flows in) and reuses
    bcf_generator's BCFIssue dataclass and private XML templating helpers
    (same package, so the leading underscore signals "package-internal",
    not "single-file-internal"). halo_volume_generator.export_halo_to_bcf
    only prepares BCFIssue-shaped data and never imports zipfile or this
    module, keeping Module 2 itself free of any Module 5 dependency.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Optional

from app.modules.module2_producer.halo_volume_generator import (
    SCHEMA_VERSION as HALO_SCHEMA_VERSION,
    ClashReport,
    HaloVolume,
    _due_date_for_severity,
    export_halo_to_bcf,
)
from app.modules.module5_reporter.bcf_generator import (
    BCFIssue,
    _markup_xml,
    _placeholder_png,
    _viewpoint_xml,
)

PSET_HALO_RESERVATION = "Pset_HaloReservation"

_SEVERITY_TO_BCF_PRIORITY: dict[str, str] = {
    "critical": "Critical",
    "major": "Major",
    "minor": "Minor",
}


def _bcf_issue_from_clash(clash: ClashReport, *, halo: Optional[HaloVolume] = None) -> BCFIssue:
    """Build one BCFIssue from a ClashReport.

    Delegates to halo_volume_generator.export_halo_to_bcf when the
    originating HaloVolume is available — that gives the issue accurate
    brace-type/service-type context. Falls back to a generic,
    clash-only issue when it isn't (a caller that only has the flat
    ClashReport list, without the HaloVolume each one came from).

    Args:
        clash: The clash to convert.
        halo: The HaloVolume clash.halo_id refers to, if known.

    Returns:
        A BCFIssue ready for markup.bcf / viewpoint.bcfv rendering.
    """
    if halo is not None:
        return BCFIssue(**export_halo_to_bcf(clash, halo))

    return BCFIssue(
        guid=str(uuid.uuid4()).upper(),
        title=f"Seismic bracing clearance clash on {clash.halo_source_element_id}",
        description=clash.description,
        priority=_SEVERITY_TO_BCF_PRIORITY.get(clash.severity, "Normal"),
        status="Active",
        assigned_to="Unassigned",
        due_date=_due_date_for_severity(clash.severity),
        labels=["blue_halo", "seismic_bracing", clash.severity],
        component_guid=clash.clashing_element_id,
        component_name=clash.clashing_element_class,
        service_type="",
        floor="",
        risk_band=clash.severity.upper(),
        mechanism="blue_halo_seismic_clearance",
        risk_score=0.0,
        mitigation=(
            "Relocate or resize the clashing element, or select a brace "
            "variant with a smaller footprint, so the clearance envelope "
            "no longer intersects it."
        ),
    )


def generate_bcf_zip_from_halo_clashes(
    clashes: list[ClashReport],
    project_id: str,
    *,
    halos: Optional[dict[str, HaloVolume]] = None,
    project_name: str = "BIMGUARD AI — Blue Halo Seismic Bracing Clearance Report",
) -> bytes:
    """Render Blue Halo clashes into a BCF 2.1 ZIP archive.

    Args:
        clashes: Clash reports to export — typically the concatenated
            output of detect_halo_clash / detect_halo_clash_against_geometry
            across every halo volume in a run.
        project_id: Stable identifier written to project.bcfp's ProjectId
            (a BIMGUARD project id, not a random GUID — so re-exporting the
            same project is recognised as the same BCF project by
            coordination software).
        halos: Optional {HaloVolume.id: HaloVolume} lookup. When a clash's
            halo_id is found here, the richer export_halo_to_bcf() issue is
            used instead of the generic clash-only fallback.
        project_name: Human-readable name written to project.bcfp.

    Returns:
        The BCF-ZIP file contents as bytes. An empty `clashes` list still
        produces a structurally valid BCF ZIP (bcf.version + project.bcfp,
        zero topic folders).
    """
    halos = halos or {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "bcf.version",
            """<?xml version="1.0" encoding="UTF-8"?>
<Version VersionId="2.1" xsi:noNamespaceSchemaLocation="version.xsd"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <DetailedVersion>2.1</DetailedVersion>
</Version>""",
        )
        zf.writestr(
            "project.bcfp",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<ProjectExtension xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Project ProjectId="{project_id}">
    <Name>{project_name}</Name>
  </Project>
  <ExtensionSchema>extensions.xsd</ExtensionSchema>
</ProjectExtension>""",
        )

        for index, clash in enumerate(clashes):
            issue = _bcf_issue_from_clash(clash, halo=halos.get(clash.halo_id))
            folder = issue.guid + "/"
            viewpoint_guid = str(uuid.uuid4()).upper()
            zf.writestr(folder + "markup.bcf", _markup_xml(issue, index, viewpoint_guid))
            zf.writestr(folder + "viewpoint.bcfv", _viewpoint_xml(issue, viewpoint_guid))
            zf.writestr(folder + "snapshot.png", _placeholder_png())

    return buf.getvalue()


def generate_pset_halo_reservation(halo: HaloVolume) -> dict:
    """Build the Pset_HaloReservation property set for one halo volume.

    Property naming follows the Pset_BIMGuard*-style custom-Pset
    convention documented in docs/ifc-property-mapping.md, and the
    {pset_name: {prop: value}} shape used throughout this codebase for IFC
    round-trip (see module2_ifc_read.__init__.extract_rich_properties).
    Writing an actual IfcPropertySet back onto the model via ifcopenshell
    is deferred to the phase that wires this into the IFC egress path
    (module2_ifc_read/ifc_egress.py) — Phase 4 returns the property data
    only, same as Module 2's own preview export,
    halo_volume_generator.export_halo_to_ifc_property_set.

    Args:
        halo: The halo volume to export.

    Returns:
        {"Pset_HaloReservation": {property_name: value, ...}}
    """
    return {
        PSET_HALO_RESERVATION: {
            "SchemaVersion": HALO_SCHEMA_VERSION,
            "SourceElementGlobalId": halo.source_element_id,
            "SourceIfcClass": halo.source_ifc_class,
            "BraceType": halo.brace_type.value,
            "RuleVariant": halo.rule_variant or "",
            "ClearanceMm": halo.clearance_mm,
            "HaloVolumeMm3": halo.halo_bbox_mm.volume_mm3,
            "ElementBBoxMinMm": [
                halo.element_bbox_mm.min.x,
                halo.element_bbox_mm.min.y,
                halo.element_bbox_mm.min.z,
            ],
            "ElementBBoxMaxMm": [
                halo.element_bbox_mm.max.x,
                halo.element_bbox_mm.max.y,
                halo.element_bbox_mm.max.z,
            ],
            "HaloBBoxMinMm": [
                halo.halo_bbox_mm.min.x,
                halo.halo_bbox_mm.min.y,
                halo.halo_bbox_mm.min.z,
            ],
            "HaloBBoxMaxMm": [
                halo.halo_bbox_mm.max.x,
                halo.halo_bbox_mm.max.y,
                halo.halo_bbox_mm.max.z,
            ],
            "GeneratedAt": halo.generated_at,
        }
    }
