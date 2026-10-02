"""
ifc_reader.py
--------------------
IFC model reader for BIMGuard compliance checking.

Extraction depth (all four gaps addressed):

  1. Rich property values
       - Data type (IfcReal, IfcInteger, IfcLabel, …)
       - Unit of measure from the property definition
       - Nominal / lower / upper bounds from IfcPropertyBoundedValue
       - Enumeration lists from IfcPropertyEnumeratedValue

  2. Relationships
       - Spatial containment (storey, space)
       - Element type object (IfcDoorType, IfcWallType, …) + its properties
       - Parent/child decomposition (aggregates)

  3. Material / composition
       - IfcMaterial (single material name)
       - IfcMaterialLayerSet / LayerSetUsage (layers with thickness)
       - IfcMaterialConstituentSet (named constituents)

  4. Direct attributes vs. properties
       - Pset properties searched first (nominated set → all sets → Qto sets)
       - Direct IFC attributes (e.g. OverallHeight, OverallWidth) as final fallback
       - element.get_info() exposes every schema-defined attribute

The public interface of extract_for_compliance() is unchanged so Module 4
continues to work — it now additionally receives richer per-element metadata.
"""

import json
import time
from collections import Counter
from pathlib import Path

from app.logging_config import get_logger
from app.modules.room_types import ROOM_SCOPE_KEYS

logger = get_logger(__name__)

try:
    import ifcopenshell
    import ifcopenshell.util.element

    _IFCOPENSHELL_AVAILABLE = True
except ImportError:
    _IFCOPENSHELL_AVAILABLE = False

try:
    from .ifc_geometry import IFCGeometryExtractor
    _GEOMETRY_AVAILABLE = True
except ImportError:
    _GEOMETRY_AVAILABLE = False

try:
    from .ifc_spatial import (
        IFCSpatialAdjacency,
        _element_matches_location,
        check_daylight_ratios,
        check_door_space_connection,
        check_egress_window_openings,
        check_fire_separation,
        check_garage_separation,
    )
    _SPATIAL_AVAILABLE = True
except ImportError:
    _SPATIAL_AVAILABLE = False

try:
    from .ifc_rooms import (
        ROOM_DERIVED_PROPERTIES,
        ROOM_LINK_PROPERTIES,
        ElementRoomLinker,
        room_context,
        room_derived_value,
    )
    _ROOMS_AVAILABLE = True
except ImportError:
    _ROOMS_AVAILABLE = False

try:
    from .ifc_egress import IFCEgressGraph, check_egress_travel_distance, check_exit_count
    _EGRESS_AVAILABLE = True
except ImportError:
    _EGRESS_AVAILABLE = False

try:
    from .ifc_penetrations import build_interference_index, penetration_context
    _PENETRATIONS_AVAILABLE = True
except ImportError:
    _PENETRATIONS_AVAILABLE = False

#: Rule property names (lower-cased, separators stripped) answered from the
#: opening an element fills, mapped to which side of that relationship they
#: read. Kept in step with ``_RELATIONSHIP_LOOKUPS`` in ``rule_reliability``.
_OPENING_RELATIONSHIP_PROPERTIES: dict[str, str] = {
    "openingglobalid": "opening_global_id",
    "openingelement": "opening_global_id",
    "ifcopeningelement": "opening_global_id",
    "fillsvoids": "opening_global_id",
    "fillsopening": "opening_global_id",
    "openingifcclass": "opening_ifc_class",
    "hostglobalid": "host_global_id",
    "hostelement": "host_global_id",
    "hostifcclass": "host_ifc_class",
}


def _opening_relationship_value(el, field: str) -> tuple[object, dict]:
    """Read ``field`` off the openings ``el`` fills (IfcRelFillsElement).

    The host is the element each opening voids (IfcRelVoidsElement), usually
    a wall. Several openings or hosts join with ", ". Returns ``(None, {})``
    when the element fills no opening.
    """
    openings = []
    try:
        for rel in getattr(el, "FillsVoids", None) or []:
            opening = getattr(rel, "RelatingOpeningElement", None)
            if opening is not None:
                openings.append(opening)
    except Exception as exc:  # noqa: BLE001 - a malformed relationship must not fail the rule run
        logger.debug("Opening lookup failed for %s: %s", el, exc)
        return None, {}
    if not openings:
        return None, {}

    hosts = []
    for opening in openings:
        for rel in getattr(opening, "VoidsElements", None) or []:
            host = getattr(rel, "RelatingBuildingElement", None)
            if host is not None:
                hosts.append(host)

    values = {
        "opening_global_id": [o.GlobalId for o in openings],
        "opening_ifc_class": [o.is_a() for o in openings],
        "host_global_id": [h.GlobalId for h in hosts],
        "host_ifc_class": [h.is_a() for h in hosts],
    }[field]
    if not values:
        return None, {}
    detail = {
        "relationship": "IfcRelFillsElement",
        "opening_global_ids": [o.GlobalId for o in openings],
        "host_global_ids": [h.GlobalId for h in hosts],
    }
    return ", ".join(dict.fromkeys(values)), detail


try:
    from .ifc_stair import IFCStairEngine, stair_context
    _STAIR_AVAILABLE = True
except ImportError:
    _STAIR_AVAILABLE = False

try:
    from .ifc_quality.validator import IFCValidator

    _QUALITY_TOOLS_AVAILABLE = True
except ImportError:
    _QUALITY_TOOLS_AVAILABLE = False

# Minimum quality score (0-100) that triggers a Projects-page improvement warning.
IFC_MIN_QUALITY_SCORE = 70


# ── IFC class fallback map ────────────────────────────────────────────────────
# Revit and some other authoring tools export the *container* class rather than
# the sub-element class that buildingSMART rules target.  When by_type(target)
# returns nothing, try each fallback in order.  For IfcStair specifically we
# also walk IsDecomposedBy to recover the individual IfcStairFlight children.
_IFC_CLASS_FALLBACKS: dict[str, list[str]] = {
    # IfcStair first (container -> flight decomposition, handled specially
    # below), then the generic proxy bucket for stairs a bad export dropped
    # to IfcBuildingElementProxy entirely — filtered by _PROXY_RECLASSIFY_HINTS.
    "IfcStairFlight":      ["IfcStair", "IfcBuildingElementProxy"],
    "IfcRampFlight":       ["IfcRamp"],
    "IfcRailing":          ["IfcHandRail", "IfcMember", "IfcBuildingElementProxy"],
    "IfcSlab":             ["IfcPlate", "IfcFooting"],
    "IfcSpace":            ["IfcZone"],
    "IfcSanitaryTerminal": ["IfcFlowTerminal"],
    "IfcAlarm":            ["IfcSensor"],
    # Roofs are often modelled as IfcSlab with PredefinedType=ROOF
    "IfcRoof":             ["IfcSlab"],
    # Structural members may be exported as beams or columns
    "IfcMember":           ["IfcBeam", "IfcColumn"],
    # Ceilings may be exported as generic IfcBuildingElementProxy
    "IfcCovering":         ["IfcBuildingElementProxy"],
    # Curtain walls may fall back to IfcWall in older exports
    "IfcCurtainWall":      ["IfcWall"],
    # Furniture may be exported as generic proxy elements
    "IfcFurnishingElement": ["IfcBuildingElementProxy"],
    # Doors/windows are sometimes exported as generic proxies too — unlike the
    # fallbacks above, IfcBuildingElementProxy is a catch-all bucket that can
    # hold anything (furniture, MEP, unclassified junk), so treating every
    # proxy in the model as a door would apply door-width/height checks to
    # unrelated elements. _PROXY_RECLASSIFY_HINTS below filters this bucket
    # down to only the proxies that actually look like the target class.
    "IfcDoor":   ["IfcBuildingElementProxy"],
    "IfcWindow": ["IfcBuildingElementProxy"],
}

# Name/ObjectType/Tag/PredefinedType keyword hints used to filter the generic
# IfcBuildingElementProxy bucket down to elements that plausibly are the
# target class, when the fallback class is that catch-all bucket. See
# _matches_reclass_hint().
_PROXY_RECLASSIFY_HINTS: dict[str, list[str]] = {
    "IfcDoor":        ["door"],
    "IfcWindow":      ["window", "glazing", "glaze"],
    "IfcStairFlight": ["stair", "step", "flight"],
    "IfcRailing":     ["railing", "handrail", "guard", "guardrail", "balustrade"],
}

# ── Property alias map ────────────────────────────────────────────────────────
# When the nominated property_name is absent, try these alternate names before
# giving up.  Covers Revit parameter naming variations and IFC schema aliases.
_PROPERTY_ALIASES: dict[str, list[str]] = {
    "OverallWidth":     ["Width", "ClearWidth", "NominalWidth", "GrossWidth", "NetWidth"],
    "OverallHeight":    ["Height", "ClearHeight", "NominalHeight", "GrossHeight", "NetHeight"],
    "Width":            ["OverallWidth", "ClearWidth", "NominalWidth", "GrossWidth"],
    "Height":           ["OverallHeight", "ClearHeight", "NominalHeight", "GrossHeight"],
    "TreadLength":      ["TreadDepth", "GoingType", "Going", "TreadRun", "StepDepth"],
    # Reverse of TreadLength above: "TreadDepth" is the more common colloquial
    # name a rule author is likely to type, but Pset_StairFlightCommon's own
    # schema property is spelled "TreadLength" -- a rule authored as
    # "TreadDepth" would otherwise never try the canonical schema name.
    "TreadDepth":       ["TreadLength", "GoingType", "Going", "TreadRun", "StepDepth"],
    "RiserHeight":      ["RiserType", "Riser", "RiserHeightType", "StepHeight"],
    "RequiredHeadroom": ["HeadroomClearance", "Headroom", "ClearHeight", "ClearanceHeight"],
    # Reverse of RequiredHeadroom above: Pset_StairFlightCommon's own property
    # is spelled "Headroom" (not "RequiredHeadroom", which is Pset_StairCommon's
    # name on the IfcStair container) — a rule authored as "Headroom" against
    # IfcStair would otherwise never try the container-level name.
    "Headroom":         ["RequiredHeadroom", "HeadroomClearance", "ClearHeight", "ClearanceHeight"],
    "HandrailHeight":   ["Height", "RailingHeight", "BarrierHeight"],
    "Area":             ["ClearOpeningArea", "GrossArea", "NetArea", "OpeningArea"],
    "RequiredSlope":    ["Slope", "PitchAngle", "SlopeAngle", "Gradient"],
    "PitchAngle":       ["Slope", "RequiredSlope", "SlopeAngle", "Gradient"],
    "FireRating":       ["FireResistanceRating", "FireResistance", "REI", "FRR"],
    "LongName":         ["Name", "SpaceName", "RoomName"],
    "ModelNumber":      ["ModelReference", "ModelLabel"],
    "OpeningDirection": ["OperationType"],
    # Pset_StairCommon / Pset_StairFlightCommon name variants a rule author
    # (human or the LLM rule-builder) is likely to type instead of the exact
    # IFC schema property name.
    "NosingLength":       ["Nosing", "NosingProjection", "NosingDepth"],
    "WaistThickness":     ["Waist", "StairWaist"],
    "HandicapAccessible": ["Accessible", "IsAccessible", "AccessibleRoute"],
    "HasNonSkidSurface":  ["NonSkidSurface", "SlipResistant", "SlipResistance", "AntiSlip"],
    "WalkingLineOffset":  ["WalklineOffset", "WalkLineOffset"],
    "FireExit":           ["IsFireExit", "EmergencyExit"],
    # Revit's door/window instance parameters, exported with their spaces
    # intact (in the "Constraints" set when Revit property sets are on).
    # Both are measured from the host level, like the geometry fallback.
    "SillHeight":         ["Sill Height"],
    "HeadHeight":         ["Head Height"],
    # NOTE: deliberately NOT aliasing a landing's clear width to
    # Qto_SlabBaseQuantities' "Width" — that Qto property is slab THICKNESS,
    # not the landing's clear walking width, on every IfcSlab including
    # PredefinedType=LANDING. A rule wanting clear width must ask for
    # "ClearWidth", which already routes to the geometry-derived corridor
    # width instead (see ifc_geometry._GEOMETRY_PROPERTY_MAP). See
    # docs/ifc-property-mapping.md.
}


#: Clear (net passage) dimensions of a door or window, by normalised rule
#: property name. They depend on the frame, leaf and stop, which Revit exports
#: empty (IfcDoorLiningProperties / IfcWindowLiningProperties carry no
#: dimensions), so they are read only from a value the model actually
#: provides -- never estimated from the overall size or the element's
#: bounding box. Each maps to the other authored names accepted for it.
_FRAME_DEPENDENT_PROPERTIES: dict[str, tuple[str, ...]] = {
    "clearwidth": ("DoorClearOpeningWidth", "ClearOpeningWidth"),
    "doorclearopeningwidth": ("ClearWidth",),
    "clearopeningwidth": ("ClearWidth",),
    "clearopeningheight": (),
    "clearopeningarea": (),
}


def _frame_dependent_missing_reason(el) -> str:
    """Why a door/window clear dimension could not be read, for the result row."""
    kind = "door" if el.is_a("IfcDoor") else "window"
    lining_cls = "IfcDoorLiningProperties" if kind == "door" else "IfcWindowLiningProperties"
    return (
        f"Clear opening is not in the model: the {kind}'s frame width is missing "
        f"({lining_cls} was exported without dimensions), so it cannot be worked out "
        f"from the {kind}'s overall size. Add the clear dimension as a property on the "
        f"{kind} (e.g. through the BIM Guard property-mapping file)."
    )


# ── Length measure IFC types ──────────────────────────────────────────────────
# Values with these NominalValue types are in model length units and must be
# scaled to mm before Module 4 comparison when the model is not in mm.
_LENGTH_MEASURE_TYPES: frozenset[str] = frozenset([
    "IfcPositiveLengthMeasure",
    "IfcLengthMeasure",
    "IfcNonNegativeLengthMeasure",
])

# Direct IFC schema attributes that are always length values (metres-based model
# stores them in metres, mm-based model in mm).  Used when rich property metadata
# is not available (Pass 3 / 4 direct attribute lookups, and the Pass 5 / 6
# alias / fallback routes, which never populate rich_detail at all — see the
# comment at the Pass 8 call site). Keep this in sync with the length-typed
# entries in _PROPERTY_ALIASES above and ifc_geometry.py's
# _GEOMETRY_PROPERTY_MAP, since a name matched via either of those but missing
# here would silently skip unit conversion.
_LENGTH_DIRECT_ATTRS: frozenset[str] = frozenset([
    "overallwidth", "overallheight", "width", "height",
    "treadlength", "treaddepth", "going", "riserheight",
    "handrailheight", "sillheight", "headheight", "headroomclearance",
    "requiredheadroom", "headroom", "clearwidth", "nominalwidth", "nominalheight",
    "clearheight", "elevationwithflooring",
    "grosswidth", "grossheight", "netwidth", "netheight",
    "thickness", "length", "depth",
    "corridorwidth", "minimumwidth", "passagewidth",
    "perimeter", "footprintperimeter",
    "diameter", "nominaldiameter",
    "nosinglength", "waistthickness", "walkinglineoffset",
    "treadlengthatoffset", "treadlengthatinnerside",
])

