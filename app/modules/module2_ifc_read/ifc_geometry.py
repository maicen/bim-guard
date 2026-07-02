"""
BIMGUARD AI — IFC Geometry Extraction
modules/ifc_geometry.py

Two responsibilities:

  1. Pipe surface area — used by the GC-001 corrosion engine.
     Reads actual mesh geometry or falls back to nominal-diameter estimation.

  2. Tier 1 architectural geometry — bounding-box measurements for
     architectural elements (windows, railings, stairs, ramps).
     Provides actual Height, SillHeight, HandrailHeight, Width, and Slope
     when those values are absent from property sets.

Usage:
  extractor = IFCGeometryExtractor(ifc_model)
  bbox  = extractor.get_bounding_box(element)
  value = extractor.get_geometry_value(element, "SillHeight", floor_z=0.0)
"""

import logging
import math
from typing import Optional

logger = logging.getLogger("bimguard.geometry")

try:
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.shape

    IFCOS_AVAILABLE = True
except ImportError:
    IFCOS_AVAILABLE = False
    logger.warning("ifcopenshell not available — geometry extraction will use estimation only")


# Properties that can be derived from a bounding box when Psets are empty.
# Keys are lowercase property names; values are the measurement method to call.
_GEOMETRY_PROPERTY_MAP: dict[str, str] = {
    # Vertical extent of the element itself
    "height":            "height",
    "overallheight":     "height",
    "clearheight":       "height",
    "nominalheight":     "height",
    "grossheight":       "height",
    # Width (horizontal extent)
    "width":             "width",
    "overallwidth":      "width",
    "clearwidth":        "width",
    "nominalwidth":      "width",
    "grosswidth":        "width",
    # Sill / bottom of element above the storey floor
    "sillheight":        "sill_height",
    "windowsillheight":  "sill_height",
    # Handrail / top of element above the storey floor
    "handrailheight":    "handrail_height",
    "railingheight":     "handrail_height",
    "barrierheight":     "handrail_height",
    # Slope / pitch (returned in degrees)
    "slope":             "slope_deg",
    "pitchangle":        "slope_deg",
    "requiredslope":     "slope_deg",
    "slopeangle":        "slope_deg",
    "gradient":          "slope_deg",
    # Headroom — vertical clearance of the element (stair flight height)
    "headroomclearance": "height",
    "requireheadroom":   "height",
    "headroom":          "height",
}


