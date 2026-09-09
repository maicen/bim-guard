"""Build ``data/ids/bimguard_piping_intake.ids`` with ifctester.ids.

The IDS is committed, so this script is not needed to use it. It is the record
of how the file was produced and the way to change it: edit a specification
here and re-run, rather than hand-editing the XML.

Every specification below is traceable to a row of
``docs/reference/piping_intake_sources.md``, which cites the parser line that
reads the datum. Nothing is required that no parser line reads.

Output is deterministic. The one field that would otherwise vary between runs
-- the header date -- is not read from the clock but passed in explicitly with
``--date``, so the same arguments always produce the same bytes.
``tests/test_model_intake_ids.py`` builds with the committed file's own date
and asserts the bytes match, which is what stops the committed IDS and this
script from drifting apart.

``--date`` is required rather than defaulted: a default would let a run
silently produce a file that differs from the committed one in a field nobody
looked at.

Usage::

    uv run python scripts/build_intake_ids.py --date 2026-09-08
    uv run python scripts/build_intake_ids.py --date 2026-09-08 --out /tmp/check.ids

Exit codes: ``0`` on success, ``1`` if the document fails IDS 1.0 schema
validation, ``2`` on a malformed ``--date``.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from ifctester import ids

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Where the committed IDS lives; the checker script defaults to the same path.
DEFAULT_OUT = REPO_ROOT / "data" / "ids" / "bimguard_piping_intake.ids"

#: The date carried by the committed IDS. Recorded here so a reader knows what
#: to pass to reproduce it; the builder itself takes the value from ``--date``
#: and never falls back to this constant or to the clock.
COMMITTED_DATE = "2026-09-08"

#: IDS 1.0 types the header date as xs:date.
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# piping_producer.py:118-137 — the classes produce_piping_elements_from_model
# iterates. An element of any other class is never seen by the audit.
PIPING_CLASSES = [
    "IFCPIPESEGMENT",
    "IFCPIPEFITTING",
    "IFCDUCTSEGMENT",
    "IFCDUCTFITTING",
    "IFCVALVE",
    "IFCPUMP",
    "IFCFILTER",
    "IFCTANK",
    "IFCHEATEXCHANGER",
    "IFCAIRTERMINAL",
    "IFCFLOWSEGMENT",
    "IFCFLOWFITTING",
    "IFCFLOWCONTROLLER",
    "IFCFLOWMOVINGDEVICE",
    "IFCFLOWTERMINAL",
    "IFCFLOWSTORAGEDEVICE",
    "IFCFLOWTREATMENTDEVICE",
    "IFCDISTRIBUTIONELEMENT",
]

IFC_VERSIONS = ["IFC4", "IFC2X3"]

# The parser flattens every property set and matches on the BARE property name
# (ifc_parser.py:400-418, piping_producer.py:1033-1053), so the set name is
# genuinely free. An IDS property facet nevertheless requires one, and
# ifctester resolves only a single named set per facet -- a pattern picks one
# matching set rather than OR-ing across all of them -- so each specification
# below names the set this project asks senders to use, and says so in its own
# description. A failure on one of these can therefore be a false negative: the
# property may be present under another set name and the audit would still
# read it.
PSET_NOTE = (
    " PROPERTY SET NAME: the audit reads the property name and ignores the set "
    "it sits in, but an IDS facet must name one set, so this specification "
    "checks {pset}. If your exporter writes the property under a different set "
    "name the audit will still read it and this line may report a false failure."
)

#: Real IFC4 property set; OperatingTemperature is its first entry.
PSET_OCCURRENCE = "Pset_PipeSegmentOccurrence"
#: This project's convention for the three MC-001 hydraulic inputs, none of
#: which has a buildingSMART equivalent.
PSET_HYDRAULICS = "Pset_BimGuardHydraulics"
#: This project's convention for the declared second material at a junction.
PSET_COUPLE = "Pset_BimGuardCouple"
#: This project's convention for a material carried as a property rather than
#: as an association. Introduced by this IDS; the parser reads the bare name.
PSET_MATERIAL = "Pset_BimGuardMaterial"
#: This project's convention for a stated atmospheric class. Introduced by this
#: IDS; the parser reads the bare name.
PSET_ENVIRONMENT = "Pset_BimGuardEnvironment"


def any_of(names: list[str]) -> ids.Restriction:
    """Return a restriction matching any one of *names*, as the parser tries them."""
    return ids.Restriction(options={"enumeration": names})


def applicability() -> list:
    """Return the applicability shared by every specification: the flow classes."""
    return [ids.Entity(name=ids.Restriction(options={"enumeration": PIPING_CLASSES}))]


def spec(name, description, requirements, usage, identifier):
    s = ids.Specification(
        name=name,
        ifcVersion=IFC_VERSIONS,
        identifier=identifier,
        description=description,
    )
    s.applicability = applicability()
    s.requirements = requirements
    s.set_usage(usage)
    return s


def build(date: str) -> ids.Ids:
    doc = ids.Ids(
        title="BIMGUARD AI — Piping audit intake requirements",
        version="1.0.0",
        author="info@aspiringdesign3d.co.nz",
        copyright="Aspiring Design 3D Consultancy Ltd",
        date=date,
        purpose=(
            "States what an IFC model must carry for the BIMGUARD AI piping "
            "corrosion audit (GC-001 galvanic, CC-001 crevice, MC-001 "
            "microbiological, MM-001 material-media, XM-001 cross-material) to "
            "return verdicts rather than Undetermined. Every requirement is "
            "derived from a line of the parser; see "
            "docs/reference/piping_intake_sources.md for the citation behind "
            "each specification."
        ),
        milestone="Model intake",
        description=(
            "Author: Aspiring Design 3D Consultancy Ltd. Requirements are "
            "traceable to app/modules/ifc_reader/piping_producer.py, "
            "app/modules/ifc_reader/ifc_parser.py and "
            "app/modules/phase_6/phase_6c_corrosion_ui.py."
        ),
    )

    # -- Required --------------------------------------------------------
    doc.specifications.append(
        spec(
            "Material association",
            "REQUIRED. Each piping element must carry a material, through "
            "IfcRelAssociatesMaterial on the occurrence or on its type "
            "(IfcMaterial, IfcMaterialLayerSet(Usage), IfcMaterialConstituentSet "
            "or IfcMaterialProfileSet are all followed). CONSEQUENCE IF ABSENT: "
            "the element is material_unresolved — GC-001 and CC-001 are refused "
            "on it and return Undetermined rather than a verdict, and XM-001 "
            "raises material_not_in_series instead of scoring a couple. The name "
            "must be recognisable text such as 'Copper', 'ASTM B88', '316L', "
            "'Galvanised steel' or 'PVC'; a placeholder such as 'Material', "
            "'Default', 'N/A' or a vendor part code resolves to nothing and "
            "counts as absent. ENGINES: GC-001, CC-001, MM-001, XM-001.",
            [ids.Material(cardinality="required")],
            "required",
            "BG-PIPE-MATERIAL",
        )
    )

    doc.specifications.append(
        spec(
            "System assignment",
            "REQUIRED. Each piping element must be assigned to an IfcSystem or "
            "IfcDistributionSystem through IfcRelAssignsToGroup, and that group "
            "must be named (for example 'Domestic Hot Water', 'Chilled Water "
            "Return', 'Fire Sprinkler', 'Medical Gas — Oxygen'). CONSEQUENCE IF "
            "ABSENT: the element falls back to its Name, Description and "
            "PredefinedType for classification and, failing those, is "
            "PipingSystem.UNKNOWN — which removes the media axis MM-001 scores "
            "against and disables the system-based material and temperature "
            "fallbacks, so an element with no material and no system cannot be "
            "recovered at all. ENGINES: all five.",
            [
                ids.PartOf(
                    name=ids.Restriction(
                        options={"enumeration": ["IFCSYSTEM", "IFCDISTRIBUTIONSYSTEM"]}
                    ),
                    relation="IFCRELASSIGNSTOGROUP",
                    cardinality="required",
                )
            ],
            "required",
            "BG-PIPE-SYSTEM",
        )
    )

    doc.specifications.append(
        spec(
            "Element name",
            "REQUIRED. Each piping element must carry a non-empty Name. "
            "CONSEQUENCE IF ABSENT: Name is the fallback hint for system "
            "classification when no IfcSystem exists, and it is the only input "
            "to subtype classification and joint-type classification besides "
            "the IFC class and PredefinedType. Without it an element with no "
            "system assignment is unclassifiable. ENGINES: all five, indirectly.",
            [ids.Attribute(name="Name", cardinality="required")],
            "required",
            "BG-PIPE-NAME",
        )
    )

    # -- Optional: material fallback -------------------------------------
    doc.specifications.append(
        spec(
            "Material stated as a property",
            "OPTIONAL fallback for the material association above. A property "
            "named Material or MaterialName, in any property set. On the models "
            "measured for this audit this is the only source that resolves a "
            "material on some tools' output, where the material sits in a "
            "property set and no IfcRelAssociatesMaterial exists. CONSEQUENCE IF "
            "ABSENT: none on its own — this only matters where the material "
            "association is also missing, in which case see BG-PIPE-MATERIAL. "
            "ENGINES: GC-001, CC-001, MM-001, XM-001.",
            [
                ids.Property(
                    propertySet=PSET_MATERIAL,
                    baseName=any_of(["Material", "MaterialName"]),
                    dataType="IFCLABEL",
                )
            ],
            "optional",
            "BG-PIPE-MATERIAL-PROPERTY",
        )
    )

    # -- Optional: hydraulics --------------------------------------------
    doc.specifications.append(
        spec(
            "Flow velocity",
            "OPTIONAL. Design or operating flow velocity in m/s, as a property "
            "named FlowVelocity, Velocity, FluidVelocity, DesignFlowVelocity or "
            "AverageVelocity, in any property set. IFC4 defines no flow-velocity "
            "property for a pipe segment, so there is no buildingSMART name to "
            "prefer; this repository's own generator writes FlowVelocity in "
            "Pset_BimGuardHydraulics. CONSEQUENCE IF ABSENT: the value stays "
            "absent and is never defaulted to 0.0, because 0.0 m/s is not a "
            "missing velocity but the worst one (stagnant, risk 1.0). MC-001 "
            "still runs if a dead-leg length or an operating temperature is "
            "present; only when all three are absent is MC-001 refused as "
            "hydraulics_unavailable. The engine does not fail — it returns "
            "Undetermined. ENGINES: MC-001.",
            [
                ids.Property(
                    propertySet=PSET_HYDRAULICS,
                    baseName=any_of(
                        [
                            "FlowVelocity",
                            "Velocity",
                            "FluidVelocity",
                            "DesignFlowVelocity",
                            "AverageVelocity",
                        ]
                    ),
                    dataType="IFCREAL",
                )
            ],
            "optional",
            "BG-PIPE-VELOCITY",
        )
    )

    doc.specifications.append(
        spec(
            "Operating temperature",
            "OPTIONAL. Operating, working, fluid, design or medium temperature "
            "in degrees Celsius, as a property named OperatingTemperature, "
            "WorkingTemperature, FluidTemperature, DesignTemperature or "
            "MediumTemperature, in any property set. OperatingTemperature is the "
            "first entry in the real IFC4 Pset_PipeSegmentOccurrence, which is "
            "where this repository's generator writes it. CONSEQUENCE IF ABSENT: "
            "the network path falls back to a design temperature deduced from "
            "the system (60 C for domestic hot water, 6/12 C for chilled flow "
            "and return, 82/71 C for heating, and so on), tagged low confidence "
            "and warned on; where no convention exists the value stays absent "
            "and MM-001 raises temperature_missing. The element-level path has "
            "no such fallback. Temperature matters more than a few degrees "
            "usually would: above about 60 C the zinc on galvanised steel "
            "reverses polarity, which is a step change, not a gradient. "
            "ENGINES: MC-001, MM-001.",
            [
                ids.Property(
                    propertySet=PSET_OCCURRENCE,
                    baseName=any_of(
                        [
                            "OperatingTemperature",
                            "WorkingTemperature",
                            "FluidTemperature",
                            "DesignTemperature",
                            "MediumTemperature",
                        ]
                    ),
                    dataType="IFCREAL",
                )
            ],
            "optional",
            "BG-PIPE-TEMPERATURE",
        )
    )

    doc.specifications.append(
        spec(
            "Dead-leg length",
            "OPTIONAL. Length of the stagnant branch in metres, as a property "
            "named DeadLegLength, StagnationLength or DeadLegLengthM, in any "
            "property set. 0.0 is a meaningful value — it states the element is "
            "a through-flow run, which is a different fact from the property "
            "being absent. CONSEQUENCE IF ABSENT: MC-001 classifies dead legs by "
            "length-to-diameter ratio, so without a length that axis is scored "
            "as unknown; the engine still runs if a velocity or a temperature is "
            "present. ENGINES: MC-001.",
            [
                ids.Property(
                    propertySet=PSET_HYDRAULICS,
                    baseName=any_of(
                        ["DeadLegLength", "StagnationLength", "DeadLegLengthM"]
                    ),
                    dataType="IFCREAL",
                )
            ],
            "optional",
            "BG-PIPE-DEADLEG-LENGTH",
        )
    )

    doc.specifications.append(
        spec(
            "Dead-leg flag",
            "OPTIONAL. Boolean IsDeadLeg, Stagnant or IsStagnant, in any "
            "property set, for tools that can flag a dead leg but cannot "
            "measure one. FALSE is read as a measurement of through flow and "
            "yields a length of 0.0. TRUE records that the element is a dead leg "
            "but leaves the length absent, because MC-001 classifies by "
            "length-to-diameter ratio and no honest length can be invented from "
            "a flag. Prefer BG-PIPE-DEADLEG-LENGTH where a length is available. "
            "CONSEQUENCE IF ABSENT: as BG-PIPE-DEADLEG-LENGTH. ENGINES: MC-001.",
            [
                ids.Property(
                    propertySet=PSET_HYDRAULICS,
                    baseName=any_of(["IsDeadLeg", "Stagnant", "IsStagnant"]),
                    dataType="IFCBOOLEAN",
                )
            ],
            "optional",
            "BG-PIPE-DEADLEG-FLAG",
        )
    )

    # -- Optional: environment, couple, geometry -------------------------
    doc.specifications.append(
        spec(
            "Environment class",
            "OPTIONAL. The atmosphere around the pipe — not the fluid inside it "
            "— as a property named EnvironmentClass, EnvironmentalClass, "
            "CorrosivityCategory or AtmosphericEnvironment, in any property set. "
            "Accepted values are the class name (T1_indoor_damp), the bare code "
            "(T1 through T5, T0 dry) or a code with a descriptor (T3 chloride). "
            "The literal 'unclassified' is rejected: a property that says "
            "'unknown' is not a classification. CONSEQUENCE IF ABSENT: the class "
            "is inferred from IfcSpace and IfcBuildingStorey names (pool, "
            "coastal, plant, basement, roof, kitchen, office and so on) at "
            "medium confidence, and failing that defaults to T1 indoor damp at "
            "low confidence with a warning. A default is not a measurement, and "
            "most MEP discipline models carry no IfcSpace at all. ENGINES: "
            "MM-001, XM-001, and CC-001 severity.",
            [
                ids.Property(
                    propertySet=PSET_ENVIRONMENT,
                    baseName=any_of(
                        [
                            "EnvironmentClass",
                            "EnvironmentalClass",
                            "CorrosivityCategory",
                            "AtmosphericEnvironment",
                        ]
                    ),
                    dataType="IFCLABEL",
                )
            ],
            "optional",
            "BG-PIPE-ENVIRONMENT",
        )
    )

    doc.specifications.append(
        spec(
            "Declared couple — second material at the junction",
            "OPTIONAL. The material of the bracket, support, hanger or fixing "
            "this element is in contact with, as a property named "
            "SecondaryMaterial, SupportMaterial, BracketMaterial or "
            "FixingMaterial, in any property set; this repository's generator "
            "writes SecondaryMaterial in Pset_BimGuardCouple. There is no "
            "buildingSMART property for this because IFC models contact through "
            "geometry, and the corrosion-relevant pairing is a design statement "
            "rather than something derivable from the pipe's own material. "
            "CONSEQUENCE IF ABSENT: the second side stays absent and is never "
            "defaulted to the element's own material; GC-001 reads a missing "
            "second material as a self-couple, which is a real verdict rather "
            "than a fault, so the audit is not blocked — it simply cannot see "
            "bimetallic junctions the model does not declare. ENGINES: GC-001.",
            [
                ids.Property(
                    propertySet=PSET_COUPLE,
                    baseName=any_of(
                        [
                            "SecondaryMaterial",
                            "SupportMaterial",
                            "BracketMaterial",
                            "FixingMaterial",
                        ]
                    ),
                    dataType="IFCLABEL",
                )
            ],
            "optional",
            "BG-PIPE-COUPLE",
        )
    )

    doc.specifications.append(
        spec(
            "Nominal diameter",
            "OPTIONAL. Nominal bore in millimetres, as a property named "
            "NominalDiameter, NominalDiameterMM, DN or Size, in any property "
            "set. CONSEQUENCE IF ABSENT: MC-001 classifies dead legs by "
            "length-to-diameter ratio, so an absent diameter degrades that "
            "classification even where a dead-leg length is present. The engine "
            "still runs. ENGINES: MC-001.",
            [
                ids.Property(
                    propertySet=PSET_OCCURRENCE,
                    baseName=any_of(
                        ["NominalDiameter", "NominalDiameterMM", "DN", "Size"]
                    ),
                    dataType="IFCREAL",
                )
            ],
            "optional",
            "BG-PIPE-DIAMETER",
        )
    )

    doc.specifications.append(
        spec(
            "Storey containment",
            "OPTIONAL. Each piping element should be contained in an "
            "IfcBuildingStorey through IfcRelContainedInSpatialStructure, and "
            "the storey should be named. CONSEQUENCE IF ABSENT: the element "
            "carries no level, which removes one of the three name hints the "
            "environment classifier uses and leaves any finding raised against "
            "the element without a floor to report it on. No engine is refused. "
            "ENGINES: MM-001, XM-001 indirectly; also the seismic audit, which "
            "reports findings per storey.",
            [
                ids.PartOf(
                    name="IFCBUILDINGSTOREY",
                    relation="IFCRELCONTAINEDINSPATIALSTRUCTURE",
                )
            ],
            "optional",
            "BG-PIPE-STOREY",
        )
    )

    doc.specifications.append(
        spec(
            "Space containment",
            "OPTIONAL. Containment in a named IfcSpace through "
            "IfcRelContainedInSpatialStructure. The space name is the strongest "
            "hint the environment classifier has: names containing pool, "
            "coastal, marine, plant, basement, kitchen, shower, laundry, "
            "external or roof all resolve to a class. CONSEQUENCE IF ABSENT: "
            "the environment falls to the storey name and then to the T1 "
            "indoor-damp default at low confidence. Most MEP discipline models "
            "carry no IfcSpace at all, which is exactly why that default "
            "exists. No engine is refused. ENGINES: MM-001, XM-001, CC-001 "
            "severity.",
            [
                ids.PartOf(
                    name="IFCSPACE",
                    relation="IFCRELCONTAINEDINSPATIALSTRUCTURE",
                )
            ],
            "optional",
            "BG-PIPE-SPACE",
        )
    )

    # Every property specification carries the same caveat about the set name,
    # generated from the set it actually names so the two can never drift.
    for specification in doc.specifications:
        for requirement in specification.requirements:
            if isinstance(requirement, ids.Property):
                specification.description += PSET_NOTE.format(
                    pset=requirement.propertySet
                )

    return doc


def main(argv: list[str] | None = None) -> int:
    """Build the IDS, write it, and report what went in.

    Returns:
        ``0`` on success, ``1`` if ifctester reports the document invalid
        against the IDS 1.0 schema.
    """
    parser = argparse.ArgumentParser(
        description="Build the BIMGUARD AI piping intake IDS from its definition."
    )
    parser.add_argument(
        "--date",
        required=True,
        help=(
            "date stamped into the IDS header, as YYYY-MM-DD. Required, so the "
            f"output never depends on the clock. The committed IDS carries "
            f"{COMMITTED_DATE}."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"where to write the IDS (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args(argv)
    if not _ISO_DATE.match(args.date):
        parser.error(f"--date must be YYYY-MM-DD, got {args.date!r}")

    document = build(args.date)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    valid = document.to_xml(str(args.out))

    required = sum(1 for s in document.specifications if s.get_usage() == "required")
    print(f"schema validation: {valid}")
    print(f"specifications: {len(document.specifications)}")
    print(f"required: {required}  optional: {len(document.specifications) - required}")
    print(f"date: {args.date}")
    print(f"wrote {args.out}")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