# ── IFC property-type → Python type label ────────────────────────────────────
_IFC_TYPE_MAP = {
    "IfcReal": "real",
    "IfcInteger": "integer",
    "IfcBoolean": "boolean",
    "IfcLogical": "boolean",
    "IfcLabel": "string",
    "IfcText": "string",
    "IfcIdentifier": "string",
    "IfcPositiveLengthMeasure": "real",
    "IfcLengthMeasure": "real",
    "IfcAreaMeasure": "real",
    "IfcVolumeMeasure": "real",
    "IfcPlaneAngleMeasure": "real",
    "IfcCountMeasure": "integer",
    "IfcMassMeasure": "real",
    "IfcTimeMeasure": "real",
    "IfcThermalTransmittanceMeasure": "real",
}



#: Per-riser/tread/handrail/guard geometry produced by ifc_stair's mesh
#: decomposition, never a Pset key: a Pset carries at most ONE nominal value
#: for a whole flight (RiserHeight, TreadLength), while these are the WORST
#: value across every individual step -- exactly the numbers a code check
#: actually needs (a flight with one bad riser among twelve good ones still
#: fails on that one riser).
#:
#: Value is either a plain field name (read off the element's own stair
#: context -- a flight, landing, or railing) or a (nested_key, field) pair
#: for whole-stairway aggregates nested under "stair_uniformity" (see
#: ifc_stair.IFCStairEngine.get_stair_uniformity -- pools every flight of
#: the same IfcStair, not just one).
#: Keys deliberately carry NO unit suffix, matching how every other
#: property_name in this file is written (RiserHeight, HandrailHeight,
#: TreadLength, ...). A rule's `unit` column, not its property_name, states
#: mm/deg/m2.
_STAIR_DERIVED_PROPERTIES: dict[str, str | tuple[str, str]] = {
    # Per-flight: worst riser/going within THIS flight.
    "minriserheight": "min_riser_mm",
    "maxriserheight": "max_riser_mm",
    "riserheightdifference": "riser_difference_mm",
    "mintreaddepth": "min_going_mm",
    "maxtreaddepth": "max_going_mm",
    "treaddepthdifference": "going_difference_mm",
    "goingdifference": "going_difference_mm",
    "minclearstairwidth": "min_clear_width_mm",
    "minclearwidth": "min_clear_width_mm",
    "openriserdetected": "open_riser",
    "openriser": "open_riser",
    "totalflightrise": "total_rise_mm",
    "totalflightrun": "total_run_mm",
    "flightpitch": "pitch_deg",
    "flightslopedlength": "sloped_length_mm",
    "numberoftreadsdetected": "tread_count",
    "numberofrisersdetected": "riser_count",
    "flightstartelevation": "start_elevation_mm",
    "flightendelevation": "end_elevation_mm",
    # Raw per-step lists (not just the min/max/difference above) -- for a
    # rule that wants to see or report every individual value, via `exists`/
    # `documented` rather than a numeric threshold (a list isn't itself a
    # number to compare).
    "riserheights": "risers_mm",
    "treaddepths": "goings_mm",
    # Combined riser+going stride formula (2*riser + going), per step --
    # see derive_flight_steps' docstring for why this is checked pairwise
    # per transition rather than from the flight's own separate min/max.
    "stepformulamin": "min_step_formula_mm",
    "stepformulamax": "max_step_formula_mm",
    "stepformulavalues": "step_formula_mm",
    # Headroom (IFCStairEngine._compute_headroom): worst overhead clearance
    # found near this flight's walking line, and what's causing it -- a
    # whole-model search, not just this element's own geometry, so it can
    # catch the flight above in a switchback/scissor stair as well as an
    # ordinary floor slab or beam.
    "minheadroom": "min_headroom_mm",
    "minheadroomlimitingglobalid": "min_headroom_limiting_guid",
    # Whole-stairway (every flight of the same IfcStair pooled together) --
    # codes require riser/tread uniformity across the WHOLE stairway, not
    # just within one flight.
    "stairriserheightdifference": ("stair_uniformity", "riser_difference_mm"),
    "stairtreaddepthdifference": ("stair_uniformity", "going_difference_mm"),
    "stairflightcount": ("stair_uniformity", "flight_count"),
    # Cross-referencing (ifc_stair.IFCStairEngine._link_elements): which
    # stair/flight/landing this element connects to or runs alongside.
    # ParentStairGlobalId reads the same "stair_guid" field regardless of
    # whether the element is a flight, a landing, or a railing.
    "parentstairglobalid": "stair_guid",
    "landingbelow": "landing_below_guid",
    "landingabove": "landing_above_guid",
    "handrailcountonflight": "handrail_count",
    "guardcountonflight": "guard_count",
    # Landing (IfcSlab, PredefinedType=LANDING). Deliberately named
    # "LandingClearWidth", not "Width" -- see the Qto_SlabBaseQuantities
    # landmine documented in docs/ifc-property-mapping.md.
    "landingclearwidth": "clear_width_mm",
    "landingclearlength": "clear_length_mm",
    "landingcleararea": "clear_area_mm2",
    "landingelevation": "elevation_mm",
    "landingslope": "slope_deg",
    "connectsflightbelow": "connects_flight_below_guid",
    "connectsflightabove": "connects_flight_above_guid",
    "landinglevelmismatch": "level_mismatch_mm",
    # Handrail / guard (IfcRailing).
    "handrailminheight": "min_height_mm",
    "handrailmaxheight": "max_height_mm",
    "handrailheightvariation": "top_elevation_variation_mm",
    "handrailpathlength": "path_length_mm",
    "handrailcontinuoussegments": "continuous_segments",
    "handrailminbottomelevation": "min_bottom_elevation_mm",
    "handrailprofilelateral": "profile_lateral_mm",
    "handrailprofilevertical": "profile_vertical_mm",
    "handrailgaplocations": "gap_locations_mm",
    "handrailmaxgaplength": "max_gap_length_mm",
    "bottomcleargap": "bottom_clear_gap_mm",
    "hostelementglobalid": "host_element_guid",
    # Guard opening / baluster spacing -- guard-type IfcRailing only (see
    # ifc_stair.analyze_railing's is_guard_like gate). MaxOpening is the
    # largest horizontal infill gap found (baluster/post spacing);
    # GuardMaxOpening also folds in BottomClearGap, so a single rule can
    # check "the worst opening anywhere on this guard" without querying
    # both. Neither is a true multi-directional sphere-passing simulation --
    # see the module docstring's v1 limitations.
    "maxopening": "max_opening_mm",
    "guardmaxopening": "guard_max_opening_mm",
    # How far this rail's own path reaches past its host flight's bottom/top
    # tread nosing (IFCStairEngine._set_handrail_extension) -- positive
    # extends past that end, negative falls short of reaching it.
    "handrailextensionbottom": "extension_bottom_mm",
    "handrailextensiontop": "extension_top_mm",
}


def _resolve_scaled_bound(raw_value: float, scale: float, offset: float) -> float:
    """Resolve a property-relative rule bound: (raw_value * scale) + offset, rounded to 4dp.

    Pure so the arithmetic behind value_min_property/value_max_property's
    scale+offset resolution (extract_for_compliance) is directly unit
    testable without an IFC model fixture. scale=1, offset=0 (the defaults
    for a rule written before value_min_scale/value_max_scale existed)
    reproduces the property's raw value unchanged.
    """
    return round(raw_value * scale + offset, 4)


