"""
module2_ifc_read.py
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
from pathlib import Path

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
        check_daylight_ratios,
        check_fire_separation,
        check_garage_separation,
        check_door_space_connection,
        _element_matches_location,
    )
    _SPATIAL_AVAILABLE = True
except ImportError:
    _SPATIAL_AVAILABLE = False

try:
    from .ifc_egress import IFCEgressGraph, check_exit_count, check_egress_travel_distance
    _EGRESS_AVAILABLE = True
except ImportError:
    _EGRESS_AVAILABLE = False

try:
    from .ifc_quality.validator import IFCValidator
    from .ifc_quality.improver import improve_ifc_file

    _QUALITY_TOOLS_AVAILABLE = True
except ImportError:
    _QUALITY_TOOLS_AVAILABLE = False

# Minimum quality score (0-100) required before extraction proceeds.
# Files below this threshold are auto-improved before loading.
IFC_MIN_QUALITY_SCORE = 70


# ── IFC class fallback map ────────────────────────────────────────────────────
# Revit and some other authoring tools export the *container* class rather than
# the sub-element class that buildingSMART rules target.  When by_type(target)
# returns nothing, try each fallback in order.  For IfcStair specifically we
# also walk IsDecomposedBy to recover the individual IfcStairFlight children.
_IFC_CLASS_FALLBACKS: dict[str, list[str]] = {
    "IfcStairFlight":      ["IfcStair"],
    "IfcRampFlight":       ["IfcRamp"],
    "IfcRailing":          ["IfcHandRail", "IfcMember"],
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
    "RiserHeight":      ["RiserType", "Riser", "RiserHeightType", "StepHeight"],
    "RequiredHeadroom": ["HeadroomClearance", "Headroom", "ClearHeight", "ClearanceHeight"],
    "HandrailHeight":   ["Height", "RailingHeight", "BarrierHeight"],
    "Area":             ["ClearOpeningArea", "GrossArea", "NetArea", "OpeningArea"],
    "RequiredSlope":    ["Slope", "PitchAngle", "SlopeAngle", "Gradient"],
    "PitchAngle":       ["Slope", "RequiredSlope", "SlopeAngle", "Gradient"],
    "FireRating":       ["FireResistanceRating", "FireResistance", "REI", "FRR"],
    "LongName":         ["Name", "SpaceName", "RoomName"],
    "ModelNumber":      ["ModelReference", "ModelLabel"],
    "OpeningDirection": ["OperationType"],
}


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
    "handrailheight", "sillheight", "headroomclearance",
    "requireheadroom", "clearwidth", "nominalwidth", "nominalheight",
    "clearheight", "elevationwithflooring",
    "grosswidth", "grossheight", "netwidth", "netheight",
    "thickness", "length", "depth",
    "corridorwidth", "minimumwidth", "passagewidth",
    "perimeter", "footprintperimeter",
    "diameter", "nominaldiameter",
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


class Module2_IFCRead:
    """Full IFC reader for Module 2 compliance extraction."""

    def __init__(self, file_path: Path | str | None = None):
        self.file_path = Path(file_path) if file_path else None
        self.ifc_file = None
        self.quality_report: dict = {}
        self.quality_warnings: list[str] = []
        self.geometry_extractor: "IFCGeometryExtractor | None" = None
        self.spatial_adjacency: "IFCSpatialAdjacency | None" = None
        self.egress_graph: "IFCEgressGraph | None" = None
        if self.file_path:
            self.load_ifc_file()

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

        if _QUALITY_TOOLS_AVAILABLE:
            results = IFCValidator(str(load_path)).validate()
            self.quality_report = results
            score = results.get("overall", {}).get("score", 100)

            if score < IFC_MIN_QUALITY_SCORE:
                improved_path = load_path.with_stem(load_path.stem + "_improved")
                improvement_summary = improve_ifc_file(str(load_path), str(improved_path))
                load_path = improved_path
                self.quality_warnings.append(
                    f"Quality {score:.1f}% was below threshold; "
                    f"auto-improved file used: {improved_path.name}"
                )
                self.quality_improvements = improvement_summary.get("improvements", [])
            elif score < 80:
                self.quality_warnings.append(
                    f"IFC quality is fair ({score:.1f}%). "
                    "Consider running the IFC improver for better results."
                )

        self.ifc_file = ifcopenshell.open(str(load_path))
        if _GEOMETRY_AVAILABLE:
            self.geometry_extractor = IFCGeometryExtractor(self.ifc_file)
        if _SPATIAL_AVAILABLE:
            self.spatial_adjacency = IFCSpatialAdjacency(self.ifc_file).build()
        if _EGRESS_AVAILABLE and self.spatial_adjacency is not None:
            self.egress_graph = IFCEgressGraph(self.spatial_adjacency).build()
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
            mat = ifcopenshell.util.element.get_material(element)
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
        """
        try:
            info = element.get_info()
        except Exception:
            return {}

        _SKIP = {
            "id",
            "type",
            "GlobalId",
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

            return candidates

        return []

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
        never uses it to decide pass/fail (the rule's own operator does)."""
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
        }

    # ── Reusable single-property resolution cascade ──────────────────────────

    def _resolve_element_property(
        self,
        el,
        prop_name: str,
        prop_set: str = "",
        fallback_prop: str = "",
        spatial: dict | None = None,
        material_info: dict | None = None,
        door_space_connection: dict | None = None,
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
        if prop_lower_name in ("storey", "level", "buildingstorey", "floor"):
            storey_name = spatial.get("storey_name")
            if storey_name:
                return storey_name, "spatial:storey", rich_detail
        elif prop_lower_name == "material":
            materials = (material_info or {}).get("materials") or []
            if materials:
                return ", ".join(materials), "material:relationship", rich_detail
        elif prop_lower_name in ("connectedspaces", "spaceconnection", "connectedspacenames", "doorconnectedspaces"):
            names = (door_space_connection or {}).get("connected_space_names") or []
            if names:
                dsc_rich = self._door_space_rich_detail(door_space_connection)
                return ", ".join(names), "spatial:door_space_connection", dsc_rich
        elif prop_lower_name in ("connectedspacecount", "spaceconnectioncount", "numberofconnectedspaces", "connectedspacescount"):
            if door_space_connection is not None:
                dsc_rich = self._door_space_rich_detail(door_space_connection)
                return door_space_connection.get("connected_space_count", 0), "spatial:door_space_connection", dsc_rich

        # ── Pass 1: instance Psets + Qto sets (fast path) ─────────
        try:
            psets_simple = ifcopenshell.util.element.get_psets(el, psets_only=False)
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
                rich_all = self.extract_rich_properties(el)
                pset_key = found_pset.split(":")[-1]  # strip "type:" prefix if any
                rich_prop = rich_all.get(pset_key, {}).get(prop_name, {})
                if rich_prop:
                    rich_detail = rich_prop
            except Exception:
                pass

        # ── Pass 3: direct IFC schema attributes ──────────────────
        if actual_value is None:
            try:
                direct = self.get_direct_attributes(el)
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
                el_type = ifcopenshell.util.element.get_type(el)
                if el_type:
                    type_psets = ifcopenshell.util.element.get_psets(
                        el_type, psets_only=False
                    )
                    v, ps = self._lookup_in_psets(type_psets, prop_name)
                    if v is not None:
                        actual_value = v
                        found_pset = f"type:{ps}"
                    if actual_value is None:
                        type_direct = self.get_direct_attributes(el_type)
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
                el_type_for_alias = ifcopenshell.util.element.get_type(el)
                if el_type_for_alias:
                    type_psets_for_alias = ifcopenshell.util.element.get_psets(
                        el_type_for_alias, psets_only=False
                    )
            except Exception:
                pass

            for alias in _PROPERTY_ALIASES.get(prop_name, []):
                v, ps = self._lookup_in_psets(psets_simple, alias)
                if v is not None:
                    actual_value, found_pset = v, f"alias:{ps}"
                    break
                try:
                    direct = self.get_direct_attributes(el)
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
                        type_direct = self.get_direct_attributes(el_type_for_alias)
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
                    direct = self.get_direct_attributes(el)
                    v = direct.get(fallback_prop)
                    if v is not None:
                        actual_value = v
                        found_pset = "fallback:direct_attribute"
                except Exception:
                    pass

        # ── Pass 7: bounding-box geometry (Tier 1) ───────────────
        # Only runs when all Pset/attribute passes returned nothing.
        if actual_value is None and self.geometry_extractor:
            try:
                floor_z = spatial.get("storey_elevation")
                # storey_elevation from IFC is in model units; convert to mm
                if floor_z is not None and self.geometry_extractor._unit_scale != 1.0:
                    floor_z = floor_z * self.geometry_extractor._unit_scale
                geo_val = self.geometry_extractor.get_geometry_value(
                    el, prop_name, floor_z
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
            and isinstance(actual_value, (int, float))
            and found_pset != "geometry"
        ):
            measure_type = rich_detail.get("measure_type", "")
            prop_lower = prop_name.lower()
            if (measure_type in _LENGTH_MEASURE_TYPES
                    or prop_lower in _LENGTH_DIRECT_ATTRS):
                actual_value = round(actual_value * unit_scale_mm, 4)

        return actual_value, found_pset, rich_detail

    # ── Compliance extraction (all fallbacks) ─────────────────────────────────

    def extract_for_compliance(self, rules: list[dict]) -> list[dict]:
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
        for rule in rules:
            target = str(rule.get("target_ifc_class") or "").strip()
            prop_name = str(rule.get("property_name") or "").strip()
            prop_set = str(rule.get("property_set") or "").strip()
            operator = str(rule.get("operator") or "").strip()
            fallback_prop = str(rule.get("fallback_property") or "").strip()

            # Property-referencing bounds — e.g. tread depth
            # must be between its own Run and Run + 25mm. Instead of a fixed
            # numeric value_min/value_max, the bound is another property on
            # the same element (optionally offset by a fixed amount).
            value_min_property = str(rule.get("value_min_property") or "").strip()
            value_max_property = str(rule.get("value_max_property") or "").strip()
            value_min_offset = self._decode_json_val(rule.get("value_min_offset")) or 0.0
            value_max_offset = self._decode_json_val(rule.get("value_max_offset")) or 0.0

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

            element_results = []
            for el in elements:
                # Spatial + material context fetched early — floor_z needed for
                # Pass 7 geometry, and both feed the Pass 0 relationship shortcut
                # for "Storey"/"Material" rules.
                try:
                    spatial = self.get_spatial_location(el)
                except Exception:
                    spatial = {}
                try:
                    mat_info = self.get_material_info(el)
                except Exception:
                    mat_info = {}
                door_space = door_space_lookup.get(getattr(el, "GlobalId", None))

                actual_value, found_pset, rich_detail = self._resolve_element_property(
                    el,
                    prop_name,
                    prop_set=prop_set,
                    fallback_prop=fallback_prop,
                    spatial=spatial,
                    material_info=mat_info,
                    door_space_connection=door_space,
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
                        resolved_value_min = round(min_val + value_min_offset, 4)
                if value_max_property:
                    max_val, _, _ = self._resolve_element_property(
                        el, value_max_property, spatial=spatial, unit_scale_mm=_unit_scale_mm
                    )
                    if isinstance(max_val, (int, float)):
                        resolved_value_max = round(max_val + value_max_offset, 4)

                # ── Type context ────────────────────────────────
                try:
                    type_inf = self.get_type_info(el)
                except Exception:
                    type_inf = {}

                element_results.append(
                    {
                        # Core compliance fields (consumed by Module 4)
                        "guid": el.GlobalId,
                        "name": getattr(el, "Name", None) or f"{target}_{el.id()}",
                        "actual_value": actual_value,
                        "found_pset": found_pset,
                        "found": actual_value is not None,
                        # Property-referencing bounds resolved for this element
                        "resolved_value_min": resolved_value_min,
                        "resolved_value_max": resolved_value_max,
                        # Gap 1: rich property metadata
                        "value_type": rich_detail.get("value_type"),
                        "value_unit": rich_detail.get("unit"),
                        "lower_bound": rich_detail.get("lower_bound"),
                        "upper_bound": rich_detail.get("upper_bound"),
                        "enum_values": rich_detail.get("enum_values"),
                        # Gap 2: spatial + type
                        "storey": spatial.get("storey_name"),
                        "space": spatial.get("space_name"),
                        "element_type": type_inf.get("type_name"),
                        # Gap 3: material
                        "materials": mat_info.get("materials", []),
                        "material_layers": mat_info.get("layers", []),
                    }
                )

            results.append(
                {
                    "rule_id": rule.get("id"),
                    "rule_ref": str(rule.get("reference") or ""),
                    "rule_desc": str(rule.get("description") or ""),
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
                    "unit": str(rule.get("unit") or ""),
                    "severity": str(rule.get("severity") or "mandatory"),
                    "egress_direction": egress_direction,
                    "elements": element_results,
                }
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

        Falls back to current hardcoded defaults whenever DB access fails or
        when matching rules are unavailable.
        """
        context = {
            "daylight_ref": "applicable code rule",
            "daylight_ratio": 0.1,
            "fire_exists_ref": "applicable code rule",
            "fire_ref": "applicable code rule",
            "fire_min": 45.0,
            "fire_unit": "min",
            "travel_ref": "applicable code rule",
            "travel_max": 25.0,
            "travel_unit": "m",
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

        daylight = check_daylight_ratios(adj)
        fire_sep = check_fire_separation(adj)
        garage_sep = check_garage_separation(adj)
        space_connection = check_door_space_connection(adj, self.ifc_file)
        rule_ctx = self._get_code_warning_context()

        daylight_ref = str(rule_ctx.get("daylight_ref") or "applicable code rule")
        daylight_ratio = self._as_float(rule_ctx.get("daylight_ratio")) or 0.1
        if daylight_ratio > 0:
            daylight_ratio_label = f"1/{int(round(1 / daylight_ratio))}"
        else:
            daylight_ratio_label = "1/10"

        fire_exists_ref = str(
            rule_ctx.get("fire_exists_ref") or "applicable code rule"
        )
        fire_ref = str(rule_ctx.get("fire_ref") or "applicable code rule")
        fire_min = self._as_float(rule_ctx.get("fire_min"))
        fire_min_label = (
            f"{int(fire_min)}"
            if isinstance(fire_min, float) and fire_min.is_integer()
            else str(fire_min or 45)
        )
        fire_unit = str(rule_ctx.get("fire_unit") or "min")

        daylight_fails = sum(1 for r in daylight if not r["passes"])
        fire_fails = sum(1 for r in fire_sep if not r["passes"])
        fire_missing = sum(1 for r in fire_sep if r["missing_rating"])

        if daylight_fails:
            warnings.append(
                f"{daylight_fails} room(s) do not meet the {daylight_ref} "
                f"{daylight_ratio_label} daylight ratio requirement."
            )
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

        return {
            "has_boundaries": adj.has_boundaries,
            "space_count": adj.space_count(),
            "party_wall_count": adj.party_wall_count(),
            "daylight": daylight,
            "fire_separation": fire_sep,
            "garage_separation": garage_sep,
            "space_connection": space_connection,
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
        travel_max_label = (
            f"{int(travel_max)}"
            if isinstance(travel_max, float) and travel_max.is_integer()
            else str(travel_max or 25)
        )
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
            travel_distance = check_egress_travel_distance(self.egress_graph)
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