class IFCGeometryExtractor:
    """
    Extracts geometric properties from IFC elements via mesh tessellation.

    Tier 1 (architectural): bounding-box measurements — height, width,
    sill height, handrail height, slope.  Used as Pass 7 fallback when all
    Pset lookups in extract_for_compliance() return nothing.

    Pipe surface area (GC-001 corrosion engine): unchanged from before.
    """

    def __init__(self, ifc_model=None):
        self.model = ifc_model
        self._settings = None
        self._unit_scale: float = 1.0  # model-unit → mm
        if IFCOS_AVAILABLE and ifc_model is not None:
            try:
                self._settings = ifcopenshell.geom.settings()
                self._settings.set(self._settings.USE_WORLD_COORDS, True)
                self._unit_scale = self._detect_length_unit_scale(ifc_model)
            except Exception as e:
                logger.warning(f"Could not initialise geometry settings: {e}")

    # ── Unit detection ────────────────────────────────────────────────────────

    @staticmethod
    def _detect_length_unit_scale(ifc_model) -> float:
        """
        Return a multiplier that converts model length units to millimetres.
        Falls back to 1.0 (assumes mm) if detection fails.
        """
        _SI_TO_MM = {
            "MILLIMETRE": 1.0,
            "CENTIMETRE": 10.0,
            "METRE":      1000.0,
            "KILOMETRE":  1_000_000.0,
            "INCH":       25.4,
            "FOOT":       304.8,
        }
        try:
            for unit_assignment in ifc_model.by_type("IfcUnitAssignment"):
                for unit in unit_assignment.Units:
                    if not hasattr(unit, "UnitType"):
                        continue
                    if str(unit.UnitType) != "LENGTHUNIT":
                        continue
                    if unit.is_a("IfcSIUnit"):
                        prefix_factors = {"MILLI": 0.001, "CENTI": 0.01, "": 1.0, None: 1.0}
                        prefix = str(getattr(unit, "Prefix", "") or "")
                        name = str(getattr(unit, "Name", "METRE") or "METRE")
                        base_mm = _SI_TO_MM.get(name, 1000.0)
                        return base_mm * prefix_factors.get(prefix, 1.0)
                    if unit.is_a("IfcConversionBasedUnit"):
                        name = str(getattr(unit, "Name", "") or "").upper()
                        if "FOOT" in name:
                            return 304.8
                        if "INCH" in name:
                            return 25.4
        except Exception:
            pass
        return 1.0  # default: model is already in mm

    # ── SURFACE AREA ─────────────────────────────────────────────────────────

    def get_external_surface_area(
        self,
        element,
        nominal_diameter_m: float,
        insulation_thickness_m: float = 0.0,
        length_m: Optional[float] = None,
    ) -> dict:
        """
        Calculate the external surface area of a pipe element.

        Tries in order:
        1. Actual geometry via ifcopenshell.geom shape analysis
        2. Length from IfcQuantityLength quantity set
        3. Estimation from nominal diameter and default length

        Returns dict with keys:
          area_m2, area_with_insulation_m2, length_m, method
        """
        result = {
            "area_m2": None,
            "area_with_insulation_m2": None,
            "length_m": None,
            "method": "unknown",
        }

        # Try actual geometry first
        if self._settings is not None and element is not None:
            try:
                shape = ifcopenshell.geom.create_shape(self._settings, element)
                verts = shape.geometry.verts
                faces = shape.geometry.faces
                area = self._calculate_mesh_area(verts, faces)
                if area and area > 0:
                    result["area_m2"] = area
                    result["method"] = "geometry"
                    # Estimate length from area and nominal diameter
                    circumference = math.pi * nominal_diameter_m
                    if circumference > 0:
                        result["length_m"] = area / circumference
            except Exception as e:
                logger.debug(f"Geometry extraction failed for {element}: {e}")

        # Try quantity set for length
        if result["length_m"] is None and element is not None:
            qset_length = self._get_quantity_length(element)
            if qset_length:
                result["length_m"] = qset_length
                result["method"] = "quantity_set"
                result["area_m2"] = math.pi * nominal_diameter_m * qset_length

        # Fall back to provided length or default
        if result["length_m"] is None:
            fallback_length = length_m if length_m else self._default_length(nominal_diameter_m)
            result["length_m"] = fallback_length
            result["area_m2"] = math.pi * nominal_diameter_m * fallback_length
            if result["method"] == "unknown":
                result["method"] = "estimated"

        # Calculate area with insulation
        if result["area_m2"] is not None:
            outer_d = nominal_diameter_m + 2 * insulation_thickness_m
            result["area_with_insulation_m2"] = math.pi * outer_d * result["length_m"]

        return result

    def _calculate_mesh_area(self, verts: list, faces: list) -> Optional[float]:
        """
        Calculate surface area from a triangle mesh.
        verts: flat list [x0,y0,z0, x1,y1,z1, ...]
        faces: flat list [i0,i1,i2, i3,i4,i5, ...]
        """
        try:
            total = 0.0
            n_faces = len(faces) // 3
            for f in range(n_faces):
                i0 = faces[f * 3] * 3
                i1 = faces[f * 3 + 1] * 3
                i2 = faces[f * 3 + 2] * 3
                v0 = verts[i0 : i0 + 3]
                v1 = verts[i1 : i1 + 3]
                v2 = verts[i2 : i2 + 3]
                # Cross product magnitude / 2 = triangle area
                ab = [v1[j] - v0[j] for j in range(3)]
                ac = [v2[j] - v0[j] for j in range(3)]
                cross = [
                    ab[1] * ac[2] - ab[2] * ac[1],
                    ab[2] * ac[0] - ab[0] * ac[2],
                    ab[0] * ac[1] - ab[1] * ac[0],
                ]
                total += math.sqrt(sum(c**2 for c in cross)) / 2
            return total
        except Exception:
            return None

    def _get_quantity_length(self, element) -> Optional[float]:
        """
        Read pipe length from Qto_PipeSegmentBaseQuantities.Length
        or any IfcQuantityLength named 'Length'.
        """
        try:
            for rel in getattr(element, "IsDefinedBy", []):
                if not hasattr(rel, "RelatingPropertyDefinition"):
                    continue
                pdef = rel.RelatingPropertyDefinition
                if pdef.is_a("IfcElementQuantity"):
                    for qty in pdef.Quantities:
                        if qty.is_a("IfcQuantityLength") and "length" in qty.Name.lower():
                            return float(qty.LengthValue)
        except Exception:
            pass
        return None

    def _default_length(self, nominal_diameter_m: float) -> float:
        """
        Return a conservative default pipe segment length when
        no geometric or quantity data is available.
        Larger pipes tend to have longer standard segments.
        """
        if nominal_diameter_m <= 0.05:
            return 3.0
        elif nominal_diameter_m <= 0.15:
            return 6.0
        else:
            return 6.0

    # ── CENTROID EXTRACTION ───────────────────────────────────────────────────

    def get_centroid(self, element) -> tuple[float, float, float]:
        """
        Extract the centroid (x, y, z) of a pipe element in world coordinates.
        Falls back to (0, 0, 0) if geometry is unavailable.
        """
        if self._settings is None or element is None:
            return (0.0, 0.0, 0.0)
        try:
            shape = ifcopenshell.geom.create_shape(self._settings, element)
            verts = shape.geometry.verts
            n = len(verts) // 3
            if n == 0:
                return (0.0, 0.0, 0.0)
            x = sum(verts[i * 3] for i in range(n)) / n
            y = sum(verts[i * 3 + 1] for i in range(n)) / n
            z = sum(verts[i * 3 + 2] for i in range(n)) / n
            return (round(x, 4), round(y, 4), round(z, 4))
        except Exception:
            return (0.0, 0.0, 0.0)

    # ── TIER 1: BOUNDING-BOX GEOMETRY ────────────────────────────────────────

    def get_bounding_box(self, element) -> dict | None:
        """
        Return world-coordinate bounding box of any IFC element.

        Returns dict with min/max xyz in millimetres, or None if geometry
        is unavailable (no geom kernel, or element has no shape).
        """
        if self._settings is None or element is None:
            return None
        try:
            shape = ifcopenshell.geom.create_shape(self._settings, element)
            verts = shape.geometry.verts
            if not verts:
                return None
            s = self._unit_scale
            xs = [verts[i] * s for i in range(0, len(verts), 3)]
            ys = [verts[i] * s for i in range(1, len(verts), 3)]
            zs = [verts[i] * s for i in range(2, len(verts), 3)]
            return {
                "min_x": min(xs), "max_x": max(xs),
                "min_y": min(ys), "max_y": max(ys),
                "min_z": min(zs), "max_z": max(zs),
            }
        except Exception as e:
            logger.debug(f"Bounding box failed for {element}: {e}")
            return None

    def get_height_mm(self, element) -> float | None:
        """Vertical extent (max_z − min_z) in mm."""
        bbox = self.get_bounding_box(element)
        return round(bbox["max_z"] - bbox["min_z"], 1) if bbox else None

    def get_width_mm(self, element) -> float | None:
        """Horizontal extent — larger of X and Y spans — in mm."""
        bbox = self.get_bounding_box(element)
        if not bbox:
            return None
        return round(max(
            bbox["max_x"] - bbox["min_x"],
            bbox["max_y"] - bbox["min_y"],
        ), 1)

    def get_bottom_z_mm(self, element) -> float | None:
        """Lowest point of element in world coordinates (mm)."""
        bbox = self.get_bounding_box(element)
        return round(bbox["min_z"], 1) if bbox else None

    def get_top_z_mm(self, element) -> float | None:
        """Highest point of element in world coordinates (mm)."""
        bbox = self.get_bounding_box(element)
        return round(bbox["max_z"], 1) if bbox else None

    def get_slope_deg(self, element) -> float | None:
        """
        Slope angle in degrees estimated from bounding box.

        Meaningful for inclined elements (ramps, stair flights).
        Returns arctan(rise / run) where run is the longer horizontal span.
        """
        bbox = self.get_bounding_box(element)
        if not bbox:
            return None
        rise = bbox["max_z"] - bbox["min_z"]
        run = max(
            bbox["max_x"] - bbox["min_x"],
            bbox["max_y"] - bbox["min_y"],
        )
        if run <= 0:
            return None
        return round(math.degrees(math.atan(rise / run)), 2)

    def get_geometry_value(
        self,
        element,
        property_name: str,
        floor_z_mm: float | None = None,
    ) -> float | None:
        """
        Derive a compliance property value from bounding-box geometry.

        Args:
            element: IFC element instance.
            property_name: Rule property name (case-insensitive).
            floor_z_mm: World Z of the storey floor in mm.
                        Required for sill_height and handrail_height.

        Returns:
            Numeric value in mm (or degrees for slope), or None if not derivable.
        """
        method = _GEOMETRY_PROPERTY_MAP.get(property_name.lower())
        if method is None:
            return None

        if method == "height":
            return self.get_height_mm(element)

        if method == "width":
            return self.get_width_mm(element)

        if method == "slope_deg":
            return self.get_slope_deg(element)

        if method == "sill_height":
            bot = self.get_bottom_z_mm(element)
            if bot is None:
                return None
            ref = floor_z_mm if floor_z_mm is not None else 0.0
            return round(bot - ref, 1)

        if method == "handrail_height":
            top = self.get_top_z_mm(element)
            if top is None:
                return None
            ref = floor_z_mm if floor_z_mm is not None else 0.0
            return round(top - ref, 1)

        return None

    # ── AREA RATIO CALCULATION ────────────────────────────────────────────────

    def calculate_area_ratio(
        self,
        anode_area_m2: float,
        cathode_area_m2: float,
    ) -> tuple[float, str]:
        """
        Calculate the anode-to-cathode area ratio and return
        the GC-001 risk band classification.

        GC-001 area ratio bands:
          Favourable  > 5.0   multiplier 0.20
          Acceptable  2.0–5.0 multiplier 0.40
          Moderate    0.5–2.0 multiplier 0.60
          Unfavourable 0.1–0.5 multiplier 0.80
          Critical    < 0.1   multiplier 1.00
        """
        if cathode_area_m2 <= 0:
            return (1.0, "Critical")
        ratio = anode_area_m2 / cathode_area_m2
        if ratio > 5.0:
            return (ratio, "Favourable")
        elif ratio > 2.0:
            return (ratio, "Acceptable")
        elif ratio > 0.5:
            return (ratio, "Moderate")
        elif ratio > 0.1:
            return (ratio, "Unfavourable")
        else:
            return (ratio, "Critical")