class IFCReader:
    """Full IFC reader for Module 2 compliance extraction."""

    def __init__(self, file_path: Path | str | None = None):
        self.file_path = Path(file_path) if file_path else None
        self.ifc_file = None
        self.quality_report: dict = {}
        self.quality_warnings: list[str] = []
        self.quality_improvements: list[str] = []
        self.geometry_extractor: "IFCGeometryExtractor | None" = None
        self.spatial_adjacency: "IFCSpatialAdjacency | None" = None
        self.room_linker: "ElementRoomLinker | None" = None
        self.egress_graph: "IFCEgressGraph | None" = None
        self._stair_engine: "IFCStairEngine | None" = None
        self._stair_engine_built = False
        # Per-run memo of per-element lookups; see _memo(). None outside
        # extract_for_compliance, so no other caller ever sees cached data.
        self._element_memo: dict[tuple[str, int], object] | None = None
        if self.file_path:
            self.load_ifc_file()

    @property
    def stair_engine(self) -> "IFCStairEngine | None":
        """Stair geometry analysis, built on first use.

        It meshes every flight, landing and railing in the model (~13s on a
        large one), and only rules that read a stair-derived property need it.
        """
        if not self._stair_engine_built:
            self._stair_engine_built = True
            if _STAIR_AVAILABLE and self.geometry_extractor is not None and self.ifc_file is not None:
                t0 = time.monotonic()
                self._stair_engine = IFCStairEngine(
                    self.ifc_file, self.geometry_extractor
                ).build()
                logger.info("IFC stage=stair-engine elapsed=%.2fs", time.monotonic() - t0)
        return self._stair_engine

    # ── Core load / schema helpers ────────────────────────────────────────────

    def load_ifc_file(self):
        if not _IFCOPENSHELL_AVAILABLE:
            raise ImportError("ifcopenshell is not installed.")
        if not self.file_path or not self.file_path.exists():
            raise FileNotFoundError(f"IFC file not found: {self.file_path}")

        load_path = self.file_path
        self.quality_report: dict = {}
        self.quality_warnings: list[str] = []
        self.quality_improvements: list[str] = []

        timings: dict[str, float] = {}

        def _timed(stage, fn):
            t0 = time.monotonic()
            try:
                return fn()
            finally:
                timings[stage] = time.monotonic() - t0
                logger.info(
                    "IFC load stage=%s elapsed=%.2fs", stage, timings[stage]
                )

        if self.ifc_file is None:
            self.ifc_file = _timed(
                "ifcopenshell-open", lambda: ifcopenshell.open(str(load_path))
            )
        if _QUALITY_TOOLS_AVAILABLE:
            results = _timed(
                "quality-validate",
                lambda: IFCValidator(str(load_path), ifc_file=self.ifc_file).validate(),
            )
            self.quality_report = results
            score = results.get("overall", {}).get("score", 100)

            if score < IFC_MIN_QUALITY_SCORE:
                self.quality_warnings.append(
                    f"IFC quality is low ({score:.1f}%). Run Quality Improvements "
                    "from the Projects page before analysis."
                )
            elif score < 80:
                self.quality_warnings.append(
                    f"IFC quality is fair ({score:.1f}%). "
                    "Consider running the IFC improver for better results."
                )

        if _GEOMETRY_AVAILABLE:
            self.geometry_extractor = _timed(
                "geometry-extractor", lambda: IFCGeometryExtractor(self.ifc_file)
            )
        if _SPATIAL_AVAILABLE:
            self.spatial_adjacency = _timed(
                "spatial-adjacency",
                lambda: IFCSpatialAdjacency(
                    self.ifc_file, geometry_extractor=self.geometry_extractor
                ).build(),
            )
        if _ROOMS_AVAILABLE and self.spatial_adjacency is not None:
            self.room_linker = _timed(
                "room-linker",
                lambda: ElementRoomLinker(
                    self.spatial_adjacency,
                    self.ifc_file,
                    geometry_extractor=self.geometry_extractor,
                ),
            )
            # Room names are left exactly as the model's author wrote them; a
            # name that looks like a misspelling is reported, with a suggested
            # fix, instead of being quietly reinterpreted.
            self.quality_warnings.extend(self.room_linker.rooms.warning_messages())
        if _EGRESS_AVAILABLE and self.spatial_adjacency is not None:
            self.egress_graph = _timed(
                "egress-graph",
                lambda: IFCEgressGraph(
                    self.spatial_adjacency, geometry_extractor=self.geometry_extractor
                ).build(),
            )
        logger.info(
            "IFC load complete total=%.2fs stages=%s",
            sum(timings.values()),
            {k: round(v, 2) for k, v in timings.items()},
        )
        return self.ifc_file

    def get_all_elements(self, ifc_type: str = "IfcBuildingElement") -> list:
        if not self.ifc_file:
            raise ValueError("No IFC file loaded.")
        return self.ifc_file.by_type(ifc_type)

    def _resolve_building_elements(self) -> list:
        for ifc_type in ("IfcBuildingElement", "IfcBuiltElement", "IfcElement"):
            try:
                return self.ifc_file.by_type(ifc_type)
            except Exception:
                continue
        return []

    def extract_properties(self, element) -> dict:
        """Return simplified {pset_name: {prop: value}} dict (legacy method)."""
        return ifcopenshell.util.element.get_psets(element)

    # ── Gap 1: Rich property extraction ──────────────────────────────────────

    def extract_rich_properties(self, element) -> dict[str, dict]:
        """
        Return the full property tree for one element.

        Structure:
          {
            "<PsetName>": {
              "<PropName>": {
                "value":       scalar_value,
                "value_type":  "real" | "integer" | "string" | "boolean" | "enum" | "bounded",
                "unit":        "mm" | "m²" | … | None,
                "lower_bound": float | None,
                "upper_bound": float | None,
                "enum_values": [str, …] | None,
                "ifc_type":    "IfcPropertySingleValue" | …
              }
            }
          }
        """
        result: dict[str, dict] = {}
        for rel in getattr(element, "IsDefinedBy", []):
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if pdef.is_a("IfcPropertySet"):
                pset_data = {}
                for prop in getattr(pdef, "HasProperties", []):
                    pset_data[prop.Name] = self._parse_ifc_property(prop)
                result[pdef.Name] = pset_data
            elif pdef.is_a("IfcElementQuantity"):
                # Qto_ quantity sets
                qset_data = {}
                for qty in getattr(pdef, "Quantities", []):
                    qset_data[qty.Name] = self._parse_ifc_quantity(qty)
                result[pdef.Name] = qset_data
        return result

    def _parse_ifc_property(self, prop) -> dict:
        """Decode one IFC property into a rich dict."""
        ifc_type = prop.is_a()

        if ifc_type == "IfcPropertySingleValue":
            nv = prop.NominalValue
            if nv is None:
                return {"value": None, "value_type": "null", "unit": None,
                        "ifc_type": ifc_type, "measure_type": None}
            raw = getattr(nv, "wrappedValue", nv)
            vtype = _IFC_TYPE_MAP.get(nv.is_a(), "string")
            unit_label = self._resolve_unit(getattr(prop, "Unit", None))
            return {
                "value": raw,
                "value_type": vtype,
                "unit": unit_label,
                "lower_bound": None,
                "upper_bound": None,
                "enum_values": None,
                "ifc_type": ifc_type,
                "measure_type": nv.is_a(),  # e.g. "IfcPositiveLengthMeasure"
            }

        if ifc_type == "IfcPropertyBoundedValue":
            lo = (
                getattr(prop.LowerBoundValue, "wrappedValue", None)
                if prop.LowerBoundValue
                else None
            )
            hi = (
                getattr(prop.UpperBoundValue, "wrappedValue", None)
                if prop.UpperBoundValue
                else None
            )
            sp = (
                getattr(prop.SetPointValue, "wrappedValue", None)
                if getattr(prop, "SetPointValue", None)
                else None
            )
            return {
                "value": sp if sp is not None else lo,
                "value_type": "bounded",
                "unit": self._resolve_unit(getattr(prop, "Unit", None)),
                "lower_bound": lo,
                "upper_bound": hi,
                "enum_values": None,
                "ifc_type": ifc_type,
            }

        if ifc_type == "IfcPropertyEnumeratedValue":
            values = [getattr(v, "wrappedValue", v) for v in (prop.EnumerationValues or [])]
            return {
                "value": values[0] if values else None,
                "value_type": "enum",
                "unit": None,
                "lower_bound": None,
                "upper_bound": None,
                "enum_values": values,
                "ifc_type": ifc_type,
            }

        # IfcPropertyListValue, IfcPropertyTableValue, etc.
        return {"value": str(prop), "value_type": "complex", "unit": None, "ifc_type": ifc_type}

    def _parse_ifc_quantity(self, qty) -> dict:
        """Decode one IFC quantity (area, length, count, …)."""
        for attr in (
            "LengthValue",
            "AreaValue",
            "VolumeValue",
            "WeightValue",
            "CountValue",
            "TimeValue",
        ):
            v = getattr(qty, attr, None)
            if v is not None:
                return {
                    "value": v,
                    "value_type": "real",
                    "unit": attr.replace("Value", "").lower(),
                    "ifc_type": qty.is_a(),
                }
        return {"value": None, "value_type": "unknown", "ifc_type": qty.is_a()}

    def _resolve_unit(self, unit_ref) -> str | None:
        """Convert an IfcUnit reference to a human-readable label."""
        if unit_ref is None:
            return None
        try:
            ifc_t = unit_ref.is_a()
            if ifc_t == "IfcSIUnit":
                prefix = getattr(unit_ref, "Prefix", None) or ""
                name = getattr(unit_ref, "Name", "") or ""
                _SI_ABBREV = {
                    "METRE": "m",
                    "SQUARE_METRE": "m²",
                    "CUBIC_METRE": "m³",
                    "GRAM": "g",
                    "SECOND": "s",
                    "AMPERE": "A",
                    "KELVIN": "K",
                    "RADIAN": "rad",
                    "STERADIAN": "sr",
                    "HERTZ": "Hz",
                    "NEWTON": "N",
                    "PASCAL": "Pa",
                }
                _PREFIX = {
                    "MILLI": "m",
                    "CENTI": "c",
                    "KILO": "k",
                    "MEGA": "M",
                }
                abbrev = _SI_ABBREV.get(name, name.lower())
                return f"{_PREFIX.get(prefix, '')}{abbrev}" if abbrev else None
            if ifc_t == "IfcConversionBasedUnit":
                return getattr(unit_ref, "Name", None)
            if ifc_t == "IfcContextDependentUnit":
                return getattr(unit_ref, "Name", None)
        except Exception:
            pass
        return None

    # ── Gap 2: Relationships ──────────────────────────────────────────────────

    def get_spatial_location(self, element) -> dict:
        """
        Return the spatial context of an element.

        Returns:
            {storey_name, storey_elevation, space_name, building_name}
        """
        storey_name = storey_elev = space_name = building_name = None
        try:
            for rel in getattr(element, "ContainedInStructure", []):
                container = rel.RelatingStructure
                if container.is_a("IfcSpace"):
                    space_name = getattr(container, "LongName", None) or getattr(
                        container, "Name", None
                    )
                if container.is_a("IfcBuildingStorey"):
                    storey_name = getattr(container, "Name", None)
                    storey_elev = getattr(container, "Elevation", None)
                if container.is_a("IfcBuilding"):
                    building_name = getattr(container, "Name", None)
            # Walk up for storey if only space was found
            if space_name and storey_name is None:
                for rel in getattr(element, "ContainedInStructure", []):
                    cont = rel.RelatingStructure
                    for rel2 in getattr(cont, "Decomposes", []):
                        parent = rel2.RelatingObject
                        if parent.is_a("IfcBuildingStorey"):
                            storey_name = getattr(parent, "Name", None)
        except Exception:
            pass
        return {
            "storey_name": storey_name,
            "storey_elevation": float(storey_elev) if storey_elev is not None else None,
            "space_name": space_name,
            "building_name": building_name,
        }

    def get_type_info(self, element) -> dict:
        """
        Return the element's type object and its properties.

        Returns:
            {type_name, type_guid, type_properties: {pset: {prop: value}}}
        """
        type_name = type_guid = None
        type_props: dict = {}
        try:
            el_type = ifcopenshell.util.element.get_type(element)
            if el_type:
                type_name = getattr(el_type, "Name", None)
                type_guid = getattr(el_type, "GlobalId", None)
                type_props = self.extract_rich_properties(el_type)
        except Exception:
            pass
        return {
            "type_name": type_name,
            "type_guid": type_guid,
            "type_properties": type_props,
        }

    def get_decomposition(self, element) -> dict:
        """
        Return immediate parent and children in the decomposition hierarchy.

        Returns:
            {parent_name, parent_type, children: [{name, type, guid}]}
        """
        parent_name = parent_type = None
        children: list[dict] = []
        try:
            for rel in getattr(element, "Decomposes", []):
                parent = rel.RelatingObject
                parent_name = getattr(parent, "Name", None)
                parent_type = parent.is_a()
            for rel in getattr(element, "IsDecomposedBy", []):
                for child in rel.RelatedObjects:
                    children.append(
                        {
                            "name": getattr(child, "Name", None),
                            "type": child.is_a(),
                            "guid": child.GlobalId,
                        }
                    )
        except Exception:
            pass
        return {
            "parent_name": parent_name,
            "parent_type": parent_type,
            "children": children,
        }

    # ── Gap 3: Material / composition ─────────────────────────────────────────

    def get_material_info(self, element) -> dict:
        """
        Return material data for an element.

        Returns:
            {
              material_type: "single" | "layer_set" | "constituent_set" | "profile_set" | "none",
              layers: [{name, thickness_mm, category}],
              materials: [str],  # flat material name list
            }
        """
        layers: list[dict] = []
        material_names: list[str] = []
        mat_type = "none"

        try:
            # should_inherit is ifcopenshell's default today, but stated
            # explicitly: a pipe's material commonly sits on its
            # IfcPipeSegmentType, and a future default flip would
            # silently empty `materials` for every such element.
            mat = ifcopenshell.util.element.get_material(
                element, should_inherit=True
            )
            if mat is None:
                return {"material_type": "none", "layers": [], "materials": []}

            t = mat.is_a()

            if t == "IfcMaterial":
                mat_type = "single"
                material_names = [mat.Name or ""]

            elif t in ("IfcMaterialLayerSet", "IfcMaterialLayerSetUsage"):
                mat_type = "layer_set"
                layer_set = mat.ForLayerSet if t == "IfcMaterialLayerSetUsage" else mat
                for layer in getattr(layer_set, "MaterialLayers", []):
                    name = (
                        getattr(layer.Material, "Name", "Unknown") if layer.Material else "Unknown"
                    )
                    thickness = getattr(layer, "LayerThickness", None)
                    category = getattr(layer, "Category", None)
                    layers.append(
                        {
                            "name": name,
                            "thickness_mm": float(thickness) if thickness is not None else None,
                            "category": category,
                        }
                    )
                    material_names.append(name)

            elif t == "IfcMaterialConstituentSet":
                mat_type = "constituent_set"
                for constituent in getattr(mat, "MaterialConstituents", []):
                    name = (
                        getattr(constituent.Material, "Name", "Unknown")
                        if constituent.Material
                        else "Unknown"
                    )
                    fraction = getattr(constituent, "Fraction", None)
                    layers.append(
                        {
                            "name": name,
                            "fraction": float(fraction) if fraction is not None else None,
                            "category": getattr(constituent, "Category", None),
                        }
                    )
                    material_names.append(name)

            elif t == "IfcMaterialProfileSet":
                mat_type = "profile_set"
                for profile in getattr(mat, "MaterialProfiles", []):
                    name = (
                        getattr(profile.Material, "Name", "Unknown")
                        if profile.Material
                        else "Unknown"
                    )
                    material_names.append(name)

        except Exception:
            pass

        return {
            "material_type": mat_type,
            "layers": layers,
            "materials": material_names,
        }

    # ── Gap 4: Direct IFC attributes ──────────────────────────────────────────

    def get_direct_attributes(self, element) -> dict:
        """
        Return all schema-defined direct attributes of an element.

        Unlike Pset properties these are encoded directly in the IFC entity:
        e.g. IfcDoor.OverallHeight, IfcWindow.OverallWidth, IfcSlab.PredefinedType

        Excludes relationship handles (those are object references, not values).
        GlobalId is kept: rules such as "every window must have a GlobalId"
        resolve it through this method, like any other schema attribute.
        """
        try:
            info = element.get_info()
        except Exception:
            return {}

        _SKIP = {
            "id",
            "type",
            "OwnerHistory",
            "ObjectPlacement",
            "Representation",
            "HasAssignments",
            "IsDecomposedBy",
            "Decomposes",
            "HasAssociations",
            "IsDefinedBy",
            "ReferencedBy",
            "ContainedInStructure",
            "ConnectedTo",
            "ConnectedFrom",
            "FillsVoids",
            "HasOpenings",
        }
        result = {}
        for k, v in info.items():
            if k in _SKIP:
                continue
            if v is None:
                continue
            # Keep only scalar values — skip IFC object references
            if isinstance(v, (str, int, float, bool)):
                result[k] = v
            elif isinstance(v, tuple):
                # Coordinate tuples (IfcCartesianPoint), enum values, etc.
                result[k] = list(v)
        return result

    # ── Extraction helpers ────────────────────────────────────────────────────

    def _get_elements_with_fallback(self, target: str) -> list:
        """
        Return IFC elements for *target* class.

        If the direct lookup returns nothing, walk _IFC_CLASS_FALLBACKS.
        For the IfcStair → IfcStairFlight case, decompose the stair containers
        to get the individual flight sub-elements.
        """
        try:
            elements = list(self.ifc_file.by_type(target))
        except Exception:
            elements = []

        if elements:
            return elements

        for fallback_cls in _IFC_CLASS_FALLBACKS.get(target, []):
            try:
                candidates = list(self.ifc_file.by_type(fallback_cls))
            except Exception:
                continue

            if not candidates:
                continue

            # Special case: IfcStair container → decompose into IfcStairFlight
            if target == "IfcStairFlight" and fallback_cls == "IfcStair":
                flights = []
                for stair in candidates:
                    for rel in getattr(stair, "IsDecomposedBy", []):
                        for child in rel.RelatedObjects:
                            if child.is_a("IfcStairFlight"):
                                flights.append(child)
                if flights:
                    return flights
                # No explicit flights found — use the stair containers themselves
                return candidates

            # Generic proxy bucket: filter down to elements that actually look
            # like the target class instead of returning every proxy in the
            # model (see _PROXY_RECLASSIFY_HINTS docstring above).
            hint_keywords = _PROXY_RECLASSIFY_HINTS.get(target)
            if fallback_cls == "IfcBuildingElementProxy" and hint_keywords:
                matched = [c for c in candidates if self._matches_reclass_hint(c, hint_keywords)]
                if matched:
                    return matched
                continue

            return candidates

        return []

    def _matches_reclass_hint(self, element, keywords: list[str]) -> bool:
        """Return True if element's name/type fields hint at one of *keywords*.

        Used to reclassify generic IfcBuildingElementProxy elements that a
        model exported instead of the proper IfcDoor/IfcWindow class, so they
        aren't silently dropped from compliance checks entirely. See
        _matched_reclass_keyword() for which fields are checked.
        """
        return self._matched_reclass_keyword(element, keywords) is not None

    def _class_fallback_warning(self, el, target: str) -> str | None:
        """Return a data-quality caveat if the model does not classify *el* as *target*.

        Returns None when *el* really is a *target*. Otherwise the caveat names
        the class it is modelled as.

        _get_elements_with_fallback() substitutes other IFC classes when the
        model has no *target* elements at all, and the result is merged into
        the normal element list -- without this caveat a reclassified
        IfcBuildingElementProxy is indistinguishable in the results from a
        properly-typed IfcDoor/IfcWindow. Kept free of any ruleset or clause
        reference: it describes the element, not the rule that reached it.
        """
        try:
            if el.is_a(target):
                return None
            actual_class = el.is_a()
        except Exception:
            return None

        advice = "Confirm it is the intended element, or reclassify it in the authoring tool."
        if actual_class == "IfcBuildingElementProxy":
            keyword = self._matched_reclass_keyword(
                el, _PROXY_RECLASSIFY_HINTS.get(target) or []
            )
            if keyword:
                return (
                    f"Modelled as IfcBuildingElementProxy, not {target}: included "
                    f'because its name/type mentions "{keyword}". {advice}'
                )
            # A proxy class with no keyword hints (e.g. IfcCovering) takes every
            # proxy in the model -- the weakest evidence a fallback can give.
            return (
                f"Modelled as IfcBuildingElementProxy, not {target}: every proxy "
                f"in the model is treated as {target}, with no name/type check. "
                f"{advice}"
            )
        return (
            f"Modelled as {actual_class}, not {target}: evaluated as {target} "
            f"through a class fallback because the model has no {target} "
            f"elements. {advice}"
        )

    def _matched_reclass_keyword(self, element, keywords: list[str]) -> str | None:
        """Return the first of *keywords* that *element* hints at, or None.

        Checks Name/ObjectType/Tag/PredefinedType — or its type object's Name
        (e.g. a Revit family/type like "Door-Single-36in") — for a
        case-insensitive substring match against *keywords*.
        """
        fields = [
            getattr(element, "Name", None),
            getattr(element, "ObjectType", None),
            getattr(element, "Tag", None),
            getattr(element, "PredefinedType", None),
        ]
        try:
            el_type = ifcopenshell.util.element.get_type(element)
            if el_type:
                fields.append(getattr(el_type, "Name", None))
        except Exception:
            pass

        haystack = " ".join(str(f) for f in fields if f).lower()
        return next((kw for kw in keywords if kw in haystack), None)

    @staticmethod
    def _lookup_in_psets(psets: dict, prop_name: str):
        """Return (value, pset_name) for the first hit of prop_name in psets."""
        for ps_name, props in psets.items():
            if isinstance(props, dict) and prop_name in props:
                v = props[prop_name]
                if v is not None:
                    return v, ps_name
        return None, None

    @staticmethod
    def _door_space_rich_detail(door_space_connection: dict | None) -> dict:
        """Rich-metadata payload for ConnectedSpaces/ConnectedSpaceCount, for
        future display/debugging — the resolver only surfaces this data, it
        never uses it to decide pass/fail (the rule's own operator does).
        """
        d = door_space_connection or {}
        return {
            "source": "IfcRelSpaceBoundary",
            "connected_space_guids": d.get("connected_space_guids", []),
            "connected_space_names": d.get("connected_space_names", []),
            "connected_space_count": d.get("connected_space_count", 0),
            "expected_count": d.get("expected_count"),
            "is_external": d.get("is_external"),
            "has_data": d.get("has_data", False),
            "spatial_status": d.get("status"),
            "interior_single_space_mismatch": d.get("interior_single_space_mismatch", False),
        }

    @staticmethod
    def _room_link_detail(room: dict | None) -> dict:
        """Return the provenance payload for a room-derived value.

        Names which evidence linked the element to its rooms, so a finding can
        say how it knows.
        """
        r = room or {}
        return {
            "link_source": r.get("link_source"),
            "connected_room_guids": r.get("room_guids") or [],
            "connected_room_types": r.get("room_types") or [],
            "warnings": [],
        }

    @classmethod
    def _needs_room_context(
        cls,
        prop_name: str,
        scope: dict,
        exceptions: list[dict],
    ) -> bool:
        """Whether this rule needs the element's room links resolved.

        Room resolution reads relationships (and, for a door or window with no
        boundary of its own, a wall and some bounding boxes), so it must not run
        for the rules that never ask about a room. Gated on the rule asking for
        a room-derived property, or naming a room predicate in its scope or any
        of its waivers.
        """
        if not _ROOMS_AVAILABLE:
            return False
        normalized = str(prop_name or "").replace("_", "").replace(" ", "").lower()
        if normalized in ROOM_DERIVED_PROPERTIES or normalized in ROOM_LINK_PROPERTIES:
            return True
        for predicate in [scope] + [e.get("predicate") or {} for e in exceptions]:
            if ROOM_SCOPE_KEYS & set(predicate or {}):
                return True
        return False

    @staticmethod
    def _needs_space_counts(prop_name: str) -> bool:
        """Whether the property is one of the per-room element counts."""
        normalized = str(prop_name or "").replace("_", "").replace(" ", "").lower()
        return ROOM_DERIVED_PROPERTIES.get(normalized, "") in (
            "DoorCount",
            "WindowCount",
            "WallCount",
            "SlabCount",
        )

    def _door_clear_opening_width(self, el) -> tuple[float | None, dict]:
        """Return a door's clear opening width in mm, as authored in the model.

        Only a stated value counts (see ``_FRAME_DEPENDENT_PROPERTIES``):
        returns ``(None, detail)`` with a ``missing_reason`` otherwise. Shared
        with the SHACL graph enrichment so both paths agree on the value.
        """
        value, _found, detail = self._resolve_element_property(
            el, "DoorClearOpeningWidth", unit_scale_mm=self._get_length_unit_scale_mm()
        )
        return value, detail

    # ── Reusable single-property resolution cascade ──────────────────────────

    # ── Per-run element memo ──────────────────────────────────────────────────
    #
    # WHY: extract_for_compliance evaluates every rule against every element of
    # its target class, so one door is read once per door rule (dozens of
    # times). The lookups below -- psets, rich property metadata, direct
    # attributes, type, spatial location, materials -- depend only on the
    # element, never on the rule, yet were recomputed on every visit;
    # ifcopenshell's get_psets alone was ~30s of a 25s-wall-clock extraction
    # on a 14 MB model. Memoising them per element makes the cost proportional
    # to elements, not rules x elements.
    #
    # The memo lives only for one extract_for_compliance call (the model is
    # not modified during a run) and is dropped afterwards, so readers used
    # for anything else never see cached values. Cached values are shared:
    # treat them as read-only and copy before mutating. A lookup that raises
    # is not cached, so callers' existing try/except fallbacks behave as before.

    def _memo(self, kind: str, el, compute):
        """Return ``compute(el)``, memoised per element for the current run."""
        memo = getattr(self, "_element_memo", None)  # tests may skip __init__
        if memo is None:
            return compute(el)
        key = (kind, el.id())
        if key in memo:
            return memo[key]
        value = compute(el)
        memo[key] = value
        return value

    def _psets(self, el) -> dict:
        """``get_psets(el, psets_only=False)`` (Psets + Qtos), memoised per run."""
        return self._memo(
            "psets", el, lambda e: ifcopenshell.util.element.get_psets(e, psets_only=False)
        )

    def _type_of(self, el):
        """``get_type(el)``, memoised per run (may be None)."""
        return self._memo("type", el, ifcopenshell.util.element.get_type)

    def _rich_properties(self, el) -> dict:
        """:meth:`extract_rich_properties`, memoised per run."""
        return self._memo("rich", el, self.extract_rich_properties)

    def _direct_attributes(self, el) -> dict:
        """:meth:`get_direct_attributes`, memoised per run."""
        return self._memo("direct", el, self.get_direct_attributes)

    def _resolve_element_property(
        self,
        el,
        prop_name: str,
        prop_set: str = "",
        fallback_prop: str = "",
        spatial: dict | None = None,
        material_info: dict | None = None,
        door_space_connection: dict | None = None,
        penetration: dict | None = None,
        stair: dict | None = None,
        room: dict | None = None,
        unit_scale_mm: float = 1.0,
    ) -> tuple[object, "str | None", dict]:
        """
        Resolve one property value for one element via the resolution cascade
        (relationship shortcut -> instance Pset -> rich metadata -> direct
        attribute -> type-level Pset -> alias -> fallback_property ->
        geometry -> unit conversion).

        Used both for a rule's main property and for property-referencing
        bounds (value_min_property / value_max_property), which is why this
        is factored out rather than left inline in extract_for_compliance().

        Returns (actual_value, found_pset, rich_detail).
        """
        spatial = spatial or {}
        actual_value = None
        found_pset = None
        rich_detail: dict = {}

        if not prop_name:
            return actual_value, found_pset, rich_detail

        # ── Pass 0: relationship-derived properties ────────────────────────
        # Storey containment (IfcRelContainedInSpatialStructure) and material
        # assignment (IfcRelAssociatesMaterial) are IFC *relationships*, not
        # Pset properties — no amount of Pset searching below would ever find
        # a rule asking for "Storey" or "Material". get_spatial_location() /
        # get_material_info() already resolve these for the same element
        # elsewhere in extract_for_compliance(); short-circuit to that data
        # instead of falling through to passes that can never succeed.
        prop_lower_name = prop_name.strip().lower()
        # Separators stripped as well, for the derived-property maps below.
        # `_needs_support_context` already gates on this form, so without it a
        # rule written with underscores rather than PascalCase would pay for
        # the traversal and then fail to read it.
        prop_key_name = prop_lower_name.replace("_", "").replace(" ", "").replace("-", "")
        # A door/window clear dimension is read only where the model states
        # it: its own aliases replace the generic ones, and the geometry pass
        # is skipped (a bounding box measures the frame, not the clear gap).
        frame_dependent = prop_key_name in _FRAME_DEPENDENT_PROPERTIES and (
            el.is_a("IfcDoor") or el.is_a("IfcWindow")
        )
        if prop_lower_name in ("storey", "level", "buildingstorey", "floor"):
            storey_name = spatial.get("storey_name")
            if storey_name:
                return storey_name, "spatial:storey", rich_detail
        elif prop_lower_name == "material":
            materials = (material_info or {}).get("materials") or []
            if materials:
                return ", ".join(materials), "material:relationship", rich_detail
        elif prop_key_name in _OPENING_RELATIONSHIP_PROPERTIES:
            # Whether a window/door sits in an opening, and in which wall, is
            # an IfcRelFillsElement -> IfcRelVoidsElement relationship, never a
            # Pset key. Falls through when the element fills no opening, so a
            # model that authors one of these names as a real property still
            # has it read by Pass 1.
            value, detail = _opening_relationship_value(el, _OPENING_RELATIONSHIP_PROPERTIES[prop_key_name])
            if value is not None:
                return value, "relationship:fills_opening", detail
        elif prop_lower_name in ("connectedspaces", "spaceconnection", "connectedspacenames", "doorconnectedspaces"):
            names = (door_space_connection or {}).get("connected_space_names") or []
            if names:
                dsc_rich = self._door_space_rich_detail(door_space_connection)
                return ", ".join(names), "spatial:door_space_connection", dsc_rich
            # Not a door (or a door with no boundary data): every other
            # element class answers from its room links instead.
            room_names = (room or {}).get("rooms")
            if room_names:
                return ", ".join(room_names), "spatial:room_link", self._room_link_detail(room)
        elif prop_lower_name in ("connectedspacecount", "spaceconnectioncount", "numberofconnectedspaces", "connectedspacescount"):
            if door_space_connection is not None:
                dsc_rich = self._door_space_rich_detail(door_space_connection)
                return door_space_connection.get("connected_space_count", 0), "spatial:door_space_connection", dsc_rich
            room_names = (room or {}).get("rooms")
            if room_names:
                return len(room_names), "spatial:room_link", self._room_link_detail(room)
        elif prop_lower_name in ("interiorsinglespacemismatch", "interiorsinglespaceflag", "spaceconnectionmismatch"):
            if door_space_connection is not None:
                dsc_rich = self._door_space_rich_detail(door_space_connection)
                return (
                    bool(door_space_connection.get("interior_single_space_mismatch")),
                    "spatial:door_space_connection",
                    dsc_rich,
                )
        elif prop_lower_name in ("annularclearance", "annular_clearance"):
            # The radial gap between an element and the opening it passes
            # through. Like Storey and Material above, this is a relationship
            # (IfcRelFillsElement -> IfcRelVoidsElement) plus geometry, never a
            # Pset key, so no amount of Pset searching below could find it.
            #
            # Falls through when the traversal produced nothing, so a model
            # that *does* author AnnularClearance as a real property still has
            # it read from the Pset by Pass 1. Authored data beats derived.
            clearance = (penetration or {}).get("annular_clearance_mm")
            if clearance is not None:
                detail = dict((penetration or {}).get("annular_clearance_detail") or {})
                detail["unit"] = "mm"
                return clearance, "geometry:penetration", detail
        elif _ROOMS_AVAILABLE and prop_key_name in ROOM_DERIVED_PROPERTIES:
            # Room identity and what bounds a room: relationships
            # (IfcRelSpaceBoundary, containment, the wall a door fills), never
            # a Pset key. Falls through when the links could not answer, so a
            # model that authors e.g. WindowCount itself still has it read.
            value, detail = room_derived_value(prop_key_name, room)
            if value is not None:
                return value, "derived:rooms", detail
        elif prop_key_name in _STAIR_DERIVED_PROPERTIES:
            # Per-riser/tread/handrail/guard geometry: no Pset stores these,
            # since a Pset carries only one nominal value for a whole flight
            # (e.g. RiserHeight) while these are the WORST value across every
            # individual step (MinRiserHeight, RiserHeightDifference, ...),
            # resolved by ifc_stair's mesh decomposition. Falls through like
            # the other derived routes: a model that also authors the plain
            # Pset property (RiserHeight itself, not a derived min/max) still
            # gets it from Pass 1 below.
            value, detail = self._stair_derived_value(prop_key_name, stair)
            if value is not None:
                return value, "geometry:stair", detail

        # ── Pass 1: instance Psets + Qto sets (fast path) ─────────
        try:
            psets_simple = self._psets(el)
        except Exception:
            psets_simple = {}

        if prop_set and prop_set in psets_simple:
            v = psets_simple[prop_set].get(prop_name)
            if v is not None:
                actual_value = v
                found_pset = prop_set

        if actual_value is None:
            v, ps = self._lookup_in_psets(psets_simple, prop_name)
            if v is not None:
                actual_value, found_pset = v, ps

        # ── Pass 2: rich property metadata (type/unit/bounds) ─────
        if found_pset:
            try:
                rich_all = self._rich_properties(el)
                pset_key = found_pset.split(":")[-1]  # strip "type:" prefix if any
                rich_prop = rich_all.get(pset_key, {}).get(prop_name, {})
                if rich_prop:
                    # Copied: rich_all is memoised and shared by every rule
                    # that reads this element.
                    rich_detail = dict(rich_prop)
            except Exception:
                pass

        # ── Pass 3: direct IFC schema attributes ──────────────────
        if actual_value is None:
            try:
                direct = self._direct_attributes(el)
                v = direct.get(prop_name)
                if v is not None:
                    actual_value = v
                    found_pset = "direct_attribute"
            except Exception:
                pass

        # ── Pass 4: element TYPE properties ───────────────────────
        # Many Revit-exported properties (OverallWidth, FireRating, …)
        # live on the IfcDoorType / IfcWindowType, not the instance.
        if actual_value is None:
            try:
                el_type = self._type_of(el)
                if el_type:
                    type_psets = self._psets(el_type)
                    v, ps = self._lookup_in_psets(type_psets, prop_name)
                    if v is not None:
                        actual_value = v
                        found_pset = f"type:{ps}"
                    if actual_value is None:
                        type_direct = self._direct_attributes(el_type)
                        v = type_direct.get(prop_name)
                        if v is not None:
                            actual_value = v
                            found_pset = "type:direct_attribute"
            except Exception:
                pass

        # ── Pass 5: property aliases (name variations) ────────────
        if actual_value is None:
            # Fetch the type once (not per-alias) so aliases can also check
            # IfcDoorType/IfcWindowType — many Revit-exported attributes
            # (e.g. OperationType) only ever live on the type, never the
            # instance, same as Pass 4 does for the un-aliased prop_name.
            el_type_for_alias = None
            type_psets_for_alias = None
            try:
                el_type_for_alias = self._type_of(el)
                if el_type_for_alias:
                    type_psets_for_alias = self._psets(el_type_for_alias)
            except Exception:
                pass

            aliases = (
                _FRAME_DEPENDENT_PROPERTIES[prop_key_name]
                if frame_dependent
                else _PROPERTY_ALIASES.get(prop_name, [])
            )
            for alias in aliases:
                v, ps = self._lookup_in_psets(psets_simple, alias)
                if v is not None:
                    actual_value, found_pset = v, f"alias:{ps}"
                    break
                try:
                    direct = self._direct_attributes(el)
                    v = direct.get(alias)
                    if v is not None:
                        actual_value = v
                        found_pset = "alias:direct_attribute"
                        break
                except Exception:
                    pass
                if type_psets_for_alias:
                    v, ps = self._lookup_in_psets(type_psets_for_alias, alias)
                    if v is not None:
                        actual_value, found_pset = v, f"alias:type:{ps}"
                        break
                if el_type_for_alias:
                    try:
                        type_direct = self._direct_attributes(el_type_for_alias)
                        v = type_direct.get(alias)
                        if v is not None:
                            actual_value = v
                            found_pset = "alias:type:direct_attribute"
                            break
                    except Exception:
                        pass

        # ── Pass 6: rule's fallback_property field ────────────────
        if actual_value is None and fallback_prop:
            v, ps = self._lookup_in_psets(psets_simple, fallback_prop)
            if v is not None:
                actual_value, found_pset = v, f"fallback:{ps}"
            if actual_value is None:
                try:
                    direct = self._direct_attributes(el)
                    v = direct.get(fallback_prop)
                    if v is not None:
                        actual_value = v
                        found_pset = "fallback:direct_attribute"
                except Exception:
                    pass

        # ── Pass 7: bounding-box geometry (Tier 1) ───────────────
        # Only runs when all Pset/attribute passes returned nothing.
        if actual_value is None and self.geometry_extractor and not frame_dependent:
            try:
                geo_val = self.geometry_extractor.get_geometry_value(
                    el, prop_name, self.geometry_extractor.get_floor_z_mm(el)
                )
                if geo_val is not None:
                    actual_value = geo_val
                    found_pset = "geometry"
            except Exception:
                pass

        # ── Pass 8: unit conversion (model-units → mm) ───────────
        # Geometry (Pass 7) already returns mm.  Pset/attribute passes
        # return model-native units, which for metre-based models means
        # values like 0.75 instead of 750.  Scale here so Module 4
        # comparisons are always against mm values when rules use mm.
        if (
            unit_scale_mm != 1.0
            and actual_value is not None
            and found_pset != "geometry"
        ):
            # A quantity can arrive as a numeric string -- e.g. an
            # IfcLabel('1.2') where the authoring tool typed the Pset value
            # as text instead of a proper IfcLengthMeasure. Coerce it before
            # the numeric check below, otherwise it silently skips scaling
            # and gets compared raw (1.2 m evaluated as 1.2 mm).
            if isinstance(actual_value, str):
                try:
                    actual_value = float(actual_value)
                except ValueError:
                    pass
            if isinstance(actual_value, (int, float)) and not isinstance(actual_value, bool):
                measure_type = rich_detail.get("measure_type", "")
                prop_lower = prop_name.lower()
                if (measure_type in _LENGTH_MEASURE_TYPES
                        or prop_lower in _LENGTH_DIRECT_ATTRS):
                    actual_value = round(actual_value * unit_scale_mm, 4)

        if actual_value is None and frame_dependent:
            rich_detail = {**rich_detail, "missing_reason": _frame_dependent_missing_reason(el)}

        return actual_value, found_pset, rich_detail

    # ── Compliance extraction (all fallbacks) ─────────────────────────────────

    def extract_for_compliance(self, rules: list[dict]) -> list[dict]:
        """Run :meth:`_extract_for_compliance` with the per-run element memo active.

        See the "Per-run element memo" note above :meth:`_memo`.
        """
        self._element_memo = {}
        try:
            return self._extract_for_compliance(rules)
        finally:
            self._element_memo = None

    def _extract_for_compliance(self, rules: list[dict]) -> list[dict]:
        """
        For each rule, find matching IFC elements and extract the property value.

        Property search order per element:
          1. Nominated property set (property_set field in rule)
          2. All Psets and Qto_ quantity sets
          3. Direct IFC schema attributes (OverallHeight, OverallWidth, …)

        Element results now include rich metadata (type, unit, bounds, spatial
        location, materials) alongside the scalar actual_value used by Module 4.
        """
        if not self.ifc_file:
            raise ValueError("No IFC file loaded.")

        # Pre-compute once; 1.0 means model is already in mm → no scaling needed
        _unit_scale_mm = self._get_length_unit_scale_mm()

        # Per-run centroid cache, keyed by element id() (not GlobalId — cheaper
        # and every el here is a live ifcopenshell entity for this run).
        # IFCGeometryExtractor already caches the triangulated *shape* per
        # element, but get_centroid() still re-derives the vertex array and
        # re-averages it on every call — ~0.5s/element even on a cache hit.
        # The same physical element gets evaluated once per rule that targets
        # its class (e.g. 37 door rules x 6 doors), so without this second
        # cache layer a 3000-rule library turns a ~1s extraction into
        # multiple minutes, repeating that ~0.5s for every rule instead of
        # once per element. See position_mm below.
        _position_cache: dict[int, tuple | None] = {}

        # Door → connected-space data, computed once regardless of whether any
        # rule in this batch actually needs it (cheap — reuses the already-built
        # spatial_adjacency, no re-parsing). Feeds the ConnectedSpaces /
        # ConnectedSpaceCount Pass 0 shortcut below.
        door_space_lookup: dict[str, dict] = {}
        if _SPATIAL_AVAILABLE and self.spatial_adjacency:
            try:
                door_space_lookup = {
                    r["door_guid"]: r
                    for r in check_door_space_connection(self.spatial_adjacency, self.ifc_file)
                }
            except Exception:
                door_space_lookup = {}

        results = []
        total_rules = len(rules)
        logger.info(
            "Rule extraction started rules=%d property_search=nominated-pset,all-psets,quantities,direct-attributes,type-properties,aliases,geometry unit_scale_mm=%s",
            total_rules,
            _unit_scale_mm,
        )
        # Index of this batch's rules by reference, so a rule listing waivers
        # in `exceptions` can have them resolved to the predicates they stand
        # for here, where the whole rule set is in hand. Module 4 then gates
        # on plain data and never needs database access of its own.
        rules_by_reference = {
            str(r.get("reference") or "").strip(): r
            for r in rules
            if str(r.get("reference") or "").strip()
        }

        # IfcRelInterferesElements has no inverse attribute, so answering
        # "what does this pipe clash with?" means scanning the whole file.
        # Done once per run and shared across every rule and element; empty
        # for models that declare no interferences, which is most of them.
        # None until a rule needs it, so a model with no interferences is
        # scanned once rather than once per penetration rule.
        _interference_index: dict | None = None
        # Host / opening traversal per unique element, keyed by element id like
        # _position_cache above and for the same reason: the same pipe is
        # re-examined by every rule targeting IfcPipeSegment, and the traversal
        # reads geometry.
        _penetration_cache: dict[int, dict] = {}

        # Stair geometry: unlike the two traversals above, IFCStairEngine
        # there is no index to lazily construct here -- only the per-element
        # context lookup is worth caching across rules targeting the same
        # flight/landing/railing.
        _stair_cache: dict[int, dict] = {}

        # Room links per element, keyed by (element, whether counts were
        # wanted). The linker already memoises by GlobalId; this only avoids
        # rebuilding the small context dict once per rule that targets the
        # same element.
        _room_cache: dict[tuple[int, bool], dict] = {}

        for rule_index, rule in enumerate(rules, start=1):
            rule_started_at = time.monotonic()
            scope_predicate = self._decode_json_obj(rule.get("applies_when"))
            resolved_exceptions = self._resolve_exceptions(rule, rules_by_reference)
            # Properties named only by the scope or waiver predicates still
            # have to be read off each element, or the gates have nothing to
            # test against.
            scope_property_names = self._scope_property_names(
                scope_predicate, resolved_exceptions
            )
            target = str(rule.get("target_ifc_class") or "").strip()
            prop_name = str(rule.get("property_name") or "").strip()
            prop_set = str(rule.get("property_set") or "").strip()
            operator = str(rule.get("operator") or "").strip()
            fallback_prop = str(rule.get("fallback_property") or "").strip()

            # A waiver definition states the condition under which another rule
            # is excused. It makes no claim about the model on its own, so
            # evaluating it standalone would report a verdict on a requirement
            # that does not exist, surfacing as MISSING_DATA and
            # NOT_APPLICABLE rows beside the requirement it belongs to. It still stays in rules_by_reference
            # above, so the rules that cite it can resolve its predicate.
            if self._is_waiver_only(operator):
                logger.info(
                    "Rule extraction rule=%d/%d reference=%s skipped=waiver_definition operator=%s",
                    rule_index,
                    total_rules,
                    rule.get("reference") or rule.get("id") or "unknown",
                    operator,
                )
                continue

            # Host and opening traversal is only worth its cost for rules that
            # actually ask about a penetration.
            needs_penetration = _PENETRATIONS_AVAILABLE and self._needs_penetration_context(
                prop_name, scope_predicate, resolved_exceptions
            )
            if needs_penetration and _interference_index is None:
                _interference_index = build_interference_index(self.ifc_file)


            needs_stair = _STAIR_AVAILABLE and self._needs_stair_context(
                prop_name, scope_predicate, resolved_exceptions
            ) and self.stair_engine is not None

            needs_room = self.room_linker is not None and self._needs_room_context(
                prop_name, scope_predicate, resolved_exceptions
            )
            wants_space_counts = needs_room and self._needs_space_counts(prop_name)

            # A scope that names a room the model does not have is worth saying
            # so once per rule: it usually means a typo, in the model or in the
            # rule, and the suggestions say which.
            scope_warnings: list[str] = []
            if needs_room:
                for predicate in [scope_predicate] + [
                    e.get("predicate") or {} for e in resolved_exceptions
                ]:
                    for message in self.room_linker.rooms.scope_miss_warnings(predicate):
                        if message not in scope_warnings:
                            scope_warnings.append(message)
                for message in scope_warnings:
                    logger.warning(
                        "Room scope rule=%s: %s",
                        rule.get("reference") or rule.get("id") or "unknown",
                        message,
                    )
            logger.info(
                "Rule extraction rule=%d/%d reference=%s target=%s property=%s pset=%s operator=%s fallback=%s",
                rule_index,
                total_rules,
                rule.get("reference") or rule.get("id") or "unknown",
                target or "missing",
                prop_name or "none",
                prop_set or "any",
                operator or "missing",
                fallback_prop or "none",
            )

            # Property-referencing bounds — e.g. tread depth
            # must be between its own Run and Run + 25mm. Instead of a fixed
            # numeric value_min/value_max, the bound is another property on
            # the same element (optionally offset by a fixed amount).
            value_min_property = str(rule.get("value_min_property") or "").strip()
            value_max_property = str(rule.get("value_max_property") or "").strip()
            value_min_offset = self._decode_json_val(rule.get("value_min_offset")) or 0.0
            value_max_offset = self._decode_json_val(rule.get("value_max_offset")) or 0.0
            # Multiplier applied to the referenced property before the offset
            # above -- lets a bound be expressed as "0.5x the room's
            # diagonal", not just "the room's diagonal plus/minus a fixed
            # amount". Defaults to 1 (no-op) so a rule written before this
            # field existed resolves exactly as it did before.
            value_min_scale = self._decode_json_val(rule.get("value_min_scale"))
            value_min_scale = 1.0 if value_min_scale is None else value_min_scale
            value_max_scale = self._decode_json_val(rule.get("value_max_scale"))
            value_max_scale = 1.0 if value_max_scale is None else value_max_scale

            # field_consistency — another property on the SAME element that
            # prop_name's value (optionally transformed by name_pattern) must
            # match, e.g. a wall's Name must embed the same code stored in its
            # Cod_Object parameter. unique_within_scope has no second property
            # to resolve; it just needs to know how to group elements.
            compare_property = str(rule.get("compare_property") or "").strip()
            name_pattern = str(rule.get("name_pattern") or "").strip()
            uniqueness_scope = str(rule.get("uniqueness_scope") or "building").strip().lower()

            # User-configurable interpretation settings stored in the rule's
            # free-form `parameters` JSON blob (no dedicated column — avoids a
            # schema migration for settings that only a few rule types need).
            try:
                rule_params = json.loads(rule.get("parameters") or "{}")
                if not isinstance(rule_params, dict):
                    rule_params = {}
            except (json.JSONDecodeError, TypeError):
                rule_params = {}
            egress_direction = str(rule_params.get("egress_direction") or "outside").strip().lower()

            if not target or (not prop_name and operator not in ("exists", "not_exists")):
                continue

            # Use class fallback so IfcStair containers resolve to IfcStairFlight, etc.
            elements = self._get_elements_with_fallback(target)

            # applies_when.location — a rule can scope itself to only interior
            # or only exterior elements (e.g. "interior doors must connect two
            # spaces" vs "exterior doors must connect one"). General: any rule
            # with this condition gets filtered here, not special-cased per rule.
            try:
                applies_when = rule.get("applies_when")
                if isinstance(applies_when, str):
                    applies_when = json.loads(applies_when) if applies_when else {}
                if not isinstance(applies_when, dict):
                    applies_when = {}
            except (json.JSONDecodeError, TypeError):
                applies_when = {}
            location_filter = str(applies_when.get("location") or "any").strip().lower()
            if location_filter in ("interior", "exterior") and _SPATIAL_AVAILABLE:
                elements = [el for el in elements if _element_matches_location(el, location_filter)]

            # Centroids (BCF camera targets) tessellate every element; do it
            # for the whole class on all cores rather than one at a time.
            if self.geometry_extractor is not None:
                self.geometry_extractor.prefetch_centroids(
                    [el for el in elements if el.id() not in _position_cache]
                )

            element_results = []
            _sub: dict[str, float] = {}
            _tick = time.monotonic
            for el in elements:
                _t = _tick()
                # Spatial + material context fetched early — floor_z needed for
                # Pass 7 geometry, and both feed the Pass 0 relationship shortcut
                # for "Storey"/"Material" rules.
                try:
                    spatial = self._memo("spatial", el, self.get_spatial_location)
                except Exception:
                    spatial = {}
                try:
                    mat_info = self._memo("material", el, self.get_material_info)
                except Exception:
                    mat_info = {}
                door_space = door_space_lookup.get(getattr(el, "GlobalId", None))
                _t2 = _tick()
                _sub["spatial+material"] = _sub.get("spatial+material", 0.0) + (_t2 - _t)
                _t = _t2

                # Host / opening traversal: what this element passes through
                # and how much gap surrounds it. Resolved before the property
                # cascade because AnnularClearance is derived from it, the way
                # Storey and Material are derived from their relationships.
                # Cached per element -- every rule targeting the class would
                # otherwise repeat a geometry read.
                penetration: dict = {}
                if needs_penetration:
                    pen_id = el.id()
                    if pen_id in _penetration_cache:
                        penetration = _penetration_cache[pen_id]
                    else:
                        try:
                            penetration = penetration_context(
                                el,
                                geometry_extractor=self.geometry_extractor,
                                unit_scale_mm=_unit_scale_mm,
                                interference_index=_interference_index,
                                material_resolver=self.get_material_info,
                            )
                        except Exception as exc:
                            logger.debug("Penetration context failed for %s: %s", el, exc)
                            penetration = {}
                        _penetration_cache[pen_id] = penetration


                # Per-riser/tread/handrail/guard geometry, already analysed
                # once for the whole model in load_ifc_file() -- only the
                # per-element lookup is cached here, not a re-analysis.
                stair = {}
                if needs_stair:
                    stair_id = el.id()
                    if stair_id in _stair_cache:
                        stair = _stair_cache[stair_id]
                    else:
                        try:
                            stair = stair_context(el, self.stair_engine)
                        except Exception as exc:
                            logger.debug("Stair context failed for %s: %s", el, exc)
                            stair = {}
                        _stair_cache[stair_id] = stair

                # Which rooms this element connects to, and the evidence for
                # saying so. Resolved only for rules that ask about a room.
                room: dict = {}
                if needs_room:
                    room_key = (el.id(), wants_space_counts)
                    if room_key in _room_cache:
                        room = _room_cache[room_key]
                    else:
                        try:
                            room = room_context(
                                el,
                                self.room_linker,
                                include_counts=wants_space_counts,
                            )
                        except Exception as exc:
                            logger.debug("Room context failed for %s: %s", el, exc)
                            room = {}
                        _room_cache[room_key] = room

                _t2 = _tick()
                _sub["penetration+stair+room"] = _sub.get("penetration+stair+room", 0.0) + (_t2 - _t)
                _t = _t2
                actual_value, found_pset, rich_detail = self._resolve_element_property(
                    el,
                    prop_name,
                    prop_set=prop_set,
                    fallback_prop=fallback_prop,
                    spatial=spatial,
                    material_info=mat_info,
                    door_space_connection=door_space,
                    penetration=penetration,
                    stair=stair,
                    room=room,
                    unit_scale_mm=_unit_scale_mm,
                )

                # Resolve property-referencing bounds for this specific element
                # (each stair flight has its own Run, so this must be per-element,
                # unlike the rule-level numeric value_min/value_max).
                resolved_value_min = None
                resolved_value_max = None
                if value_min_property:
                    min_val, _, _ = self._resolve_element_property(
                        el, value_min_property, spatial=spatial, unit_scale_mm=_unit_scale_mm
                    )
                    if isinstance(min_val, (int, float)):
                        resolved_value_min = _resolve_scaled_bound(min_val, value_min_scale, value_min_offset)
                if value_max_property:
                    max_val, _, _ = self._resolve_element_property(
                        el, value_max_property, spatial=spatial, unit_scale_mm=_unit_scale_mm
                    )
                    if isinstance(max_val, (int, float)):
                        resolved_value_max = _resolve_scaled_bound(max_val, value_max_scale, value_max_offset)

                # field_consistency's second property, resolved per-element via
                # the same cascade as prop_name itself (Pset -> direct attribute
                # -> type -> alias -> fallback) so it finds Cod_Object wherever
                # the authoring tool actually put it, not just as a literal Pset key.
                resolved_compare_value = None
                if compare_property:
                    resolved_compare_value, _, _ = self._resolve_element_property(
                        el, compare_property, spatial=spatial, unit_scale_mm=_unit_scale_mm
                    )

                # Scope/waiver predicate inputs, through the same cascade. The
                # loop body is skipped entirely for rules that declare no
                # predicates, so extraction cost is unchanged for them.
                scope_values: dict = {}
                for scope_prop in scope_property_names:
                    try:
                        scope_value, _, _ = self._resolve_element_property(
                            el,
                            scope_prop,
                            spatial=spatial,
                            penetration=penetration,
                            stair=stair,
                            unit_scale_mm=_unit_scale_mm,
                        )
                    except Exception:
                        scope_value = None
                    scope_values[scope_prop] = scope_value


                _t2 = _tick()
                _sub["property-resolve"] = _sub.get("property-resolve", 0.0) + (_t2 - _t)
                _t = _t2
                # ── Type context ────────────────────────────────
                try:
                    type_inf = self._memo("type_info", el, self.get_type_info)
                except Exception:
                    type_inf = {}
                _t2 = _tick()
                _sub["type-info"] = _sub.get("type-info", 0.0) + (_t2 - _t)
                _t = _t2

                # World-space centroid (mm) — resolved once per unique
                # element via _position_cache above, not once per rule. Only
                # consumed downstream by Module 5's BCF export / the "View in
                # 3D" links, to point the camera at a failing element instead
                # of the world origin — None here just means that fallback,
                # nothing breaks.
                eid = el.id()
                if eid in _position_cache:
                    position_mm = _position_cache[eid]
                else:
                    position_mm = None
                    if self.geometry_extractor:
                        try:
                            position_mm = self.geometry_extractor.get_centroid_or_none(el)
                        except Exception:
                            position_mm = None
                    _position_cache[eid] = position_mm
                _t2 = _tick()
                _sub["centroid"] = _sub.get("centroid", 0.0) + (_t2 - _t)

                # A class-fallback caveat leads the list: whether the element
                # is the kind of thing this rule targets at all outranks any
                # caveat about how well one of its properties was measured.
                data_quality_warnings = list(rich_detail.get("warnings") or [])
                fallback_warning = self._class_fallback_warning(el, target)
                if fallback_warning:
                    data_quality_warnings.insert(0, fallback_warning)
                data_quality_warnings.extend(room.get("name_warnings") or [])

                element_results.append(
                    {
                        # Core compliance fields (consumed by Module 4)
                        "guid": el.GlobalId,
                        "name": getattr(el, "Name", None) or f"{target}_{el.id()}",
                        "actual_value": actual_value,
                        "found_pset": found_pset,
                        # Why actual_value is None, when the resolver knows.
                        "missing_reason": rich_detail.get("missing_reason"),
                        "found": actual_value is not None,
                        # Property-referencing bounds resolved for this element
                        "resolved_value_min": resolved_value_min,
                        "resolved_value_max": resolved_value_max,
                        # field_consistency's second property, resolved for this element
                        "resolved_compare_value": resolved_compare_value,
                        # World-space position for BCF viewpoint camera placement
                        "position_mm": position_mm,
                        # Gap 1: rich property metadata
                        "value_type": rich_detail.get("value_type"),
                        "value_unit": rich_detail.get("unit"),
                        "lower_bound": rich_detail.get("lower_bound"),
                        "upper_bound": rich_detail.get("upper_bound"),
                        "enum_values": rich_detail.get("enum_values"),
                        # Geometry-analysis caveats (e.g. ifc_stair flagging a
                        # winder flight, or a guard whose baluster spacing
                        # isn't computed), plus a note when the element was only
                        # reached through a class fallback (e.g. a reclassified
                        # IfcBuildingElementProxy) -- surfaced regardless of
                        # PASS/FAIL status, because a caveat matters most on a PASS: a
                        # value that looks compliant but was measured along
                        # the wrong axis for a curved stair is the case a
                        # reviewer most needs to see flagged, not just a
                        # failure they'd investigate anyway.
                        "data_quality_warnings": data_quality_warnings or None,
                        # Gap 2: spatial + type
                        "storey": spatial.get("storey_name"),
                        "space": spatial.get("space_name"),
                        "element_type": type_inf.get("type_name"),
                        # Gap 3: material
                        "materials": list(mat_info.get("materials", [])),
                        "material_layers": list(mat_info.get("layers", [])),
                        # Properties needed only by this rule's scope/waiver
                        # predicates, resolved through the same cascade as the
                        # main property. Empty for rules that declare neither.
                        "scope_values": scope_values,
                        # What this element passes through. Present only for
                        # rules that ask about a penetration; the comparator
                        # reads a missing key as UNDETERMINED, which keeps an
                        # element in scope and refuses to waive it.
                        #
                        # `or None` collapses an empty list to undetermined on
                        # purpose. "The traversal found no host" is not the
                        # same claim as "this element penetrates nothing" --
                        # an exporter that omits IfcRelVoidsElement produces
                        # the first and means neither. Reporting it as a
                        # determinate empty set would put every pipe in such a
                        # model quietly out of scope.
                        "host_classes": penetration.get("host_classes") or None,
                        "host_names": penetration.get("host_names") or None,
                        "host_materials": penetration.get("host_materials") or None,
                        "host_is_breakaway": penetration.get("host_is_breakaway"),
                        "annular_clearance_detail": penetration.get(
                            "annular_clearance_detail"
                        ),
                        # The rooms this element connects to. `or None` for the
                        # same reason as host_classes above: "no room could be
                        # linked" is not the claim "this element touches no
                        # room", and an exporter that omits space boundaries
                        # makes the first. The link source and note ride along
                        # so an UNDETERMINED predicate can say why.
                        "connected_rooms": room.get("rooms") or None,
                        # Unique per room, unlike the name: two rooms called
                        # "BADROOM 1" differ here. Ids are the IFC GlobalIds;
                        # labels are "name [#short id]" for display.
                        "connected_room_ids": room.get("room_guids") or None,
                        "connected_room_labels": room.get("room_labels") or None,
                        "connected_room_types": room.get("room_types") or None,
                        "room_link_source": room.get("link_source"),
                        "room_link_note": room.get("link_note"),
                    }
                )

            results.append(
                {
                    "rule_id": rule.get("id"),
                    "rule_ref": str(rule.get("reference") or ""),
                    "rule_desc": str(rule.get("description") or ""),
                    # Provenance the rule stores about itself, carried through
                    # so a finding can cite its source (see
                    # AnalysisService._rule_citations). Absent on rules that
                    # were authored by hand rather than extracted.
                    "ruleset_id": rule.get("ruleset_id"),
                    # Groups this rule's result under its element type in the
                    # analysis view (e.g. "Fire and Smoke Protection").
                    "check_category_id": rule.get("check_category_id") or None,
                    "source_text": rule.get("source_text"),
                    "source_document_id": rule.get("source_document_id"),
                    "source_page_number": rule.get("source_page_number"),
                    "target_ifc_class": target,
                    "property_name": prop_name,
                    "property_set": prop_set,
                    "operator": operator,
                    "check_value": self._decode_json_val(rule.get("check_value")),
                    "value_min": self._decode_json_val(rule.get("value_min")),
                    "value_max": self._decode_json_val(rule.get("value_max")),
                    "value_min_property": value_min_property,
                    "value_max_property": value_max_property,
                    "value_min_offset": value_min_offset,
                    "value_max_offset": value_max_offset,
                    "value_min_scale": value_min_scale,
                    "value_max_scale": value_max_scale,
                    "compare_property": compare_property,
                    "name_pattern": name_pattern,
                    "uniqueness_scope": uniqueness_scope,
                    "unit": str(rule.get("unit") or ""),
                    "severity": str(rule.get("severity") or "mandatory"),
                    "egress_direction": egress_direction,
                    # Scope narrowing and waivers, carried through for Module 4
                    # to gate on. Both are empty for every rule that does not
                    # declare them, which keeps the comparator on its original
                    # path. Exceptions arrive resolved from references to the
                    # predicates they stand for, so Module 4 needs no database.
                    "applies_when": scope_predicate,
                    "exceptions": resolved_exceptions,
                    # Notes about the rule's own room scope (a room it names that
                    # the model does not have), for the user to act on.
                    "scope_warnings": scope_warnings,
                    "elements": element_results,
                }
            )

            source_counts = Counter(
                str(item.get("found_pset") or "missing") for item in element_results
            )
            found_count = sum(1 for item in element_results if item.get("found"))
            progress = round(100 * rule_index / total_rules) if total_rules else 100
            logger.info(
                "Rule extraction complete rule=%d/%d progress=%d%% reference=%s matched_elements=%d values_found=%d values_missing=%d sources=%s elapsed=%.2fs",
                rule_index,
                total_rules,
                progress,
                rule.get("reference") or rule.get("id") or "unknown",
                len(element_results),
                found_count,
                len(element_results) - found_count,
                dict(source_counts),
                time.monotonic() - rule_started_at,
            )
            if time.monotonic() - rule_started_at > 2.0:
                logger.info(
                    "Rule extraction slow rule=%d/%d reference=%s breakdown=%s",
                    rule_index,
                    total_rules,
                    rule.get("reference") or rule.get("id") or "unknown",
                    {k: round(v, 2) for k, v in _sub.items()},
                )

        return results

    # ── Unit-scale helper (does not require geometry extractor) ──────────────

    def _get_length_unit_scale_mm(self) -> float:
        """
        Return model-unit → mm multiplier by reading IfcUnitAssignment directly.

        Always reads from the IFC file (not from geometry_extractor) to avoid
        inheriting any stale or incorrectly-detected unit scale.
        """
        if not self.ifc_file:
            return 1.0
        _SI_TO_MM = {
            "MILLIMETRE": 1.0, "MILLIMETER": 1.0,
            "CENTIMETRE": 10.0, "CENTIMETER": 10.0,
            "METRE": 1000.0, "METER": 1000.0,
            "KILOMETRE": 1_000_000.0, "KILOMETER": 1_000_000.0,
            "INCH": 25.4, "FOOT": 304.8,
        }
        _PREFIX_FACTORS = {"MILLI": 0.001, "CENTI": 0.01, "KILO": 1000.0, "": 1.0}
        try:
            for ua in self.ifc_file.by_type("IfcUnitAssignment"):
                for unit in (ua.Units or []):
                    if not hasattr(unit, "UnitType"):
                        continue
                    if "LENGTHUNIT" not in str(unit.UnitType).upper():
                        continue
                    if unit.is_a("IfcSIUnit"):
                        prefix = str(getattr(unit, "Prefix", "") or "").upper()
                        name = str(getattr(unit, "Name", "METRE") or "METRE").upper()
                        base_mm = _SI_TO_MM.get(name, 1000.0)
                        return base_mm * _PREFIX_FACTORS.get(prefix, 1.0)
                    if unit.is_a("IfcConversionBasedUnit"):
                        cname = str(getattr(unit, "Name", "") or "").upper()
                        if "FOOT" in cname:
                            return 304.8
                        if "INCH" in cname:
                            return 25.4
        except Exception:
            pass
        return 1.0

    # ── Rule message context (DB-backed with safe fallbacks) ────────────────

    @staticmethod
    def _as_float(value) -> float | None:
        """Best-effort conversion of rule values to float."""
        if isinstance(value, (int, float)):
            return float(value)
        if value is None:
            return None
        try:
            decoded = json.loads(str(value))
        except (json.JSONDecodeError, TypeError, ValueError):
            decoded = value
        if isinstance(decoded, (int, float)):
            return float(decoded)
        try:
            return float(str(decoded).strip())
        except (TypeError, ValueError):
            return None

    def _get_code_warning_context(self) -> dict:
        """Return DB-backed references/limits used in Tier 2/3 warning text.

        Numeric thresholds (daylight_ratio, fire_min, travel_max) stay None
        when no matching BUILDING-CODE-PART9 rule exists -- callers must
        treat None as "no threshold configured" and skip the corresponding
        check rather than substitute a hardcoded number. Text labels/units
        keep generic placeholders since they only affect wording, never a
        pass/fail verdict.
        """
        context = {
            "daylight_ref": "applicable code rule",
            "daylight_ratio": None,
            "fire_exists_ref": "applicable code rule",
            "fire_ref": "applicable code rule",
            "fire_min": None,
            "fire_unit": "min",
            "travel_ref": "applicable code rule",
            "travel_max": None,
            "travel_unit": "m",
            "egress_window_ref": "applicable code rule",
            "egress_window_clear_area_m2": None,
            "egress_window_clear_width_mm": None,
            "egress_window_clear_height_mm": None,
            "egress_window_max_sill_mm": None,
        }

        try:
            from app.services.rules_service import RuleService

            rules = RuleService().list_code_rules()
        except Exception:
            return context

        def _matches(row: dict, token: str) -> bool:
            return token in str(row.get("reference") or "")

        def _best_fire_numeric() -> dict | None:
            for row in rules:
                if not _matches(row, "9.10.9"):
                    continue
                if str(row.get("target_ifc_class") or "") != "IfcWall":
                    continue
                if str(row.get("property_name") or "") not in (
                    "FireRating",
                    "FireResistanceRating",
                    "FireResistance",
                    "REI",
                    "FRR",
                ):
                    continue
                if str(row.get("operator") or "") != ">=":
                    continue
                check = self._as_float(row.get("check_value"))
                if check is None:
                    continue
                return row
            return None

        def _best_fire_exists() -> dict | None:
            for row in rules:
                if not _matches(row, "9.10.9"):
                    continue
                if str(row.get("target_ifc_class") or "") != "IfcWall":
                    continue
                if str(row.get("property_name") or "") != "FireRating":
                    continue
                if str(row.get("operator") or "") != "exists":
                    continue
                return row
            return None

        fire_rule = _best_fire_numeric()
        if fire_rule is not None:
            context["fire_ref"] = str(fire_rule.get("reference") or context["fire_ref"])
            fire_min = self._as_float(fire_rule.get("check_value"))
            if fire_min is not None:
                context["fire_min"] = fire_min
            unit = str(fire_rule.get("unit") or "").strip()
            if unit:
                context["fire_unit"] = unit

        fire_exists_rule = _best_fire_exists()
        if fire_exists_rule is not None:
            context["fire_exists_ref"] = str(
                fire_exists_rule.get("reference") or context["fire_exists_ref"]
            )

        for row in rules:
            if not _matches(row, "9.9.10.1"):
                continue
            check = self._as_float(row.get("check_value"))
            if check is None:
                continue
            context["travel_ref"] = str(row.get("reference") or context["travel_ref"])
            context["travel_max"] = check
            unit = str(row.get("unit") or "").strip()
            if unit:
                context["travel_unit"] = unit
            break

        for row in rules:
            if not _matches(row, "9.7.2"):
                continue
            context["daylight_ref"] = str(row.get("reference") or context["daylight_ref"])
            ratio_val = self._as_float(row.get("check_value"))
            unit = str(row.get("unit") or "").strip().lower()
            if ratio_val and unit == "ratio" and 0.0 < ratio_val <= 1.0:
                context["daylight_ratio"] = ratio_val
                break

        _EGRESS_WINDOW_PROP_MAP = {
            "EgressWindowClearArea": "egress_window_clear_area_m2",
            "EgressWindowClearWidth": "egress_window_clear_width_mm",
            "EgressWindowClearHeight": "egress_window_clear_height_mm",
            "EgressWindowMaxSillHeight": "egress_window_max_sill_mm",
        }
        for row in rules:
            prop = str(row.get("property_name") or "")
            context_key = _EGRESS_WINDOW_PROP_MAP.get(prop)
            if context_key is None or context[context_key] is not None:
                continue
            val = self._as_float(row.get("check_value"))
            if val is None:
                continue
            context[context_key] = val
            context["egress_window_ref"] = str(row.get("reference") or context["egress_window_ref"])

        return context

    # ── Building-level summary (no geometry required) ─────────────────────────

    def extract_building_summary(self) -> dict:
        """
        Extract building-level summary data from the IFC model.

        Returns counts, areas, storey heights, fixture types, and QA flags
        without requiring any mesh / geometry computation.
        """
        if not self.ifc_file:
            return {}

        summary: dict = {}

        # Unit scale: model-unit → mm (e.g. 1000.0 when model is in metres)
        unit_scale = self._get_length_unit_scale_mm()

        # ── Storeys ───────────────────────────────────────────────────────────
        try:
            raw_storeys = self.ifc_file.by_type("IfcBuildingStorey")
            storeys = sorted(
                [
                    {
                        "name": getattr(s, "Name", None) or f"Level {i}",
                        # elevation stored in mm for consistent downstream use
                        "elevation": float(getattr(s, "Elevation", 0) or 0) * unit_scale,
                        "guid": s.GlobalId,
                    }
                    for i, s in enumerate(raw_storeys)
                ],
                key=lambda x: x["elevation"],
            )
            summary["storey_count"] = len(storeys)
            summary["storeys"] = storeys

            floor_heights = []
            for i in range(1, len(storeys)):
                diff = storeys[i]["elevation"] - storeys[i - 1]["elevation"]
                floor_heights.append(
                    {
                        "from": storeys[i - 1]["name"],
                        "to": storeys[i]["name"],
                        "height_mm": round(diff),
                    }
                )
            summary["floor_heights"] = floor_heights
        except Exception:
            summary["storey_count"] = 0
            summary["storeys"] = []
            summary["floor_heights"] = []

        # ── Spaces / Rooms ────────────────────────────────────────────────────

        # Build space→storey map top-down (storey → children) rather than
        # bottom-up (space → Decomposes/ContainedInStructure) because some
        # IFC exporters leave the space's back-references empty.
        _space_guid_to_storey: dict[str, str] = {}
        try:
            for _s in self.ifc_file.by_type("IfcBuildingStorey"):
                _sname = getattr(_s, "Name", None) or "Unassigned"
                # Pattern A: spaces directly contained in storey
                for _rel in getattr(_s, "ContainsElements", []):
                    for _child in getattr(_rel, "RelatedElements", []):
                        try:
                            if _child.is_a("IfcSpace"):
                                _space_guid_to_storey[_child.GlobalId] = _sname
                        except Exception:
                            pass
                # Pattern B: spaces aggregated under storey
                for _rel in getattr(_s, "IsDecomposedBy", []):
                    for _child in getattr(_rel, "RelatedObjects", []):
                        try:
                            if _child.is_a("IfcSpace"):
                                _space_guid_to_storey[_child.GlobalId] = _sname
                        except Exception:
                            pass
        except Exception:
            pass

        def _storey_name_for_space(sp) -> str:
            """Return storey name from top-down map, then fall back to space relationships."""
            # Top-down lookup (most reliable)
            name = _space_guid_to_storey.get(sp.GlobalId)
            if name:
                return name
            # Bottom-up fallback: direct containment
            for rel in getattr(sp, "ContainedInStructure", []):
                cont = rel.RelatingStructure
                if cont.is_a("IfcBuildingStorey"):
                    return getattr(cont, "Name", None) or "Unassigned"
            # Bottom-up fallback: aggregation
            for rel in getattr(sp, "Decomposes", []):
                parent = rel.RelatingObject
                if parent.is_a("IfcBuildingStorey"):
                    return getattr(parent, "Name", None) or "Unassigned"
            return "Unassigned"

        try:
            spaces = self.ifc_file.by_type("IfcSpace")
            total_area = 0.0
            rooms_by_storey: dict[str, dict] = {}
            unplaced_rooms = []

            for sp in spaces:
                psets = ifcopenshell.util.element.get_psets(sp, psets_only=False)

                # Area — check Qto then Pset
                area: float | None = None
                for ps_props in psets.values():
                    if not isinstance(ps_props, dict):
                        continue
                    for key in ("NetFloorArea", "GrossFloorArea", "Area", "NetArea"):
                        v = ps_props.get(key)
                        if v is not None:
                            try:
                                area = float(v)
                            except (ValueError, TypeError):
                                pass
                            break
                    if area is not None:
                        break

                if area:
                    total_area += area

                storey = _storey_name_for_space(sp)

                if _storey_name_for_space(sp) == "Unassigned":
                    unplaced_rooms.append(
                        {
                            "name": (
                                getattr(sp, "LongName", None)
                                or getattr(sp, "Name", None)
                                or "Unnamed"
                            ),
                            "guid": sp.GlobalId,
                        }
                    )

                if storey not in rooms_by_storey:
                    rooms_by_storey[storey] = {"count": 0, "total_area_m2": 0.0}
                rooms_by_storey[storey]["count"] += 1
                if area:
                    rooms_by_storey[storey]["total_area_m2"] = round(
                        rooms_by_storey[storey]["total_area_m2"] + area, 2
                    )

            summary["room_count"] = len(spaces)
            summary["total_gfa_m2"] = round(total_area, 2)
            summary["rooms_per_storey"] = rooms_by_storey
            summary["unplaced_rooms"] = unplaced_rooms
        except Exception:
            summary["room_count"] = 0
            summary["total_gfa_m2"] = 0.0
            summary["rooms_per_storey"] = {}
            summary["unplaced_rooms"] = []

        # ── Element counts by IFC class ───────────────────────────────────────
        _COUNT_TYPES = [
            # Vertical enclosure
            "IfcWall", "IfcCurtainWall",
            # Openings
            "IfcDoor", "IfcWindow",
            # Horizontal structure
            "IfcSlab", "IfcRoof", "IfcCovering",
            # Vertical structure
            "IfcColumn", "IfcBeam", "IfcMember",
            # Circulation
            "IfcStairFlight", "IfcRamp", "IfcRampFlight", "IfcRailing",
            # Fixtures / life safety
            "IfcSanitaryTerminal", "IfcAlarm", "IfcSensor",
            # Furniture
            "IfcFurnishingElement",
        ]
        element_counts: dict[str, int] = {}
        for ifc_type in _COUNT_TYPES:
            try:
                # Use class fallback so IfcStairFlight counts include IfcStair-decomposed flights
                elems = self._get_elements_with_fallback(ifc_type)
                if elems:
                    element_counts[ifc_type] = len(elems)
            except Exception:
                pass
        summary["element_counts"] = element_counts

        # ── Plumbing fixture counts (IfcSanitaryTerminal by PredefinedType) ──
        _FIXTURE_LABELS: dict[str, str] = {
            "TOILETPAN": "WC / Toilet",
            "BATH": "Bath",
            "SHOWER": "Shower",
            "WASHHANDBASIN": "Washbasin",
            "SINK": "Sink",
            "URINAL": "Urinal",
            "CISTERN": "Cistern",
        }
        fixture_counts: dict[str, int] = {}
        try:
            fixtures = self._get_elements_with_fallback("IfcSanitaryTerminal")
            for f in fixtures:
                ptype = getattr(f, "PredefinedType", None)
                if not ptype:
                    psets = ifcopenshell.util.element.get_psets(f, psets_only=False)
                    for ps in psets.values():
                        if isinstance(ps, dict) and "PredefinedType" in ps:
                            ptype = ps["PredefinedType"]
                            break
                label = _FIXTURE_LABELS.get(str(ptype or "").upper(), str(ptype or "Unknown").title())
                fixture_counts[label] = fixture_counts.get(label, 0) + 1
        except Exception:
            pass
        summary["fixture_counts"] = fixture_counts

        # ── External door count ───────────────────────────────────────────────
        external_doors = 0
        try:
            doors = self._get_elements_with_fallback("IfcDoor")
            for door in doors:
                psets = ifcopenshell.util.element.get_psets(door, psets_only=False)
                is_ext = None
                for ps in psets.values():
                    if isinstance(ps, dict) and "IsExternal" in ps:
                        is_ext = ps["IsExternal"]
                        break
                if is_ext is True or str(is_ext).upper() in ("TRUE", "1", "YES"):
                    external_doors += 1
        except Exception:
            pass
        summary["external_door_count"] = external_doors

        # ── Alarm / detector count by type ────────────────────────────────────
        alarm_counts: dict[str, int] = {}
        _ALARM_LABELS: dict[str, str] = {
            "SMOKEALARM": "Smoke Alarm",
            "FIREDETECTOR": "Fire Detector",
            "HEATDETECTOR": "Heat Detector",
            "CO2SENSOR": "CO Sensor",
            "MANUALPULLBOX": "Manual Pull Station",
        }
        try:
            alarms = self._get_elements_with_fallback("IfcAlarm")
            for a in alarms:
                ptype = getattr(a, "PredefinedType", None)
                if not ptype:
                    psets = ifcopenshell.util.element.get_psets(a, psets_only=False)
                    for ps in psets.values():
                        if isinstance(ps, dict) and "PredefinedType" in ps:
                            ptype = ps["PredefinedType"]
                            break
                label = _ALARM_LABELS.get(str(ptype or "").upper(), str(ptype or "Unknown").title())
                alarm_counts[label] = alarm_counts.get(label, 0) + 1
        except Exception:
            pass
        summary["alarm_counts"] = alarm_counts

        # ── QA: unnamed elements ──────────────────────────────────────────────
        unnamed_elements: list[dict] = []
        for ifc_type in ("IfcDoor", "IfcWindow", "IfcStairFlight", "IfcRailing", "IfcSpace"):
            try:
                elems = self._get_elements_with_fallback(ifc_type)
                unnamed = [
                    {"type": ifc_type, "guid": el.GlobalId}
                    for el in elems
                    if not getattr(el, "Name", None)
                ]
                if unnamed:
                    unnamed_elements.append({"type": ifc_type, "count": len(unnamed)})
            except Exception:
                pass
        summary["unnamed_elements"] = unnamed_elements

        return summary

    # ── Tier 2: spatial adjacency checks ─────────────────────────────────────

    def extract_spatial_checks(self) -> dict:
        """
        Run Tier 2 spatial compliance checks that require room-to-element linking.

        Returns:
            {
              "has_boundaries": bool,
              "space_count": int,
              "party_wall_count": int,
              "daylight": [list of per-room daylight ratio results],
              "fire_separation": [list of per-party-wall fire rating results],
              "egress_windows": [list of per-sleeping-room rescue-opening results],
              "warnings": [str],
            }
        """
        if not self.ifc_file or not self.spatial_adjacency:
            return {
                "has_boundaries": False,
                "space_count": 0,
                "party_wall_count": 0,
                "daylight": [],
                "fire_separation": [],
                "warnings": ["Spatial adjacency engine not available."],
            }

        adj = self.spatial_adjacency
        warnings: list[str] = []

        if not adj.has_boundaries:
            warnings.append(
                "No IfcRelSpaceBoundary data found in this file. "
                "Export with 'Space Boundaries' enabled for daylight and "
                "fire separation checks."
            )

        rule_ctx = self._get_code_warning_context()

        daylight_ref = str(rule_ctx.get("daylight_ref") or "applicable code rule")
        daylight_ratio = self._as_float(rule_ctx.get("daylight_ratio"))

        fire_exists_ref = str(
            rule_ctx.get("fire_exists_ref") or "applicable code rule"
        )
        fire_ref = str(rule_ctx.get("fire_ref") or "applicable code rule")
        fire_min = self._as_float(rule_ctx.get("fire_min"))
        fire_unit = str(rule_ctx.get("fire_unit") or "min")

        daylight = check_daylight_ratios(
            adj, min_ratio=daylight_ratio, room_linker=self.room_linker
        )
        fire_sep = check_fire_separation(adj, min_rating_min=fire_min)
        garage_sep = check_garage_separation(adj)
        space_connection = check_door_space_connection(adj, self.ifc_file)
        egress_windows = check_egress_window_openings(
            adj,
            geometry_extractor=self.geometry_extractor,
            min_clear_area_m2=self._as_float(rule_ctx.get("egress_window_clear_area_m2")),
            min_clear_width_mm=self._as_float(rule_ctx.get("egress_window_clear_width_mm")),
            min_clear_height_mm=self._as_float(rule_ctx.get("egress_window_clear_height_mm")),
            max_sill_height_mm=self._as_float(rule_ctx.get("egress_window_max_sill_mm")),
            room_linker=self.room_linker,
        )

        if daylight_ratio is None:
            warnings.append(
                "No rule was found for daylight ratio -- daylight check not evaluated."
            )
        else:
            daylight_ratio_label = f"1/{int(round(1 / daylight_ratio))}" if daylight_ratio > 0 else "0"
            daylight_fails = sum(1 for r in daylight if not r["passes"] and not r.get("undetermined"))
            if daylight_fails:
                warnings.append(
                    f"{daylight_fails} room(s) do not meet the {daylight_ref} "
                    f"{daylight_ratio_label} daylight ratio requirement."
                )
            daylight_unknown = [r for r in daylight if r.get("undetermined")]
            if daylight_unknown:
                warnings.append(
                    f"Daylight ratio could not be determined for {len(daylight_unknown)} room(s): "
                    f"{daylight_unknown[0]['undetermined_reason']}"
                )

        if fire_min is None:
            warnings.append(
                "No rule was found for party-wall fire rating -- "
                "fire-separation check not evaluated."
            )
        else:
            fire_min_label = f"{int(fire_min)}" if fire_min.is_integer() else str(fire_min)
            fire_fails = sum(1 for r in fire_sep if not r["passes"])
            fire_missing = sum(1 for r in fire_sep if r["missing_rating"])
            if fire_missing:
                warnings.append(
                    f"{fire_missing} party wall(s) have no FireRating declared "
                    f"({fire_exists_ref}; {fire_ref} requires >= {fire_min_label} {fire_unit})."
                )
            if fire_fails and not fire_missing:
                warnings.append(
                    f"{fire_fails} party wall(s) have FireRating below "
                    f"{fire_min_label} {fire_unit} ({fire_ref})."
                )

        if not any(
            rule_ctx.get(k) is not None
            for k in (
                "egress_window_clear_area_m2", "egress_window_clear_width_mm",
                "egress_window_clear_height_mm", "egress_window_max_sill_mm",
            )
        ):
            warnings.append(
                "No rule was found for the emergency escape and rescue window "
                "opening -- egress-window check not evaluated."
            )
        else:
            egress_window_fails = sum(1 for r in egress_windows if not r["passes"])
            if egress_window_fails:
                warnings.append(
                    f"{egress_window_fails} sleeping room(s) do not have a "
                    f"compliant emergency escape and rescue window opening "
                    f"({rule_ctx.get('egress_window_ref')})."
                )

        return {
            "has_boundaries": adj.has_boundaries,
            "space_count": adj.space_count(),
            "party_wall_count": adj.party_wall_count(),
            "daylight": daylight,
            "fire_separation": fire_sep,
            "garage_separation": garage_sep,
            "space_connection": space_connection,
            "egress_windows": egress_windows,
            "warnings": warnings,
        }

    # ── Tier 3: egress checks ─────────────────────────────────────────────────

    def extract_egress_checks(self) -> dict:
        """
        Run Tier 3 egress compliance checks.

        Returns:
            {
              "exit_count": dict from check_exit_count(),
              "travel_distance": list from check_egress_travel_distance(),
              "has_graph": bool,
              "warnings": [str],
            }
        """
        warnings: list[str] = []
        rule_ctx = self._get_code_warning_context()
        travel_ref = str(rule_ctx.get("travel_ref") or "applicable code rule")
        travel_max = self._as_float(rule_ctx.get("travel_max"))
        travel_unit = str(rule_ctx.get("travel_unit") or "m")

        # Exit count always runs (doesn't need boundary data)
        if self.ifc_file and _EGRESS_AVAILABLE:
            exit_count = check_exit_count(self.ifc_file)
        else:
            exit_count = {
                "total_exterior_doors": 0,
                "exits_per_storey": {},
                "results": [],
                "warnings": ["Egress engine not available."],
            }
            warnings.append("Egress engine not available.")

        # Travel distance requires boundary data + egress graph
        has_graph = self.egress_graph is not None and self.egress_graph.graph is not None
        if has_graph and _EGRESS_AVAILABLE:
            travel_distance = check_egress_travel_distance(
                self.egress_graph, max_distance_m=travel_max
            )
            if not self.egress_graph._exit_spaces:
                warnings.append(
                    "No exits identified in the space graph (no exterior doors linked to spaces). "
                    "Travel-distance check requires exterior doors tagged IsExternal=True and "
                    "IfcRelSpaceBoundary data."
                )
        else:
            travel_distance = []
            if not has_graph:
                warnings.append(
                    "Egress travel-distance check requires IfcRelSpaceBoundary data. "
                    "Re-export the model with Space Boundaries enabled."
                )

        if travel_max is None:
            warnings.append(
                "No rule was found for maximum egress travel distance -- "
                "travel-distance check not evaluated."
            )
        else:
            travel_max_label = f"{int(travel_max)}" if travel_max.is_integer() else str(travel_max)
            td_fails = sum(1 for r in travel_distance if not r["passes"])
            if td_fails:
                warnings.append(
                    f"{td_fails} habitable space(s) exceed the {travel_ref} "
                    f"maximum travel distance of {travel_max_label} {travel_unit}."
                )

        return {
            "exit_count": exit_count,
            "travel_distance": travel_distance,
            "has_graph": has_graph,
            "warnings": warnings,
        }

    def get_full_element_data(self, element) -> dict:
        """
        Return everything about one IFC element — for inspection / debugging.

        Combines: direct attributes, rich properties, type, spatial, materials,
        decomposition.
        """
        return {
            "guid": element.GlobalId,
            "ifc_type": element.is_a(),
            "name": getattr(element, "Name", None),
            "description": getattr(element, "Description", None),
            "direct_attributes": self.get_direct_attributes(element),
            "properties": self.extract_rich_properties(element),
            "spatial": self.get_spatial_location(element),
            "type_info": self.get_type_info(element),
            "materials": self.get_material_info(element),
            "decomposition": self.get_decomposition(element),
        }

    # ── Utility ───────────────────────────────────────────────────────────────

    def extract_geometry(self) -> list[dict]:
        """Return {id, type, properties} for all building elements (legacy)."""
        if not self.ifc_file:
            raise ValueError("No IFC file loaded.")
        return [
            {"id": el.id(), "type": el.is_a(), "properties": self.extract_properties(el)}
            for el in self._resolve_building_elements()
        ]

    def extract_summary_counts(
        self,
        include_openings: bool = True,
        include_spaces: bool = True,
        include_type_definitions: bool = False,
    ) -> dict:
        if not self.ifc_file:
            raise ValueError("No IFC file loaded.")
        built = len(self._resolve_building_elements())
        phys = self._count_by_type("IfcElement")
        prods = self._count_by_type("IfcProduct")
        opens = self._count_by_type("IfcOpeningElement")
        spaces = self._count_by_type("IfcSpace")
        types = self._count_by_type("IfcElementType")
        adj_phys = max(0, phys - (opens if not include_openings else 0))
        adj_prods = max(
            0,
            prods
            - (opens if not include_openings else 0)
            - (spaces if not include_spaces else 0)
            + (types if include_type_definitions else 0),
        )
        return {
            "built_elements": built,
            "all_physical_elements": phys,
            "all_products": prods,
            "adjusted_physical_elements": adj_phys,
            "adjusted_products": adj_prods,
            "filters": {
                "include_openings": include_openings,
                "include_spaces": include_spaces,
                "include_type_definitions": include_type_definitions,
            },
            "excluded_or_added": {
                "openings": opens,
                "spaces": spaces,
                "type_definitions": types,
            },
        }

    def _count_by_type(self, ifc_type: str) -> int:
        try:
            return len(self.ifc_file.by_type(ifc_type))
        except Exception:
            return 0

    #: Scope predicate key -> IFC property to resolve per element. Mirrors
    #: ``comparator._SCOPE_NUMERIC_PROPERTIES``; the comparator does
    #: the comparing, this side only has to know what to fetch.
    _SCOPE_PROPERTY_SOURCES = {
        "nominal_diameter_mm": "NominalDiameter",
        "nominal_diameter_below_mm": "NominalDiameter",
        # Resolved by the support traversal rather than from a Pset, but it
        # travels the same route: the comparator reads it out of `scope_values`
        # and needs no new machinery.
        "hanger_rod_length_below_mm": "HangerRodLength",
        "hanger_rod_length_mm": "HangerRodLength",
        "lateral_brace_spacing_mm": "LateralBraceSpacing",
        "longitudinal_brace_spacing_mm": "LongitudinalBraceSpacing",
    }

    #: Predicate keys answered by the penetration traversal (``ifc_penetrations``)
    #: rather than by reading a property off the element itself. They describe
    #: the element's *host* -- what it passes through -- which no Pset holds.
    _PENETRATION_PREDICATE_KEYS = frozenset(
        {
            "penetrates",
            "host_class_any_of",
            "host_material_any_of",
            "host_is_breakaway",
        }
    )

    #: Property names that only the penetration traversal can produce, matched
    #: case- and separator-insensitively against a rule's ``property_name``.
    _PENETRATION_PROPERTIES = frozenset({"annularclearance"})


    #: Property names produced by the stair geometry engine (``ifc_stair``),
    #: matched the same way. v1 gates on property name only -- unlike the
    #: two traversals above, no scope/waiver predicate yet references a
    #: stair-derived property, so there is no predicate-key set to check.
    _STAIR_PROPERTIES = frozenset(_STAIR_DERIVED_PROPERTIES)

    #: Operators marking a rule as a waiver *definition* rather than a
    #: requirement. Such a row states the condition under which some other rule
    #: is excused; on its own it asserts nothing about the model and has no
    #: verdict to give, so it is never extracted or evaluated standalone. It
    #: reaches the comparator only through the `exceptions` of the rule it
    #: waives, as a resolved predicate.
    _WAIVER_ONLY_OPERATORS = frozenset({"exempt", "exemption", "waiver"})

    @classmethod
    def _is_waiver_only(cls, operator: str) -> bool:
        """Return True when a rule defines a waiver, not a requirement."""
        return str(operator or "").strip().lower() in cls._WAIVER_ONLY_OPERATORS

    @classmethod
    def _needs_penetration_context(
        cls, prop_name: str, scope: dict, exceptions: list[dict]
    ) -> bool:
        """Whether this rule needs the host/opening traversal for its elements.

        The traversal walks relationships and reads geometry, so it is worth
        far more than a Pset lookup and must not run for the ~1,878 rules that
        have no use for it. Gated on the rule asking for a penetration-derived
        property, or naming a host predicate in its scope or any of its
        waivers.
        """
        normalized = str(prop_name or "").replace("_", "").replace(" ", "").lower()
        if normalized in cls._PENETRATION_PROPERTIES:
            return True
        for predicate in [scope] + [e.get("predicate") or {} for e in exceptions]:
            if cls._PENETRATION_PREDICATE_KEYS & set(predicate or {}):
                return True
        return False


    @staticmethod
    def _stair_derived_value(prop_key_name: str, stair: dict | None):
        """Return (value, detail) for a stair-derived property, or (None, {}).

        None means the geometry analysis could not answer -- no resolvable
        mesh, fewer than two detected tread bands, or (for whole-stairway
        properties) no sibling flights to aggregate. Never a guessed 0,
        False, or empty list standing in for "not measured".
        """
        spec = _STAIR_DERIVED_PROPERTIES[prop_key_name]
        context = stair or {}
        if isinstance(spec, tuple):
            nested_key, field = spec
            value = (context.get(nested_key) or {}).get(field)
        else:
            value = context.get(spec)
        # An empty list (risers_mm/goings_mm when fewer than 2 tread bands
        # were detected) is the same "could not answer" case as None, not a
        # determinate empty result -- otherwise `exists` would read "no
        # risers were detected" as "RiserHeights exists".
        if isinstance(value, (list, tuple)) and len(value) == 0:
            value = None
        if value is None:
            return None, {}
        return value, {"warnings": context.get("warnings") or []}

    @classmethod
    def _needs_stair_context(
        cls, prop_name: str, scope: dict, exceptions: list[dict]
    ) -> bool:
        """Whether this rule needs the stair geometry engine for its elements.

        Gated like the other traversals -- ``IFCStairEngine`` meshes
        and decomposes every flight/landing/railing once per model up front
        (not per rule), but a rule that never asks for a stair-derived
        property must not pay even that lookup cost.
        """
        normalized = str(prop_name or "").replace("_", "").replace(" ", "").lower()
        return normalized in cls._STAIR_PROPERTIES

    @staticmethod
    def _decode_json_obj(value):
        """Decode a JSON object column (applies_when) into a dict."""
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return decoded if isinstance(decoded, dict) else {}

    @staticmethod
    def _decode_json_list(value):
        """Decode a JSON array column (exceptions) into a list."""
        if isinstance(value, list):
            return value
        if not value:
            return []
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return []
        return decoded if isinstance(decoded, list) else []

    @classmethod
    def _resolve_exceptions(cls, rule: dict, rules_by_reference: dict) -> list[dict]:
        """Turn a rule's `exceptions` references into predicates to evaluate.

        A reference that names no rule in this batch is kept with an empty
        predicate and marked unresolved, rather than dropped: the comparator
        treats an empty predicate as undetermined and so declines to waive,
        which is the safe direction. Silently discarding it would instead make
        the exemption look considered and rejected.
        """
        resolved: list[dict] = []
        for entry in cls._decode_json_list(rule.get("exceptions")):
            if isinstance(entry, dict):
                # An inline predicate, already in the shape Module 4 wants.
                resolved.append(entry)
                continue
            ref = str(entry).strip()
            if not ref:
                continue
            source = rules_by_reference.get(ref)
            if source is None:
                resolved.append({"reference": ref, "predicate": {}, "unresolved": True})
                continue
            resolved.append(
                {
                    "reference": ref,
                    "label": str(source.get("description") or ref),
                    "predicate": cls._decode_json_obj(source.get("applies_when")),
                }
            )
        return resolved

    @classmethod
    def _scope_property_names(cls, scope: dict, exceptions: list[dict]) -> set:
        """Return the IFC properties the scope and waiver predicates need."""
        wanted = set()
        predicates = [scope] + [e.get("predicate") or {} for e in exceptions]
        for predicate in predicates:
            for key in predicate or {}:
                prop = cls._SCOPE_PROPERTY_SOURCES.get(key)
                if prop:
                    wanted.add(prop)
        return wanted

    @staticmethod
    def _decode_json_val(v):
        """Decode a DB JSON-encoded check_value / value_min / value_max.

        value_min/value_max/offsets are always numeric, but check_value can
        legitimately be a string or boolean (e.g. IsExternal == "TRUE") —
        forcing float() on those silently discarded them as None, which broke
        both the "Required" display text and the actual == / != / matches
        comparison (Module 4 always compared against None instead of the
        real value). Only coerce to float when the decoded value is numeric.
        """
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        try:
            decoded = json.loads(str(v))
        except (json.JSONDecodeError, ValueError, TypeError):
            return None
        if isinstance(decoded, bool):
            return decoded
        if isinstance(decoded, (int, float)):
            return float(decoded)
        if isinstance(decoded, str):
            try:
                return float(decoded)
            except ValueError:
                return decoded  # genuinely non-numeric, e.g. "TRUE" / an enum value
        return decoded
