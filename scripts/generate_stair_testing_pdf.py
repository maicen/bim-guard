"""Generate the Stair Testing Property Reference PDF.

One-off documentation generator (not part of the runtime app) that dumps
every stair/landing/railing property BIM-Guard can extract into a single
structured PDF, for use when preparing or reviewing a test IFC model. The
property lists here are transcribed directly from their sources of truth --
docs/ifc-property-mapping.md (standard IFC / custom Shared Parameter
properties) and app/modules/ifc_reader/__init__.py's _STAIR_DERIVED_PROPERTIES
dict plus app/modules/ifc_reader/ifc_stair.py's module docstring (engine-
derived geometry properties and known v1 limitations) -- update this script
if those sources change, rather than letting the PDF drift out of sync.

Usage: uv run python scripts/generate_stair_testing_pdf.py
Output: docs/reference/stair_testing_properties.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT_PATH = Path("docs/reference/stair_testing_properties.pdf")

HEADER_BG = colors.HexColor("#0071e3")
ROW_ALT_BG = colors.HexColor("#f5f5f5")
GRID_COLOR = colors.HexColor("#cccccc")
GROUP_BG = colors.HexColor("#dbe9fb")

styles = getSampleStyleSheet()
cell_style = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7, leading=8.5)
cell_bold = ParagraphStyle("cellBold", parent=cell_style, fontName="Helvetica-Bold")


def P(text: str, bold: bool = False) -> Paragraph:
    return Paragraph(text, cell_bold if bold else cell_style)


def make_table(header: list[str], rows: list[list], col_widths: list[float], group_rows: set[int] = frozenset()) -> Table:
    data = [[P(h, bold=True) for h in header]]
    for row in rows:
        data.append([cell if isinstance(cell, Paragraph) else P(str(cell)) for cell in row])
    table = Table(data, colWidths=[w * mm for w in col_widths], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT_BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for r in group_rows:
        style.append(("BACKGROUND", (0, r + 1), (-1, r + 1), GROUP_BG))
        style.append(("SPAN", (0, r + 1), (-1, r + 1)))
    table.setStyle(TableStyle(style))
    return table


# ---------------------------------------------------------------------------
# Table 1: Standard IFC properties + custom Shared Parameters
# ---------------------------------------------------------------------------

TABLE1_HEADER = ["IFC Class", "BIM-Guard Property", "IFC Source", "Export Requirement", "Notes"]
TABLE1_ROWS = [
    ["IfcStairFlight", "RiserHeight", "Pset_StairFlightCommon.RiserHeight", "IFC Common Property Sets", "Direct match"],
    ["IfcStairFlight", "TreadDepth", "Pset_StairFlightCommon.TreadLength", "IFC Common Property Sets", "Name mismatch — rule aliases to TreadLength automatically"],
    ["IfcStairFlight", "HeadroomClearance", "Pset_StairFlightCommon.RequiredHeadroom", "IFC Common Property Sets", "Name mismatch, aliased — superseded by engine-computed MinHeadroom (Table 2) for most checks"],
    ["IfcStairFlight", "NumberOfRiser / NumberOfTreads", "Pset_StairFlightCommon", "IFC Common Property Sets", "Exported automatically; not yet consumed by a shipped rule"],
    ["IfcStairFlight / IfcStair", "NosingLength", "Pset_StairFlightCommon.NosingLength", "IFC Common Property Sets", "Aliases: Nosing, NosingProjection, NosingDepth"],
    ["IfcStairFlight / IfcStair", "WaistThickness", "No standard property", "Custom Shared Parameter", "Aliases: Waist, StairWaist — needs a Shared Param mapped via the user-defined Pset file"],
    ["IfcStairFlight / IfcStair", "WalkingLineOffset", "No standard property", "Custom Shared Parameter", "Aliases: WalklineOffset, WalkLineOffset"],
    ["IfcStair", "HandicapAccessible", "No standard property", "Custom Shared Parameter", "Aliases: Accessible, IsAccessible, AccessibleRoute"],
    ["IfcStair", "HasNonSkidSurface", "No standard property", "Custom Shared Parameter", "Aliases: NonSkidSurface, SlipResistant, SlipResistance, AntiSlip"],
    ["IfcStair", "FireExit", "No standard property", "Custom Shared Parameter", "Aliases: IsFireExit, EmergencyExit"],
    ["IfcStairFlight", "Width", "No standard property", "Custom Shared Parameter", "See BIMGuard_UserDefinedPsets.txt (Pset_BIMGuardStairFlight)"],
    ["IfcStairFlight", "FlightHeight", "No standard property", "Custom Shared Parameter", "See BIMGuard_UserDefinedPsets.txt"],
    ["IfcStairFlight", "WinderTurnAngle / IndividualWinderAngle / WinderSetSeparation", "No standard property", "Custom Shared Parameter", "See BIMGuard_UserDefinedPsets.txt — winder-specific, no automatic geometric equivalent yet"],
    ["IfcRailing", "Reference / IsExternal", "Pset_RailingCommon", "IFC Common Property Sets", "Exported automatically; not yet consumed by a shipped rule"],
    ["IfcRailing", "PredefinedType", "Direct IFC attribute", "Always exported", "HANDRAIL vs GUARDRAIL/BALUSTRADE/FENCE/unset — gates which railing checks apply (Table 2, Group F)"],
    ["IfcRailing", "Height / HandrailHeight", "No standard property", "Custom Shared Parameter", "See BIMGuard_UserDefinedPsets.txt (Pset_BIMGuardRailing)"],
    ["IfcSlab (landing)", "FireRating", "Pset_SlabCommon.FireRating", "IFC Common Property Sets", "Direct match"],
    ["IfcSlab (landing)", "MaxSlope", "Pset_SlabCommon.PitchAngle", "IFC Common Property Sets", "Name mismatch — rule aliases to PitchAngle"],
    ["IfcSlab (landing)", "HeadroomClearance", "No standard property", "Custom Shared Parameter", "Superseded by engine-computed MinHeadroom (Table 2) for most checks"],
    ["IfcSlab (landing)", "Width — DO NOT USE for clear width", "Qto_SlabBaseQuantities.Width", "Base Quantities", "Landmine: this is slab THICKNESS on every IfcSlab, landings included — never clear walking width. Use LandingClearWidth (Table 2) instead"],
]

# ---------------------------------------------------------------------------
# Table 2: Engine-derived geometry properties (ifc_stair.py / IFCStairEngine)
# ---------------------------------------------------------------------------

TABLE2_HEADER = ["BIM-Guard Property", "Measures", "Unit"]

GROUP_A = "Group A — Per-flight riser/tread geometry (worst value within THIS flight)"
ROWS_A = [
    ["MinRiserHeight / MaxRiserHeight", "Smallest / largest riser height detected in the flight", "mm"],
    ["RiserHeightDifference", "Spread between the smallest and largest riser in the flight", "mm"],
    ["MinTreadDepth / MaxTreadDepth", "Smallest / largest tread going (nosing-to-nosing) in the flight", "mm"],
    ["TreadDepthDifference (alias GoingDifference)", "Spread between the smallest and largest going in the flight", "mm"],
    ["MinClearStairWidth (alias MinClearWidth)", "Narrowest lateral clearance sampled along the flight's run — catches a local pinch point, not just the overall footprint width", "mm"],
    ["OpenRiserDetected (alias OpenRiser)", "Whether any tread-to-tread transition lacks a closed riser face", "boolean"],
    ["TotalFlightRise / TotalFlightRun", "Overall vertical rise / horizontal run of the whole flight", "mm"],
    ["FlightPitch", "Overall flight angle from rise/run", "deg"],
    ["FlightSlopedLength", "Straight-line sloped length of the flight (hypotenuse of rise/run)", "mm"],
    ["NumberOfTreadsDetected / NumberOfRisersDetected", "Count of tread-top bands / mid-flight risers actually detected in the mesh", "count"],
    ["FlightStartElevation / FlightEndElevation", "Absolute Z elevation at the bottom / top of the flight", "mm"],
    ["RiserHeights / TreadDepths", "Full per-step lists (every riser / every going), not just min-max-difference — for exists/documented checks, not numeric thresholds", "list of mm"],
    ["StepFormulaMin / StepFormulaMax", "Smallest / largest per-step riser+going stride value (2×riser + going), paired per transition — not mixed from the flight's separate riser/going extremes", "mm"],
    ["StepFormulaValues", "Full per-step 2×riser+going list, paired with that same transition's own riser/going", "list of mm"],
]

GROUP_B = "Group B — Headroom (whole-model overhead search)"
ROWS_B = [
    ["MinHeadroom", "Worst vertical clearance found above the flight's walking line or the landing's centroid, searched against every nearby slab/beam/flight/covering/roof in the model", "mm"],
    ["MinHeadroomLimitingGlobalId", "GlobalId of the element causing that worst clearance", "GUID"],
]

GROUP_C = "Group C — Whole-stairway uniformity (every flight of the same IfcStair pooled)"
ROWS_C = [
    ["StairRiserHeightDifference", "Riser spread across ALL flights of this stairway, not just one flight", "mm"],
    ["StairTreadDepthDifference", "Going spread across ALL flights of this stairway", "mm"],
    ["StairFlightCount", "Number of flights pooled into this stairway's uniformity figures", "count"],
]

GROUP_D = "Group D — Cross-referencing (flight ↔ landing ↔ railing ↔ stair linkage)"
ROWS_D = [
    ["ParentStairGlobalId", "GlobalId of the IfcStair this flight/landing/railing belongs to (resolved by decomposition or proximity matching)", "GUID"],
    ["LandingBelow / LandingAbove", "GlobalId of the landing connecting below / above this flight", "GUID"],
    ["ConnectsFlightBelow / ConnectsFlightAbove", "GlobalId of the flight a landing connects below / above it", "GUID"],
    ["LandingLevelMismatch", "Worst elevation gap between a landing and the flight(s) it's matched to", "mm"],
    ["HandrailCountOnFlight / GuardCountOnFlight", "Number of HANDRAIL-type / guard-type railings matched to this flight", "count"],
    ["HostElementGlobalId", "GlobalId of the flight or landing a railing is matched to (nearest by plan proximity)", "GUID"],
]

GROUP_E = "Group E — Landing geometry (IfcSlab, PredefinedType = LANDING)"
ROWS_E = [
    ["LandingClearWidth / LandingClearLength", "Min-rotated-rectangle clear walking dimensions of the landing's own footprint mesh (NOT Qto_SlabBaseQuantities.Width — see Table 1 landmine)", "mm"],
    ["LandingClearArea", "Landing footprint area", "mm²"],
    ["LandingElevation", "Absolute Z elevation of the landing's top surface", "mm"],
    ["LandingSlope", "Tilt of the landing's own walking surface (isolated top faces only, not the whole slab's bounding box — avoids misreading slab thickness as slope)", "deg"],
]

GROUP_F = "Group F — Handrail / guard geometry (IfcRailing / IfcHandRail)"
ROWS_F = [
    ["HandrailMinHeight / HandrailMaxHeight", "Lowest / highest top-of-rail elevation relative to the walking surface, sampled along the rail's run", "mm"],
    ["HandrailHeightVariation", "Spread between the highest and lowest top elevation sampled", "mm"],
    ["HandrailPathLength", "Straight-line run-axis length of the rail (undercounts a curved rail — flagged in warnings when curvature is detected)", "mm"],
    ["HandrailContinuousSegments", "Number of physically continuous material segments detected along the run", "count"],
    ["HandrailMaxGapLength", "Length of the largest real break between continuous segments", "mm"],
    ["HandrailGapLocations", "Run-axis (start, end) position of every detected gap", "list of mm pairs"],
    ["HandrailMinBottomElevation", "Lowest bottom-of-rail elevation sampled", "mm"],
    ["BottomClearGap", "Median clear gap between the rail's bottom member and the walking surface (median, not minimum — avoids floor-anchored posts masking a real elevated gap)", "mm"],
    ["HandrailProfileLateral / HandrailProfileVertical", "Coarse cross-section width / height of the rail profile near mid-run", "mm"],
    ["MaxOpening", "Guard-type railings only: largest horizontal infill/baluster gap found across several sampled heights", "mm"],
    ["GuardMaxOpening", "Guard-type railings only: the worse of MaxOpening and BottomClearGap, for a single “worst opening anywhere” check", "mm"],
    ["HandrailExtensionBottom / HandrailExtensionTop", "How far this rail's own path reaches past its host flight's bottom / top tread nosing, projected onto the flight's own walking direction. Positive extends past that end; negative falls short of reaching it (a real, worse condition, not clipped to zero)", "mm"],
]

ALIAS_HEADER = ["Rule Property Name", "Also Tries (resolved automatically)", "IFC Class"]
ALIAS_ROWS = [
    ["NosingLength", "Nosing, NosingProjection, NosingDepth", "IfcStairFlight, IfcStair"],
    ["WaistThickness", "Waist, StairWaist", "IfcStairFlight, IfcStair"],
    ["HandicapAccessible", "Accessible, IsAccessible, AccessibleRoute", "IfcStair"],
    ["HasNonSkidSurface", "NonSkidSurface, SlipResistant, SlipResistance, AntiSlip", "IfcStair"],
    ["Headroom", "RequiredHeadroom, HeadroomClearance, ClearHeight, ClearanceHeight", "IfcStair"],
    ["WalkingLineOffset", "WalklineOffset, WalkLineOffset", "IfcStairFlight, IfcStair"],
    ["FireExit", "IsFireExit, EmergencyExit", "IfcStair"],
]

LIMITATIONS = [
    "Winder / curved flights: overall turning angle and rise/run still resolve, but per-winder tread depth at the inner / walking-line / outer edges is not yet computed. A lateral tread-centroid drift beyond ~75mm is detected internally and flags the flight's warnings as “winder suspected”, but this flag is not yet exposed as a queryable rule property.",
    "Guards (MaxOpening / GuardMaxOpening): computed as the largest horizontal gap at a sampled height, not a true multi-directional sphere-passing simulation. Baluster centre-to-centre spacing and the triangular stair-nosing opening are not yet computed as their own figures.",
    "Handrail/guard path length (HandrailPathLength) is a straight-line run-axis approximation; a curved rail's true swept length is undercounted (flagged in warnings when curvature is detected).",
    "Headroom (MinHeadroom) is sampled at discrete points — one per detected tread nosing for a flight, one at the plan centroid for a landing — not scanned continuously across the full walking surface. An obstruction that misses every sample point is not caught.",
    "Whole-stairway uniformity (Group C) requires flights to actually resolve to the same stairway, either via a real IfcStair decomposition relationship or proximity-based fallback grouping — flights that don't group correctly report uniformity figures for themselves alone.",
]

DIAGNOSTIC_ONLY = [
    "Curvature drift distance and the “winder suspected” flag (surfaced only in the element's warnings text)",
    "Per-height opening gap series behind MaxOpening (only the worst value is exposed as a property)",
    "The exact XYZ location of the worst headroom clearance point (only the limiting element's GlobalId is exposed)",
    "Per-tread nosing world coordinates, per-tread elevations, and open-riser run positions (used internally for headroom sampling and warning text)",
    "Each element's own world bounding box (used internally for cross-referencing; not itself a rule property)",
]


def build_pdf() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="BIM-Guard Stair Testing - Property Reference",
    )

    story = [
        Paragraph("BIM-Guard Stair Testing — Property Reference", styles["Title"]),
        Paragraph(
            "Every stair, landing, and railing/handrail property BIM-Guard can extract or "
            "compute, for use when preparing or reviewing a test IFC model. Covers "
            "IfcStairFlight, IfcStair, IfcSlab (PredefinedType = LANDING), and IfcRailing / "
            "IfcHandRail.",
            styles["Normal"],
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            "Two extraction layers feed these properties. <b>Layer 1</b> (Table 1) is read "
            "directly from the IFC file — standard property sets/quantities plus custom "
            "Shared Parameters — and depends entirely on Revit export settings (see the "
            "IFC Export Setting page). <b>Layer 2</b> (Table 2) is computed by BIM-Guard's "
            "own mesh-based stair geometry engine at analysis time; it needs correctly "
            "tessellated geometry for real IfcStairFlight/IfcRailing/IfcSlab(LANDING) "
            "entities, but no Revit-side property mapping at all.",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
        Paragraph("Table 1 — Standard IFC Properties &amp; Custom Shared Parameters", styles["Heading2"]),
        make_table(TABLE1_HEADER, TABLE1_ROWS, [28, 42, 45, 30, 65]),
        Spacer(1, 6 * mm),
    ]

    story.append(Paragraph("Table 2 — Engine-Derived Geometry Properties", styles["Heading2"]))

    def group_block(title: str, rows: list[list[str]]) -> KeepTogether:
        header_row = [P(title, bold=True), "", ""]
        combined = [header_row] + rows
        t = make_table(TABLE2_HEADER, combined, [55, 130, 20], group_rows={0})
        return KeepTogether(t)

    story.append(group_block(GROUP_A, ROWS_A))
    story.append(Spacer(1, 3 * mm))
    story.append(group_block(GROUP_B, ROWS_B))
    story.append(Spacer(1, 3 * mm))
    story.append(group_block(GROUP_C, ROWS_C))
    story.append(Spacer(1, 3 * mm))
    story.append(group_block(GROUP_D, ROWS_D))
    story.append(Spacer(1, 3 * mm))
    story.append(group_block(GROUP_E, ROWS_E))
    story.append(Spacer(1, 3 * mm))
    story.append(group_block(GROUP_F, ROWS_F))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Alias Resolution (already handled automatically — no rule or Revit change needed)", styles["Heading2"]))
    story.append(make_table(ALIAS_HEADER, ALIAS_ROWS, [45, 100, 55]))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Known v1 Limitations", styles["Heading2"]))
    story.append(
        ListFlowable(
            [ListItem(Paragraph(item, styles["Normal"]), bulletColor=HEADER_BG) for item in LIMITATIONS],
            bulletType="bullet",
        )
    )
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Computed Internally but Not Yet Queryable by Name", styles["Heading2"]))
    story.append(
        ListFlowable(
            [ListItem(Paragraph(item, styles["Normal"]), bulletColor=HEADER_BG) for item in DIAGNOSTIC_ONLY],
            bulletType="bullet",
        )
    )
    story.append(Spacer(1, 6 * mm))

    story.append(
        Paragraph(
            "See also: frontend/public/downloads/IFC_Export_Setting.json, "
            "BIMGuard_UserDefinedPsets.txt, and README.md for how to configure a Revit "
            "export that populates Table 1's properties, and docs/ifc-property-mapping.md "
            "for the full cross-domain property mapping reference.",
            styles["Italic"],
        )
    )

    doc.build(story)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
