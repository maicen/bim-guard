"""
BIMGUARD AI — IFC Parser Module
OpenBIM compliant: reads any IFC 2x3 or IFC4 file regardless of authoring tool.
Standard: ISO 16739-1
Library:  ifcopenshell (open source)
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional

import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.element
import ifcopenshell.util.placement


@dataclass
class ParsedElement:
    """One IFC element extracted from the model, identified by its GlobalId."""

    guid: str
    name: str
    ifc_type: str
    description: str
    material: str = "Unknown"


# Mapping from IFC type to plain English element category
IFC_SERVICE_LABELS = {
    "IfcPipeSegment": "Pipework",
    "IfcFlowSegment": "Flow segment",
    "IfcPipeFitting": "Pipe fitting",
    "IfcFlowFitting": "Flow fitting",
    "IfcValve": "Valve",
    "IfcPump": "Pump",
    "IfcHeatExchanger": "Heat exchanger",
    "IfcDistributionElement": "Distribution element",
    "IfcMember": "Structural member",
    "IfcPlate": "Structural plate",
    "IfcFastener": "Fastener / fixing",
    "IfcCableSegment": "Cable",
    "IfcDuctSegment": "Ductwork",
    "IfcDuctFitting": "Duct fitting",
}


def get_material_name(element, ifc_model) -> str:
    """Extract primary material name from an IFC element."""
    try:
        mats = ifcopenshell.util.element.get_materials(element)
        if mats:
            return mats[0].Name if hasattr(mats[0], "Name") else str(mats[0])
    except Exception:
        pass

    # Fallback: check material associations directly
    for rel in getattr(element, "HasAssociations", []):
        if rel.is_a("IfcRelAssociatesMaterial"):
            mat = rel.RelatingMaterial
            if hasattr(mat, "Name"):
                return mat.Name
            if hasattr(mat, "ForLayerSet"):
                layers = mat.ForLayerSet.MaterialLayers
                if layers:
                    return layers[0].Material.Name
    return "Unknown"


def parse_ifc_model(model) -> list[ParsedElement]:
    """Parse an already opened IFC model into elements.

    One entity yields exactly one ParsedElement. IFC classes are a hierarchy —
    an IfcPipeSegment is also an IfcFlowSegment and an IfcDistributionElement —
    so ``model.by_type()`` returns the same entity once per matching class in
    ``IFC_SERVICE_LABELS``. Without the GlobalId guard below, a three-entity
    model produced eight rows: inflated element counts and duplicate issues
    raised against a single GlobalId.

    ``IFC_SERVICE_LABELS`` is ordered specific to general and iterated in
    order, so first-occurrence-wins keeps the most specific class: a pipe
    segment is reported as IfcPipeSegment, not IfcDistributionElement.
    """
    elements = []
    # A GlobalId identifies exactly one entity in IFC, so a repeat is always
    # the same element arriving under a broader class.
    seen_guids: set[str] = set()

    target_types = list(IFC_SERVICE_LABELS.keys())

    for ifc_type in target_types:
        # IFC2X3/IFC4 differ for some MEP classes; skip unknown classes safely.
        try:
            typed_elements = model.by_type(ifc_type)
        except Exception:
            continue

        for el in typed_elements:
            guid = str(getattr(el, "GlobalId", "") or "").strip()
            if guid:
                if guid in seen_guids:
                    continue
                seen_guids.add(guid)

            elements.append(
                ParsedElement(
                    guid=el.GlobalId,
                    name=el.Name or f"{ifc_type}_{el.id()}",
                    ifc_type=ifc_type,
                    description=IFC_SERVICE_LABELS.get(ifc_type, ifc_type),
                    material=get_material_name(el, model),
                )
            )

    return elements


#: IFC classes grouped by discipline for the models table's discipline-breakdown
#: column. A heuristic for a quick-glance column, not a certification: classes
#: that fit no group below (proxies, generic furnishings, civil elements) land
#: in "other" rather than being guessed at.
_DISCIPLINE_CLASSES: dict[str, frozenset[str]] = {
    "architectural": frozenset(
        {
            "IfcWall",
            "IfcWallStandardCase",
            "IfcWallElementedCase",
            "IfcSlab",
            "IfcSlabStandardCase",
            "IfcRoof",
            "IfcDoor",
            "IfcWindow",
            "IfcCurtainWall",
            "IfcStair",
            "IfcStairFlight",
            "IfcRailing",
            "IfcRamp",
            "IfcRampFlight",
            "IfcCovering",
            "IfcFurnishingElement",
            "IfcSpace",
        }
    ),
    "structural": frozenset(
        {
            "IfcBeam",
            "IfcColumn",
            "IfcFooting",
            "IfcPile",
            "IfcMember",
            "IfcPlate",
            "IfcReinforcingBar",
            "IfcReinforcingMesh",
            "IfcTendon",
            "IfcTendonAnchor",
        }
    ),
    "mep": frozenset(
        {
            "IfcPipeSegment",
            "IfcPipeFitting",
            "IfcDuctSegment",
            "IfcDuctFitting",
            "IfcCableSegment",
            "IfcCableFitting",
            "IfcCableCarrierSegment",
            "IfcCableCarrierFitting",
            "IfcFlowSegment",
            "IfcFlowFitting",
            "IfcFlowTerminal",
            "IfcFlowController",
            "IfcFlowMovingDevice",
            "IfcFlowStorageDevice",
            "IfcFlowTreatmentDevice",
            "IfcFlowInstrument",
            "IfcElectricAppliance",
            "IfcElectricDistributionBoard",
            "IfcElectricFlowStorageDevice",
            "IfcElectricGenerator",
            "IfcElectricMotor",
            "IfcElectricTimeControl",
            "IfcSanitaryTerminal",
            "IfcValve",
            "IfcPump",
            "IfcBoiler",
            "IfcChiller",
            "IfcCoil",
            "IfcCondenser",
            "IfcCooledBeam",
            "IfcCoolingTower",
            "IfcDamper",
            "IfcEvaporativeCooler",
            "IfcEvaporator",
            "IfcFan",
            "IfcFilter",
            "IfcFireSuppressionTerminal",
            "IfcHeatExchanger",
            "IfcHumidifier",
            "IfcJunctionBox",
            "IfcLamp",
            "IfcLightFixture",
            "IfcMedicalDevice",
            "IfcMotorConnection",
            "IfcOutlet",
            "IfcProtectiveDevice",
            "IfcSensor",
            "IfcSpaceHeater",
            "IfcSwitchingDevice",
            "IfcTank",
            "IfcTransformer",
            "IfcTubeBundle",
            "IfcUnitaryEquipment",
            "IfcAirTerminal",
            "IfcAirTerminalBox",
            "IfcAlarm",
            "IfcActuator",
            "IfcController",
        }
    ),
}


def _classify_discipline(ifc_class: str) -> str:
    """Map one IFC entity class to a discipline bucket, or ``"other"``."""
    for discipline, classes in _DISCIPLINE_CLASSES.items():
        if ifc_class in classes:
            return discipline
    return "other"


@dataclass
class IfcModelSummary:
    """Cheap header/type-count metadata read from an IFC model, for display.

    Every field is a header entity or a ``by_type()`` count -- nothing here
    walks geometry -- so this stays fast enough to run on every model attach,
    not just during a full analysis pass.
    """

    schema: str = ""
    authoring_application: str = ""
    storey_count: Optional[int] = None
    element_count: Optional[int] = None
    discipline_summary: dict[str, int] = field(default_factory=dict)


def summarize_ifc_model(model) -> IfcModelSummary:
    """Read schema, authoring app, storey/element counts, and a discipline breakdown.

    Args:
        model: An already-open ``ifcopenshell`` model.
    """
    schema = str(getattr(model, "schema", "") or "")

    authoring_application = ""
    try:
        applications = model.by_type("IfcApplication")
        if applications:
            app = applications[0]
            authoring_application = " ".join(
                part
                for part in (
                    str(getattr(app, "ApplicationFullName", "") or ""),
                    str(getattr(app, "Version", "") or ""),
                )
                if part
            ).strip()
    except Exception:
        authoring_application = ""

    try:
        storey_count = len(model.by_type("IfcBuildingStorey"))
    except Exception:
        storey_count = None

    try:
        elements = model.by_type("IfcElement")
    except Exception:
        elements = []

    discipline_summary: dict[str, int] = {}
    for el in elements:
        category = _classify_discipline(el.is_a())
        discipline_summary[category] = discipline_summary.get(category, 0) + 1

    return IfcModelSummary(
        schema=schema,
        authoring_application=authoring_application,
        storey_count=storey_count,
        element_count=len(elements) if elements is not None else None,
        discipline_summary=discipline_summary,
    )


def extract_ifc_summary_metadata(ifc_path: str) -> IfcModelSummary:
    """Open an IFC file and read its cheap summary metadata.

    Args:
        ifc_path: Path to a local ``.ifc`` file.

    Returns:
        The summary. On any failure to open or read the file, callers should
        catch the exception themselves -- this raises rather than swallowing,
        since a caller may want to distinguish "no metadata" from "failed".
    """
    model = ifcopenshell.open(ifc_path)
    return summarize_ifc_model(model)


def get_schema_compatibility_note(model) -> str | None:
    """Return a short note when the IFC schema omits MEP classes used by this parser."""
    schema = str(getattr(model, "schema", "") or "").upper()
    if schema.startswith("IFC2X3"):
        return (
            "Schema compatibility: this IFC2X3 model may skip IFC4 MEP classes such as "
            "IfcPipeSegment; equivalent flow elements are parsed where available."
        )
    return None


def parse_ifc(ifc_path: str) -> list[ParsedElement]:
    """
    Backward-compatible wrapper that opens an IFC file and parses elements.

    Args:
        ifc_path: Path to .ifc file (IFC 2x3 or IFC4)

    Returns:
        List of ParsedElement dataclass instances
    """
    model = ifcopenshell.open(ifc_path)
    return parse_ifc_model(model)


def generate_synthetic_elements(n: int = 25) -> list[ParsedElement]:
    """
    Generates synthetic elements for demo use when no IFC file is available.
    """
    scenarios = [
        # (name, ifc_type, material)
        ("CHW Supply Pipe", "IfcPipeSegment", "SS_316_passive"),
        ("HWS Return Pipe", "IfcPipeSegment", "Copper"),
        ("Pool Heating Pipe", "IfcPipeSegment", "SS_316_passive"),
        ("Pool Plant Flange", "IfcPipeFitting", "SS_316_passive"),
        ("Coastal Facade Fix", "IfcFastener", "Aluminum_alloy_6063"),
        ("Roof Drainage Fix", "IfcFastener", "Galvanized_steel"),
        ("Structural Bracket", "IfcMember", "Carbon_steel_mild"),
        ("Cold Water Feed", "IfcPipeSegment", "Copper"),
        ("SS Pipe Clamp", "IfcPipeSegment", "SS_316_passive"),
        ("Unlined Pipe Clamp", "IfcPipeSegment", "SS_316_passive"),
        ("HX Tube Joint", "IfcHeatExchanger", "SS_316_passive"),
        ("Drainage Transition", "IfcPipeFitting", "Cast_iron"),
        ("Gas Pipe Riser", "IfcPipeSegment", "Carbon_steel_mild"),
        ("Marine Plant Pipe", "IfcPipeSegment", "SS_316_passive"),
        ("Electrical Tray", "IfcDistributionElement", "Aluminum_alloy_6063"),
        ("Vent Duct Bracket", "IfcDuctSegment", "Galvanized_steel"),
        ("Condenser Pipe", "IfcPipeSegment", "Copper"),
        ("Fix Plate Coastal", "IfcPlate", "SS_316_passive"),
        ("Sprinkler Header", "IfcPipeSegment", "Carbon_steel_mild"),
        ("Threaded SS Riser", "IfcPipeSegment", "SS_304_passive"),
        ("Pool Valve Body", "IfcValve", "SS_304_passive"),
        ("Industrial Flange", "IfcPipeFitting", "SS_316_passive"),
        ("Lead Flashing Fix", "IfcFastener", "Aluminum_alloy_6063"),
        ("Bronze Valve", "IfcValve", "Bronze"),
        ("Stainless Header", "IfcPipeSegment", "SS_316_passive"),
    ]

    elements = []
    for name, ifc_type, material in scenarios[:n]:
        elements.append(
            ParsedElement(
                # A real IfcGuid, not a sliced UUID. BCF's IfcGuid type is
                # 22 characters drawn from [0-9A-Za-z_$]; truncating a UUID
                # string hits the length but keeps the hyphens, so every
                # viewpoint built from synthetic elements failed schema
                # validation. ifcopenshell.guid.compress does the real
                # base64 encoding IFC specifies.
                guid=ifcopenshell.guid.compress(uuid.uuid4().hex),
                name=name,
                ifc_type=ifc_type,
                description=IFC_SERVICE_LABELS.get(ifc_type, ifc_type),
                material=material,
            )
        )
    return elements


def extract_ifc_header_iso_metadata(ifc_model) -> dict:
    """Extract IfcProject and IfcDocumentInformation header attributes from an opened IFC model or file path."""
    from pathlib import Path
    if isinstance(ifc_model, (str, Path)):
        try:
            ifc_model = ifcopenshell.open(str(ifc_model))
        except Exception:
            return {}

    header = {}
    try:
        projects = ifc_model.by_type("IfcProject")
        if projects:
            p = projects[0]
            header["project_name"] = getattr(p, "Name", "") or ""
            header["project_description"] = getattr(p, "Description", "") or ""
            header["project_long_name"] = getattr(p, "LongName", "") or ""

        doc_infos = ifc_model.by_type("IfcDocumentInformation")
        if doc_infos:
            d = doc_infos[0]
            header["document_id"] = getattr(d, "Identification", "") or getattr(d, "DocumentId", "") or ""
            header["document_name"] = getattr(d, "Name", "") or ""
            header["document_revision"] = getattr(d, "Revision", "") or ""
            header["document_status"] = getattr(d, "Status", "") or ""
    except Exception:
        pass

    return header