# ── ESTIMATION UTILITIES (no IFC model required) ──────────────────────────────


def estimate_surface_area(
    nominal_diameter_m: float,
    length_m: float,
    insulation_thickness_m: float = 0.0,
) -> dict:
    """
    Estimate surface area from nominal dimensions without IFC geometry.
    Used as the default calculation when geometry extraction is unavailable.
    """
    pipe_area = math.pi * nominal_diameter_m * length_m
    insulated_d = nominal_diameter_m + 2 * insulation_thickness_m
    insulated_area = math.pi * insulated_d * length_m
    return {
        "area_m2": round(pipe_area, 4),
        "area_with_insulation_m2": round(insulated_area, 4),
        "length_m": length_m,
        "method": "nominal_diameter_estimate",
    }


def nps_to_od_m(nps_inch: float) -> float:
    """
    Convert NPS (nominal pipe size in inches) to actual outside diameter
    in metres per ASME B36.10M lookup table.
    Handles NPS 0.125 through NPS 24.
    """
    NPS_OD_TABLE = {
        0.125: 0.01080,
        0.25: 0.01350,
        0.375: 0.01730,
        0.5: 0.02130,
        0.75: 0.02670,
        1.0: 0.03340,
        1.25: 0.04220,
        1.5: 0.04830,
        2.0: 0.06030,
        2.5: 0.07300,
        3.0: 0.08890,
        3.5: 0.10160,
        4.0: 0.11430,
        5.0: 0.14130,
        6.0: 0.16830,
        8.0: 0.21910,
        10.0: 0.27305,
        12.0: 0.32385,
        14.0: 0.35560,
        16.0: 0.40640,
        18.0: 0.45720,
        20.0: 0.50800,
        22.0: 0.55880,
        24.0: 0.60960,
    }
    # Exact match
    if nps_inch in NPS_OD_TABLE:
        return NPS_OD_TABLE[nps_inch]
    # Interpolate
    keys = sorted(NPS_OD_TABLE.keys())
    for i, k in enumerate(keys[:-1]):
        if k < nps_inch < keys[i + 1]:
            ratio = (nps_inch - k) / (keys[i + 1] - k)
            od = NPS_OD_TABLE[k] + ratio * (NPS_OD_TABLE[keys[i + 1]] - NPS_OD_TABLE[k])
            return round(od, 5)
    # Extrapolate for large sizes
    return nps_inch * 0.0254


def dn_to_od_m(dn: int) -> float:
    """
    Convert DN (Diametre Nominal) to actual outside diameter in metres
    per EN 10220 / ISO 4200 for carbon and stainless steel pipe.
    DN values follow ASME-equivalent ODs for interchangeability.
    """
    DN_OD_TABLE = {
        6: 0.01080,
        8: 0.01350,
        10: 0.01730,
        15: 0.02130,
        20: 0.02670,
        25: 0.03340,
        32: 0.04220,
        40: 0.04830,
        50: 0.06030,
        65: 0.07300,
        80: 0.08890,
        90: 0.10160,
        100: 0.11430,
        125: 0.14130,
        150: 0.16830,
        200: 0.21910,
        250: 0.27305,
        300: 0.32385,
        350: 0.35560,
        400: 0.40640,
        450: 0.45720,
        500: 0.50800,
        600: 0.60960,
    }
    if dn in DN_OD_TABLE:
        return DN_OD_TABLE[dn]
    # Linear extrapolation for non-standard values
    return dn / 1000.0 * 1.05  # approximate
