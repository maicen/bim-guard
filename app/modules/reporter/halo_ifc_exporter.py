"""Write SB-001 clearance envelopes as a standalone IFC4 model.

WHAT THIS IS FOR

    Blue Halo computes a clearance envelope around every braced service, uses
    it for clash maths, and until now threw the geometry away: a finding
    carried the overlap volume and the clearance, but nothing a coordinator
    could open. This module turns the envelopes back into geometry -- one
    IfcBuildingElementProxy box per finding -- in a file any IFC tool opens
    (Revit, Navisworks, Solibri, BlenderBIM, usBIM).

    The output is a NEW model, never an edit of the uploaded one. A clearance
    zone is BIMGUARD's assertion about space, not a fact about the author's
    design, and writing it into their federated model would blur the two. The
    zones carry the source element's GlobalId in Pset_HaloReservation, so a
    coordinator can relate them back without the two files being merged.

WHAT IT READS

    Findings, not HaloVolumes. By export time the run is long finished and only
    the Issue metadata survives, which is why phase_6d_seismic records the
    envelope there (``halo_bbox``, ``element_bbox``, ``source_ifc_class``,
    ``halo_generated_at``). A finding without ``halo_bbox`` -- a data-quality
    note, or any mechanism that is not SB-001 -- is skipped rather than
    guessed at: an invented box is worse than an absent one.

UNITS

    Findings carry millimetres in model coordinates. IFC here is SI metres, so
    every coordinate is divided by 1000 on the way in. The property set keeps
    the millimetre values, because that is what the rest of BIMGUARD reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit

from app.modules.blue_halo.halo_volume_generator import (
    PSET_HALO_RESERVATION,
    halo_reservation_properties,
)

#: Written into the IFC header and the owner history.
APPLICATION_NAME = "BIMGUARD AI"
APPLICATION_ID = "BIMGUARD"

#: Only SB-001 findings carry a clearance envelope.
_SEISMIC_RULE_PREFIX = "SB-001"

#: Findings-side context, kept out of Pset_HaloReservation so that the property
#: set shared with the BCF path keeps exactly the shape it has there.
PSET_HALO_FINDING = "Pset_HaloFinding"

#: A degenerate box (zero or negative extent on any axis) cannot be extruded.
#: Below this, in millimetres, the zone is skipped rather than written as a
#: sliver that no viewer will show.
_MIN_EXTENT_MM = 1e-6


def _field(issue: Any, name: str, default: Any = None) -> Any:
    """Read *name* off an Issue dataclass or the dict form of one.

    The export path is handed dataclasses in-process and dicts when a result
    has been through the cache or the API contract, and both reach here.
    """
    if isinstance(issue, dict):
        return issue.get(name, default)
    return getattr(issue, name, default)


def _metadata(issue: Any) -> dict:
    """The mechanism-specific extras, under either of the two names they use.

    ``Issue.metadata`` becomes ``details`` in the API contract
    (analyze.py ``_format_result``), so a result that has been round-tripped
    through the frontend arrives under the other name.
    """
    meta = _field(issue, "metadata") or _field(issue, "details") or {}
    return meta if isinstance(meta, dict) else {}


def _corners_mm(bbox: Any) -> Optional[tuple[list[float], list[float]]]:
    """Extract ``(min_mm, max_mm)`` from a stored bbox, or None if unusable."""
    if not isinstance(bbox, dict):
        return None
    lo = bbox.get("min_mm")
    hi = bbox.get("max_mm")
    if not isinstance(lo, (list, tuple)) or not isinstance(hi, (list, tuple)):
        return None
    if len(lo) != 3 or len(hi) != 3:
        return None
    try:
        return [float(v) for v in lo], [float(v) for v in hi]
    except (TypeError, ValueError):
        return None


def issue_has_clearance_zone(issue: Any) -> bool:
    """True when *issue* carries an envelope this module can draw.

    The same predicate the API uses to decide whether an IFC export would be
    empty, so the answer cannot differ between the check and the export.
    """
    meta = _metadata(issue)
    corners = _corners_mm(meta.get("halo_bbox"))
    if corners is None:
        return False
    lo, hi = corners
    return all(hi[i] - lo[i] > _MIN_EXTENT_MM for i in range(3))


def count_clearance_zones(issues: Iterable[Any]) -> int:
    """How many findings would become geometry."""
    return sum(1 for issue in issues if issue_has_clearance_zone(issue))


def _zone_name(issue: Any) -> str:
    """Human-readable label: what it is, which rule, which band."""
    meta = _metadata(issue)
    rule_id = str(_field(issue, "rule_id", "") or _SEISMIC_RULE_PREFIX)
    band = _band_text(issue).upper()
    clashing = str(meta.get("clashing_element_id", "") or "")
    suffix = f" vs {clashing}" if clashing else ""
    return f"Seismic clearance zone [{rule_id}] {band}{suffix}"


def _band_text(issue: Any) -> str:
    """The risk band as a plain string, whether it is an enum or already text."""
    band = _field(issue, "band", "")
    value = getattr(band, "value", band)
    return str(value or "")


def _zone_description(issue: Any) -> str:
    """One sentence a coordinator can act on, without opening the report."""
    meta = _metadata(issue)
    clearance = meta.get("clearance_mm")
    brace = meta.get("brace_type", "")
    source = str(_field(issue, "element_id", "") or "")
    parts = [
        f"BIMGUARD SB-001 seismic bracing clearance envelope around {source}.",
    ]
    if clearance is not None:
        parts.append(f"Clearance {clearance} mm.")
    if brace:
        parts.append(f"Brace type {brace}.")
    overlap = meta.get("overlap_volume_mm3")
    if overlap is not None:
        parts.append(f"Intrusion {overlap} mm3.")
    parts.append("Screening geometry, not a bracing design.")
    return " ".join(parts)


def _box_representation(file: ifcopenshell.file, context, size_m: tuple[float, float, float]):
    """A rectangular prism of *size_m*, centred on x/y, rising from z=0.

    IfcExtrudedAreaSolid over an IfcRectangleProfileDef rather than a mesh:
    it is the smallest exact description of a box, and every IFC viewer draws
    it as a solid rather than a shell.
    """
    x_m, y_m, z_m = size_m
    profile = file.create_entity(
        "IfcRectangleProfileDef",
        ProfileType="AREA",
        ProfileName="SeismicClearanceZone",
        XDim=x_m,
        YDim=y_m,
    )
    solid = file.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=file.create_entity(
            "IfcAxis2Placement3D",
            Location=file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0)),
        ),
        ExtrudedDirection=file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
        Depth=z_m,
    )
    return file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solid],
    )


def _placement_matrix(origin_m: tuple[float, float, float]):
    """A 4x4 identity matrix translated to *origin_m*, as ifcopenshell wants it."""
    x, y, z = origin_m
    return (
        (1.0, 0.0, 0.0, x),
        (0.0, 1.0, 0.0, y),
        (0.0, 0.0, 1.0, z),
        (0.0, 0.0, 0.0, 1.0),
    )


def build_clearance_zone_ifc(
    issues: Iterable[Any],
    *,
    project_name: str = "BIMGUARD AI seismic clearance zones",
    site_name: str = "Exported clearance zones",
    building_name: str = "Clearance zone container",
    storey_name: str = "Clearance zones",
    generated_at: Optional[str] = None,
) -> bytes:
    """Build a standalone IFC4 model of the clearance envelopes in *issues*.

    Args:
        issues: SB-001 findings. Anything without a usable ``halo_bbox`` is
            skipped, so a mixed result set or a run with no clashes is valid
            input and yields a model with no proxies rather than an error.
        project_name: IfcProject name, shown as the model name in most tools.
        generated_at: ISO timestamp for the header; defaults to now (UTC).

    Returns:
        The IFC-SPF file as UTF-8 bytes, ready to stream as a download.
    """
    stamp = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    file = ifcopenshell.file(schema="IFC4")

    project = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcProject", name=project_name
    )
    length_unit = ifcopenshell.api.unit.add_si_unit(file, unit_type="LENGTHUNIT")
    area_unit = ifcopenshell.api.unit.add_si_unit(file, unit_type="AREAUNIT")
    volume_unit = ifcopenshell.api.unit.add_si_unit(file, unit_type="VOLUMEUNIT")
    ifcopenshell.api.unit.assign_unit(file, units=[length_unit, area_unit, volume_unit])

    model_context = ifcopenshell.api.context.add_context(file, context_type="Model")
    body_context = ifcopenshell.api.context.add_context(
        file,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_context,
    )

    # A spatial container, because a product outside one is not a valid IFC4
    # model and several viewers will not list it.
    site = ifcopenshell.api.root.create_entity(file, ifc_class="IfcSite", name=site_name)
    building = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcBuilding", name=building_name
    )
    storey = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcBuildingStorey", name=storey_name
    )
    ifcopenshell.api.aggregate.assign_object(file, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(file, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(file, products=[storey], relating_object=building)

    for issue in issues:
        if not issue_has_clearance_zone(issue):
            continue
        _add_zone(file, issue, body_context, storey, stamp)

    _write_header(file, project_name, stamp)
    return file.to_string().encode("utf-8")


def _add_zone(file: ifcopenshell.file, issue: Any, body_context, storey, stamp: str) -> None:
    """Add one proxy box, placed and propertied, for a single finding."""
    meta = _metadata(issue)
    lo_mm, hi_mm = _corners_mm(meta.get("halo_bbox"))  # type: ignore[misc]
    size_mm = [hi_mm[i] - lo_mm[i] for i in range(3)]

    proxy = ifcopenshell.api.root.create_entity(
        file,
        ifc_class="IfcBuildingElementProxy",
        name=_zone_name(issue),
        predefined_type="PROVISIONFORVOID",
    )
    proxy.Description = _zone_description(issue)
    proxy.Tag = str(_field(issue, "id", "") or "")

    # The profile is centred on its placement, so the placement sits at the box
    # centre in x/y and at its base in z, and the extrusion rises to the top.
    origin_m = (
        (lo_mm[0] + size_mm[0] / 2.0) / 1000.0,
        (lo_mm[1] + size_mm[1] / 2.0) / 1000.0,
        lo_mm[2] / 1000.0,
    )
    ifcopenshell.api.geometry.edit_object_placement(
        file, product=proxy, matrix=_placement_matrix(origin_m), is_si=True
    )
    representation = _box_representation(
        file, body_context, (size_mm[0] / 1000.0, size_mm[1] / 1000.0, size_mm[2] / 1000.0)
    )
    ifcopenshell.api.geometry.assign_representation(
        file, product=proxy, representation=representation
    )
    ifcopenshell.api.spatial.assign_container(
        file, products=[proxy], relating_structure=storey
    )

    element_bbox = _corners_mm(meta.get("element_bbox")) or (lo_mm, hi_mm)
    volume_mm3 = size_mm[0] * size_mm[1] * size_mm[2]
    properties = halo_reservation_properties(
        source_element_id=str(_field(issue, "element_id", "") or ""),
        source_ifc_class=str(meta.get("source_ifc_class", "") or ""),
        brace_type=str(meta.get("brace_type", "") or ""),
        rule_variant=str(meta.get("rule_variant") or ""),
        clearance_mm=float(meta.get("clearance_mm") or 0.0),
        halo_volume_mm3=volume_mm3,
        element_bbox_min_mm=element_bbox[0],
        element_bbox_max_mm=element_bbox[1],
        halo_bbox_min_mm=lo_mm,
        halo_bbox_max_mm=hi_mm,
        generated_at=str(meta.get("halo_generated_at") or stamp),
    )
    # Findings-side context the halo itself never knew: which rule fired, how
    # badly, and what intruded. A coordinator filtering the zone model wants
    # these, and they do not belong in Pset_HaloReservation, whose shape is
    # shared with the BCF path.
    finding_properties = {
        "RuleId": str(_field(issue, "rule_id", "") or ""),
        "FindingId": str(_field(issue, "id", "") or ""),
        "RiskBand": _band_text(issue),
        "ClashingElementGlobalId": str(meta.get("clashing_element_id", "") or ""),
        "ClashingElementIfcClass": str(meta.get("clashing_element_class", "") or ""),
        "OverlapVolumeMm3": float(meta.get("overlap_volume_mm3") or 0.0),
        "SourceModel": str(meta.get("source_model", "") or ""),
        "ClashingSourceModel": str(meta.get("clashing_source_model", "") or ""),
    }

    for pset_name, values in (
        (PSET_HALO_RESERVATION, properties),
        (PSET_HALO_FINDING, finding_properties),
    ):
        _attach_property_set(file, proxy, pset_name, values)


def _property_value(file: ifcopenshell.file, value: Any):
    """Wrap a Python value as an IFC property value.

    Numbers become IfcReal, not IfcLengthMeasure, deliberately. A length
    measure is interpreted in the project's length unit, which is metres here,
    so a 200 mm clearance written as a length would read as 200 m in a viewer.
    These properties are millimetres and say so in their names; IfcReal carries
    the number without inviting a conversion.
    """
    if isinstance(value, bool):
        return file.create_entity("IfcBoolean", bool(value))
    if isinstance(value, (int, float)):
        return file.create_entity("IfcReal", float(value))
    return file.create_entity("IfcLabel", str(value))


def _attach_property_set(
    file: ifcopenshell.file, product, name: str, values: dict
) -> None:
    """Attach one property set to *product*, building the properties by hand.

    ``ifcopenshell.api.pset.edit_pset`` cannot type a list value without a
    registered pset template, and a custom Pset_ name has none, so the
    coordinate triples are written here as IfcPropertyListValue directly. The
    relationship itself still comes from the API.
    """
    pset = ifcopenshell.api.pset.add_pset(file, product=product, name=name)
    properties = []
    for prop_name, value in values.items():
        if isinstance(value, (list, tuple)):
            properties.append(
                file.create_entity(
                    "IfcPropertyListValue",
                    Name=prop_name,
                    ListValues=[_property_value(file, item) for item in value],
                )
            )
        else:
            properties.append(
                file.create_entity(
                    "IfcPropertySingleValue",
                    Name=prop_name,
                    NominalValue=_property_value(file, value),
                )
            )
    pset.HasProperties = tuple(properties)


def _write_header(file: ifcopenshell.file, project_name: str, stamp: str) -> None:
    """Fill the SPF header so the file says where it came from.

    A viewer shows these fields in "model information", and a coordinator
    receiving a file of boxes deserves to see which tool asserted them.
    """
    header = file.header
    header.file_name.name = f"{project_name}.ifc"
    header.file_name.time_stamp = stamp
    header.file_name.author = [APPLICATION_NAME]
    header.file_name.organization = [APPLICATION_NAME]
    header.file_name.preprocessor_version = f"ifcopenshell {ifcopenshell.version}"
    header.file_name.originating_system = APPLICATION_NAME
    header.file_description.description = (
        "ViewDefinition [CoordinationView]",
        f"BIMGUARD SB-001 seismic clearance zones, generated {stamp}",
    )
