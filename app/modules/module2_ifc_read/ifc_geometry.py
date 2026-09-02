"""
BIMGUARD AI — IFC Geometry Extraction
modules/ifc_geometry.py

Two responsibilities:

  1. Pipe surface area — used by the GC-001 corrosion engine.
     Reads actual mesh geometry or falls back to nominal-diameter estimation.

  2. Tier 1 architectural geometry — measurements for architectural elements
     (windows, railings, stairs, ramps, corridors, slabs).
     Derives Height, Width, SillHeight, HandrailHeight, Slope, Volume,
     FootprintArea, SurfaceArea, and CorridorWidth when those values are
     absent from property sets.

Native engine:
     All mesh operations now delegate to ifcopenshell.util.shape where
     available (v0.8+).  shapely (already a transitive dep) handles 2-D
     polygon analysis for corridor / room minimum-width computation.

Usage:
  extractor = IFCGeometryExtractor(ifc_model)
  bbox  = extractor.get_bounding_box(element)
  value = extractor.get_geometry_value(element, "SillHeight", floor_z_mm=0.0)
  w_mm  = extractor.get_corridor_width_mm(element)   # room/corridor narrow dim
  vol   = extractor.get_volume_m3(element)
"""

import logging
import math
from typing import Optional

logger = logging.getLogger("bimguard.geometry")

try:
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.shape as _ifcos_shape

    IFCOS_AVAILABLE = True
except ImportError:
    IFCOS_AVAILABLE = False
    logger.warning("ifcopenshell not available — geometry extraction will use estimation only")

try:
    import numpy as np
    _NP_AVAILABLE = True
except ImportError:
    _NP_AVAILABLE = False

try:
    import shapely.geometry
    import shapely.ops
    _SHAPELY_AVAILABLE = True
except ImportError:
    _SHAPELY_AVAILABLE = False

try:
    from scipy.spatial import cKDTree

    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False
    logger.warning("scipy not available — element proximity checks return Undetermined")


# ---------------------------------------------------------------------------
# Property → method name lookup
# Pass 7 in extract_for_compliance() calls get_geometry_value(element, prop)
# which resolves property names (lowercase) to method names via this map.
# ---------------------------------------------------------------------------
_GEOMETRY_PROPERTY_MAP: dict[str, str] = {
    # Vertical extent
    "height":              "height",
    "overallheight":       "height",
    "clearheight":         "height",
    "nominalheight":       "height",
    "grossheight":         "height",
    "headroomclearance":   "height",
    "requiredheadroom":    "height",
    "headroom":            "height",
    # Horizontal extent — axis-aligned max span
    "width":               "width",
    "overallwidth":        "width",
    "nominalwidth":        "width",
    "grosswidth":          "width",
    # Narrow dimension of room/corridor (minimum rotated rectangle)
    "clearwidth":          "corridor_width",
    "corridorwidth":       "corridor_width",
    "minimumwidth":        "corridor_width",
    "passagewidth":        "corridor_width",
    # Sill / bottom-above-floor
    "sillheight":          "sill_height",
    "windowsillheight":    "sill_height",
    "thresholdheight":     "sill_height",
    "doorthreshold":       "sill_height",
    # Top-above-floor (handrail / guard)
    "handrailheight":      "handrail_height",
    "railingheight":       "handrail_height",
    "barrierheight":       "handrail_height",
    # Slope / pitch (degrees)
    "slope":               "slope_deg",
    "pitchangle":          "slope_deg",
    "requiredslope":       "slope_deg",
    "slopeangle":          "slope_deg",
    "gradient":            "slope_deg",
    # Volume and area
    "volume":              "volume",
    "netvolume":           "volume",
    "grossvolume":         "volume",
    "footprintarea":       "footprint_area",
    "surfacearea":         "surface_area",
    "outersurfacearea":    "surface_area",
    # Perimeter
    "perimeter":           "footprint_perimeter",
    "footprintperimeter":  "footprint_perimeter",
}


# ---------------------------------------------------------------------------
# Point-to-triangle distance (narrow phase for calculate_shortest_distance)
# ---------------------------------------------------------------------------


def _point_to_triangle_distance(p, a, b, c):
    """Return the orthogonal distance from point *p* to each triangle (a, b, c).

    Vectorised over a batch of triangles: *p* is a single (3,) point while
    *a*, *b* and *c* are (M, 3) arrays of the triangles' corners. Returns an
    (M,) array of distances in the same units as the inputs.

    This is Ericson's closest-point-on-triangle (Real-Time Collision
    Detection, 5.1.5) evaluated in barycentric coordinates, with every region
    test written as a mask so the whole batch resolves in one pass. The seven
    Voronoi regions of a triangle -- its three corners, its three edges and
    its interior -- are each handled explicitly, so a point whose projection
    falls outside the triangle gets the distance to the nearest edge or
    corner rather than to the unbounded plane.

    Degenerate triangles (zero area, or a repeated corner) would divide by
    zero; their denominators are clamped and the corresponding results fall
    back to a corner distance, which is correct for a collapsed triangle.

    Args:
        p: The query point, shape (3,).
        a: First corner of each triangle, shape (M, 3).
        b: Second corner of each triangle, shape (M, 3).
        c: Third corner of each triangle, shape (M, 3).

    Returns:
        (M,) array of point-to-triangle distances.
    """
    p = np.asarray(p, dtype=float).reshape(3)
    a = np.atleast_2d(np.asarray(a, dtype=float))
    b = np.atleast_2d(np.asarray(b, dtype=float))
    c = np.atleast_2d(np.asarray(c, dtype=float))

    ab = b - a
    ac = c - a
    ap = p - a

    d1 = np.einsum("ij,ij->i", ab, ap)
    d2 = np.einsum("ij,ij->i", ac, ap)

    bp = p - b
    d3 = np.einsum("ij,ij->i", ab, bp)
    d4 = np.einsum("ij,ij->i", ac, bp)

    cp = p - c
    d5 = np.einsum("ij,ij->i", ab, cp)
    d6 = np.einsum("ij,ij->i", ac, cp)

    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2

    def _safe(denominator):
        """Avoid 0/0 on degenerate triangles; masked-out lanes are discarded."""
        return np.where(np.abs(denominator) < 1e-20, 1.0, denominator)

    # Interior (the general case) -- barycentric weights from the sub-areas.
    denom = _safe(va + vb + vc)
    v = vb / denom
    w = vc / denom
    closest = a + ab * v[:, None] + ac * w[:, None]

    # Edge BC.
    on_bc = (va <= 0.0) & ((d4 - d3) >= 0.0) & ((d5 - d6) >= 0.0)
    w_bc = (d4 - d3) / _safe((d4 - d3) + (d5 - d6))
    closest = np.where(on_bc[:, None], b + (c - b) * w_bc[:, None], closest)

    # Edge AC.
    on_ac = (vb <= 0.0) & (d2 >= 0.0) & (d6 <= 0.0)
    w_ac = d2 / _safe(d2 - d6)
    closest = np.where(on_ac[:, None], a + ac * w_ac[:, None], closest)

    # Edge AB.
    on_ab = (vc <= 0.0) & (d1 >= 0.0) & (d3 <= 0.0)
    v_ab = d1 / _safe(d1 - d3)
    closest = np.where(on_ab[:, None], a + ab * v_ab[:, None], closest)

    # Corners last, so they win over the edge regions they border.
    closest = np.where(((d6 >= 0.0) & (d5 <= d6))[:, None], c, closest)
    closest = np.where(((d3 >= 0.0) & (d4 <= d3))[:, None], b, closest)
    closest = np.where(((d1 <= 0.0) & (d2 <= 0.0))[:, None], a, closest)

    return np.linalg.norm(closest - p, axis=1)


class IFCGeometryExtractor:
    """
    Extracts geometric properties from IFC elements via ifcopenshell.geom tessellation.

    All mesh measurements delegate to ifcopenshell.util.shape (v0.8+) for
    accuracy.  shapely handles 2-D polygon analysis.

    Tier 1 (architectural): bounding-box + polygon measurements — height,
    width, corridor width, sill height, handrail height, slope, volume,
    footprint area, surface area.

    Pipe surface area (GC-001 corrosion engine): unchanged API, updated
    internals.
    """

    def __init__(self, ifc_model=None):
        self.model = ifc_model
        self._settings = None
        # Two distinct scales, because the mesher does NOT emit model units:
        #
        #   _unit_scale   model-unit → mm.  For values read straight from the
        #                 file (storey elevations, Pset lengths).  Module2
        #                 relies on this meaning when it scales floor_z.
        #   _mesher_scale mesher-output → mm.  ifcopenshell.geom normalises
        #                 tessellated coordinates to SI metres whenever the
        #                 model declares a length unit (convert-back-units is
        #                 False by default), so this is 1000.0 for a
        #                 millimetre model -- NOT 1.0.  Treating mesh output
        #                 as model units made every mm-model bounding box,
        #                 height, width and centroid 1000x too small.
        self._unit_scale: float = 1.0
        self._mesher_scale: float = 1.0
        # Keyed on the STEP entity instance id, never on id(element): see
        # _get_shape for why the Python object address is not an identity.
        self._shape_cache: dict[int, object] = {}  # STEP #id → shape
        # Triangle meshes and their KD-trees, keyed the same way and for the
        # same reason. XM-001 sweeps every dissimilar-material pair in a
        # network, so an element is queried once per candidate partner;
        # rebuilding its tree each time turns an O(n) extraction into O(n^2)
        # tessellations. The mesh caches the FACES alongside the vertices
        # because calculate_shortest_distance's narrow phase measures to
        # triangles, not to the vertex cloud alone.
        # STEP #id → ((N, 3) mm vertices, (M, 3) triangle indices) or None
        self._mesh_cache: dict[int, object] = {}
        self._kdtree_cache: dict[int, object] = {}   # STEP #id → cKDTree

        if IFCOS_AVAILABLE and ifc_model is not None:
            try:
                self._settings = ifcopenshell.geom.settings()
                self._settings.set(self._settings.USE_WORLD_COORDS, True)
                self._unit_scale = self._detect_length_unit_scale(ifc_model)
                self._mesher_scale = self._detect_mesher_scale_mm(
                    ifc_model, self._settings, self._unit_scale
                )
            except Exception as exc:
                logger.warning(f"Could not initialise geometry settings: {exc}")

    # ── Unit detection ────────────────────────────────────────────────────────

    @staticmethod
    def _has_declared_length_unit(ifc_model) -> bool:
        """Return True if the model's IfcUnitAssignment declares a LENGTHUNIT."""
        try:
            for ua in ifc_model.by_type("IfcUnitAssignment"):
                for unit in (ua.Units or []):
                    if not hasattr(unit, "UnitType"):
                        continue
                    if "LENGTHUNIT" in str(unit.UnitType).upper():
                        return True
        except Exception:
            pass
        return False

    @classmethod
    def _detect_mesher_scale_mm(cls, ifc_model, settings=None, unit_scale: float = 1.0) -> float:
        """Return multiplier that converts mesher output coordinates to mm.

        ifcopenshell.geom applies the model's declared length unit while
        tessellating and emits SI metres, regardless of whether the file is
        authored in millimetres, metres, feet or inches.  Two exceptions:

        * ``convert-back-units`` is enabled on *settings* -- the mesher then
          undoes that normalisation and emits model units.
        * The model declares no length unit at all -- the mesher has nothing
          to normalise with and passes raw coordinates through unchanged.

        In both exceptions the output is in model units, so the model-unit →
        mm factor (*unit_scale*) applies.  Otherwise the factor is a flat
        metres → mm conversion.
        """
        if settings is not None:
            try:
                if bool(settings.get("convert-back-units")):
                    return unit_scale
            except Exception:
                # Older ifcopenshell exposes the flag as an attribute constant.
                try:
                    if bool(settings.get(settings.CONVERT_BACK_UNITS)):
                        return unit_scale
                except Exception:
                    pass
        if not cls._has_declared_length_unit(ifc_model):
            return unit_scale
        return 1000.0

    @staticmethod
    def _detect_length_unit_scale(ifc_model) -> float:
        """Return multiplier that converts model length units to millimetres."""
        _SI_TO_MM = {
            "MILLIMETRE": 1.0, "MILLIMETER": 1.0,
            "CENTIMETRE": 10.0, "CENTIMETER": 10.0,
            "METRE":      1000.0, "METER":      1000.0,
            "KILOMETRE":  1_000_000.0, "KILOMETER":  1_000_000.0,
            "INCH":       25.4,
            "FOOT":       304.8,
        }
        try:
            for ua in ifc_model.by_type("IfcUnitAssignment"):
                for unit in ua.Units:
                    if not hasattr(unit, "UnitType"):
                        continue
                    if "LENGTHUNIT" not in str(unit.UnitType).upper():
                        continue
                    if unit.is_a("IfcSIUnit"):
                        # KILO included: without it, a kilometre-scaled model
                        # (Prefix=.KILO., Name=.METRE.) silently loses the
                        # 1000x prefix factor and is scaled as if it were
                        # plain metres.
                        prefix_factors = {
                            "MILLI": 0.001, "CENTI": 0.01, "KILO": 1000.0, "": 1.0,
                        }
                        # IFC enum values are uppercase by schema convention, but
                        # some exporters deviate — normalise defensively so this
                        # matches Module2_IFCRead._get_length_unit_scale_mm()
                        # (the Pset/attribute-side unit detector) exactly.
                        prefix = str(getattr(unit, "Prefix", "") or "").upper()
                        name = str(getattr(unit, "Name", "METRE") or "METRE").upper()
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
        return 1.0

    # ── Shape helper (cached) ─────────────────────────────────────────────────

    def _get_shape(self, element):
        """Return tessellated shape for *element*, cached by STEP entity id.

        The cache key must be the entity's own ``#id``, not ``id(element)``.
        ifcopenshell hands out a fresh ``entity_instance`` wrapper on every
        lookup and frees it when the caller drops it, so CPython reuses those
        addresses: fetching a model's spaces twice in a row, 31 of 99 addresses
        came back pointing at a *different* space. Keyed that way the cache
        silently answered one element with another element's geometry -- or
        with a cached ``None``, which is what made a space's derived Height or
        Width vanish and a rule stop firing between two otherwise identical
        runs.
        """
        if self._settings is None or element is None:
            return None
        try:
            eid = element.id()
        except Exception:
            # Not an ifcopenshell entity; nothing stable to key on, so measure
            # it and do not cache.
            return self._create_shape(element)
        if eid in self._shape_cache:
            return self._shape_cache[eid]
        shape = self._create_shape(element)
        self._shape_cache[eid] = shape
        return shape

    def _create_shape(self, element):
        """Tessellate *element*, returning None if ifcopenshell cannot."""
        try:
            return ifcopenshell.geom.create_shape(self._settings, element)
        except Exception as exc:
            logger.debug(f"create_shape failed for {element}: {exc}")
            return None

    # ── BOUNDING BOX ─────────────────────────────────────────────────────────

    def get_bounding_box(self, element) -> dict | None:
        """
        Return world-coordinate bounding box of any IFC element in millimetres.

        Uses ifcopenshell.util.shape.get_vertices() on the world-coord
        tessellation (USE_WORLD_COORDS=True).
        """
        shape = self._get_shape(element)
        if shape is None:
            return None
        try:
            s = self._mesher_scale
            if IFCOS_AVAILABLE and _NP_AVAILABLE:
                verts = _ifcos_shape.get_vertices(shape.geometry) * s
                return {
                    "min_x": float(verts[:, 0].min()), "max_x": float(verts[:, 0].max()),
                    "min_y": float(verts[:, 1].min()), "max_y": float(verts[:, 1].max()),
                    "min_z": float(verts[:, 2].min()), "max_z": float(verts[:, 2].max()),
                }
            # Fallback: manual flat-list approach
            raw = shape.geometry.verts
            xs = [raw[i] * s for i in range(0, len(raw), 3)]
            ys = [raw[i] * s for i in range(1, len(raw), 3)]
            zs = [raw[i] * s for i in range(2, len(raw), 3)]
            return {
                "min_x": min(xs), "max_x": max(xs),
                "min_y": min(ys), "max_y": max(ys),
                "min_z": min(zs), "max_z": max(zs),
            }
        except Exception as exc:
            logger.debug(f"Bounding box failed for {element}: {exc}")
            return None

    # ── DIMENSION MEASUREMENTS ────────────────────────────────────────────────

    def get_height_mm(self, element) -> float | None:
        """Vertical extent (Z dimension) in mm — ifcopenshell.util.shape.get_z()."""
        shape = self._get_shape(element)
        if shape is None:
            return None
        try:
            return round(_ifcos_shape.get_z(shape.geometry) * self._mesher_scale, 1)
        except Exception:
            return None

    def get_width_mm(self, element) -> float | None:
        """Larger horizontal span (max of X, Y) in mm — ifcopenshell.util.shape.get_max_xy()."""
        shape = self._get_shape(element)
        if shape is None:
            return None
        try:
            return round(_ifcos_shape.get_max_xy(shape.geometry) * self._mesher_scale, 1)
        except Exception:
            return None

    def get_bottom_z_mm(self, element) -> float | None:
        """Lowest world Z of element in mm — ifcopenshell.util.shape.get_bottom_elevation()."""
        shape = self._get_shape(element)
        if shape is None:
            return None
        try:
            return round(_ifcos_shape.get_bottom_elevation(shape.geometry) * self._mesher_scale, 1)
        except Exception:
            return None

    def get_top_z_mm(self, element) -> float | None:
        """Highest world Z of element in mm — ifcopenshell.util.shape.get_top_elevation()."""
        shape = self._get_shape(element)
        if shape is None:
            return None
        try:
            return round(_ifcos_shape.get_top_elevation(shape.geometry) * self._mesher_scale, 1)
        except Exception:
            return None

    def get_slope_deg(self, element) -> float | None:
        """Slope angle in degrees from bounding-box rise/run ratio."""
        shape = self._get_shape(element)
        if shape is None:
            return None
        try:
            s = self._mesher_scale
            rise = _ifcos_shape.get_z(shape.geometry) * s
            run  = _ifcos_shape.get_max_xy(shape.geometry) * s
            if run <= 0:
                return None
            return round(math.degrees(math.atan(rise / run)), 2)
        except Exception:
            return None

    # ── VOLUME AND AREA ───────────────────────────────────────────────────────

    def get_volume_m3(self, element) -> float | None:
        """
        Exact element volume in m³ via ifcopenshell.util.shape.get_volume().

        get_volume() returns value in mesher-unit³ (SI metres unless the
        model declares no length unit); scale to mm³ then convert to m³.
        """
        shape = self._get_shape(element)
        if shape is None:
            return None
        try:
            vol_native = _ifcos_shape.get_volume(shape.geometry)
            vol_mm3 = vol_native * (self._mesher_scale ** 3)
            return round(vol_mm3 / 1e9, 6)
        except Exception:
            return None

    def get_footprint_area_m2(self, element) -> float | None:
        """
        2-D footprint (top-down projected) area in m².
        Uses ifcopenshell.util.shape.get_footprint_area().
        """
        shape = self._get_shape(element)
        if shape is None:
            return None
        try:
            area_native = _ifcos_shape.get_footprint_area(shape.geometry)
            area_mm2 = area_native * (self._mesher_scale ** 2)
            return round(area_mm2 / 1e6, 4)
        except Exception:
            return None

    def get_footprint_perimeter_mm(self, element) -> float | None:
        """Perimeter of the 2-D footprint (top-down) in mm — ifcopenshell.util.shape.get_footprint_perimeter()."""
        shape = self._get_shape(element)
        if shape is None:
            return None
        try:
            return round(_ifcos_shape.get_footprint_perimeter(shape.geometry) * self._mesher_scale, 1)
        except Exception:
            return None

    def get_surface_area_m2(self, element) -> float | None:
        """
        Outer surface area in m².
        Uses ifcopenshell.util.shape.get_outer_surface_area().
        """
        shape = self._get_shape(element)
        if shape is None:
            return None
        try:
            area_native = _ifcos_shape.get_outer_surface_area(shape.geometry)
            area_mm2 = area_native * (self._mesher_scale ** 2)
            return round(area_mm2 / 1e6, 4)
        except Exception:
            return None

    # ── CORRIDOR / ROOM MINIMUM WIDTH ─────────────────────────────────────────

    def get_corridor_width_mm(self, element) -> float | None:
        """
        Minimum passable width of a room or corridor in mm.

        Algorithm:
          1. Project all tessellated vertices onto the XY plane.
          2. Compute convex hull → shapely Polygon.
          3. Find minimum rotated rectangle (tightest enclosing box).
          4. Return the shorter side length → the minimum clear width.

        This is accurate for rectangular corridors and gives a conservative
        estimate for L-shaped or irregular rooms.  Requires shapely (already
        installed as a transitive dependency of ifcopenshell).
        """
        if not _SHAPELY_AVAILABLE:
            logger.debug("shapely not available — corridor width check skipped")
            return None

        shape = self._get_shape(element)
        if shape is None:
            return None

        try:
            s = self._mesher_scale
            if _NP_AVAILABLE:
                verts = _ifcos_shape.get_vertices(shape.geometry)
                pts_2d = [(float(v[0] * s), float(v[1] * s)) for v in verts]
            else:
                raw = shape.geometry.verts
                pts_2d = [
                    (raw[i] * s, raw[i + 1] * s)
                    for i in range(0, len(raw), 3)
                ]

            if len(pts_2d) < 3:
                return None

            footprint = shapely.geometry.MultiPoint(pts_2d).convex_hull
            if footprint.geom_type not in ("Polygon",):
                return None

            mrr = footprint.minimum_rotated_rectangle
            coords = list(mrr.exterior.coords)
            side_lengths = [
                math.sqrt(
                    (coords[i][0] - coords[i + 1][0]) ** 2
                    + (coords[i][1] - coords[i + 1][1]) ** 2
                )
                for i in range(4)
            ]
            return round(min(side_lengths), 1)

        except Exception as exc:
            logger.debug(f"corridor_width failed for {element}: {exc}")
            return None

    # ── CENTROID ──────────────────────────────────────────────────────────────

    def get_centroid(self, element) -> tuple[float, float, float]:
        """Return centroid (x, y, z) in world mm.  Falls back to (0, 0, 0)."""
        shape = self._get_shape(element)
        if shape is None:
            return (0.0, 0.0, 0.0)
        try:
            if _NP_AVAILABLE:
                verts = _ifcos_shape.get_vertices(shape.geometry) * self._mesher_scale
                cx, cy, cz = verts.mean(axis=0)
                return (round(float(cx), 4), round(float(cy), 4), round(float(cz), 4))
            # Manual fallback
            raw = shape.geometry.verts
            s = self._mesher_scale
            n = len(raw) // 3
            if n == 0:
                return (0.0, 0.0, 0.0)
            cx = sum(raw[i * 3]     for i in range(n)) / n * s
            cy = sum(raw[i * 3 + 1] for i in range(n)) / n * s
            cz = sum(raw[i * 3 + 2] for i in range(n)) / n * s
            return (round(cx, 4), round(cy, 4), round(cz, 4))
        except Exception:
            return (0.0, 0.0, 0.0)

    def get_centroid_or_none(self, element) -> tuple[float, float, float] | None:
        """Return centroid (x, y, z) in world mm, or None if unresolvable.

        Unlike get_centroid(), never silently substitutes (0, 0, 0) for a
        failure — for callers that need to distinguish "no geometry
        available" from "genuinely placed at the world origin" (e.g. to
        fall back to a non-geometric estimate instead of computing a
        meaningless distance from/to the origin).
        """
        if self._get_shape(element) is None:
            return None
        return self.get_centroid(element)

    # ── PROXIMITY / SEPARATION ────────────────────────────────────────────────

    def _get_mesh_mm(self, element):
        """Return the element's world-coordinate triangle mesh, in millimetres.

        Returns ``(vertices, faces)`` where *vertices* is an (N, 3) float
        array of mm coordinates and *faces* is an (M, 3) integer array of
        indices into it — the triangles the narrow phase of
        calculate_shortest_distance measures against. Both are returned
        together, and cached together, because a vertex cloud on its own
        cannot answer "how far is this point from that surface?": a contact
        landing mid-face carries no vertex anywhere near it.

        Returns ``(None, None)`` when the element has no resolvable
        tessellation, when numpy is unavailable, or when the mesh is empty.
        *faces* alone may be None for a mesh whose vertices resolved but whose
        connectivity did not; callers must then fall back to the vertex cloud.
        Cached on the STEP entity id for the same identity reason as
        _get_shape.
        """
        if not _NP_AVAILABLE:
            return None, None

        eid = None
        try:
            eid = element.id()
        except Exception:
            eid = None
        if eid is not None and eid in self._mesh_cache:
            return self._mesh_cache[eid]

        verts = None
        faces = None
        shape = self._get_shape(element)
        if shape is not None:
            try:
                if IFCOS_AVAILABLE:
                    verts = np.asarray(
                        _ifcos_shape.get_vertices(shape.geometry), dtype=float
                    ) * self._mesher_scale
                else:
                    raw = shape.geometry.verts
                    verts = (
                        np.asarray(raw, dtype=float).reshape(-1, 3) * self._mesher_scale
                    )
                if verts.size == 0:
                    verts = None
            except Exception as exc:
                logger.debug(f"vertex extraction failed for {element}: {exc}")
                verts = None

            if verts is not None:
                try:
                    if IFCOS_AVAILABLE:
                        faces = np.asarray(
                            _ifcos_shape.get_faces(shape.geometry), dtype=np.intp
                        )
                    else:
                        faces = np.asarray(
                            shape.geometry.faces, dtype=np.intp
                        ).reshape(-1, 3)
                    if faces.size == 0:
                        faces = None
                    else:
                        faces = faces.reshape(-1, 3)
                except Exception as exc:
                    logger.debug(f"face extraction failed for {element}: {exc}")
                    faces = None

        mesh = (verts, faces)
        if eid is not None:
            self._mesh_cache[eid] = mesh
        return mesh

    def _get_vertices_mm(self, element):
        """Return just the (N, 3) mm vertex cloud from _get_mesh_mm, or None."""
        return self._get_mesh_mm(element)[0]

    def _get_kdtree(self, element):
        """Return a cKDTree over the element's world vertices, or None."""
        if not _SCIPY_AVAILABLE:
            return None

        eid = None
        try:
            eid = element.id()
        except Exception:
            eid = None
        if eid is not None and eid in self._kdtree_cache:
            return self._kdtree_cache[eid]

        verts = self._get_vertices_mm(element)
        tree = None
        if verts is not None:
            try:
                tree = cKDTree(verts)
            except Exception as exc:
                logger.debug(f"cKDTree build failed for {element}: {exc}")
                tree = None

        if eid is not None:
            self._kdtree_cache[eid] = tree
        return tree

    @staticmethod
    def _surface_distance_from(point, verts, faces, vertex_index):
        """Distance from *point* to the faces of a mesh incident on one vertex.

        The narrow phase of calculate_shortest_distance. *vertex_index* is the
        broad phase's answer — the mesh vertex nearest *point* — and the
        triangles that share it are the only ones that can carry a closer
        surface point, so only those are measured.

        Returns None when the mesh has no connectivity or no triangle touches
        that vertex, which the caller reads as "no narrow-phase improvement"
        rather than as a measurement.
        """
        if faces is None or verts is None:
            return None
        incident = faces[np.any(faces == vertex_index, axis=1)]
        if incident.size == 0:
            return None
        distances = _point_to_triangle_distance(
            point,
            verts[incident[:, 0]],
            verts[incident[:, 1]],
            verts[incident[:, 2]],
        )
        if distances.size == 0:
            return None
        return float(np.min(distances))

    def calculate_shortest_distance(self, element_a, element_b) -> float | None:
        """Return the shortest distance between two elements in millimetres.

        Both elements are tessellated in world coordinates and measured in two
        phases:

          * Broad phase — a scipy cKDTree over one vertex cloud, queried by
            the other, finds the closest vertex PAIR in O(log N) per query.
          * Narrow phase — the triangles incident on each of those two
            vertices are measured against the opposite vertex with
            _point_to_triangle_distance, giving a true point-to-surface
            distance rather than a point-to-point one.

        The narrow phase is what closes the mid-span blind spot: two coarse
        boxes meeting along a face interior — a branch tee landing mid-span on
        a riser — carry no vertices near the contact patch, so a
        vertex-to-vertex read put them hundreds of millimetres apart while
        their surfaces were touching. Measuring to the face reads 0 mm.

        Both directions are measured and the minimum taken, so the result
        stays symmetric: it does not depend on which cloud builds the tree.

        Tri-state contract — this returns None (Undetermined), never a
        distance the caller could mistake for a measurement, whenever the
        separation cannot be established:

          * either element is None, or has no resolvable geometry;
          * either tessellation is empty;
          * numpy or scipy is unavailable.

        A caller must therefore treat None as "not assessed" and must not
        compare it against a clearance threshold.

        Accuracy note: the narrow phase searches only the triangles incident
        on the broad phase's closest vertex pair, which is exact whenever the
        true closest surface point lies on one of them — the case for the
        contact and near-contact geometry XM-001 asks about. It remains an
        upper bound in the general case (a long sliver face whose nearest
        point sits far from every vertex of the closest pair), so the result
        is sound for "are these two elements touching or near-touching?" and
        still unsuitable for certifying a precise clearance. A mesh whose
        connectivity the mesher did not supply falls back to the
        vertex-to-vertex distance.

        Args:
            element_a: First IFC element.
            element_b: Second IFC element.

        Returns:
            Shortest surface distance in mm, or None if undetermined.
        """
        if element_a is None or element_b is None:
            return None
        if not (_SCIPY_AVAILABLE and _NP_AVAILABLE):
            logger.debug("shortest distance undetermined — scipy/numpy unavailable")
            return None

        verts_a, faces_a = self._get_mesh_mm(element_a)
        if verts_a is None:
            return None
        verts_b, faces_b = self._get_mesh_mm(element_b)
        if verts_b is None:
            return None

        tree_a = self._get_kdtree(element_a)
        if tree_a is None:
            return None

        try:
            # Broad phase: the closest vertex pair, and the vertex distance
            # that is the upper bound the narrow phase refines downward.
            distances, a_indices = tree_a.query(verts_b, k=1)
            b_index = int(np.argmin(distances))
            a_index = int(a_indices[b_index])
            best = float(distances[b_index])

            # Narrow phase, once per direction so the result stays symmetric.
            for point, verts, faces, index in (
                (verts_a[a_index], verts_b, faces_b, b_index),
                (verts_b[b_index], verts_a, faces_a, a_index),
            ):
                surface = self._surface_distance_from(point, verts, faces, index)
                if surface is not None and surface < best:
                    best = surface

            return round(best, 4)
        except Exception as exc:
            logger.debug(f"shortest distance failed for {element_a}/{element_b}: {exc}")
            return None

    # ── GEOMETRY VALUE DISPATCHER ─────────────────────────────────────────────

    def get_geometry_value(
        self,
        element,
        property_name: str,
        floor_z_mm: float | None = None,
    ) -> float | None:
        """
        Derive a compliance property value from geometry.

        Args:
            element:       IFC element instance.
            property_name: Rule property name (case-insensitive).
            floor_z_mm:    World Z of the storey floor in mm.
                           Required for sill_height and handrail_height.

        Returns:
            Numeric value in mm (or degrees for slope, or m³ for volume),
            or None if not derivable.
        """
        method = _GEOMETRY_PROPERTY_MAP.get(property_name.lower())
        if method is None:
            return None

        if method == "height":
            return self.get_height_mm(element)

        if method == "width":
            return self.get_width_mm(element)

        if method == "corridor_width" and element is not None and element.is_a() in (
            "IfcDoor", "IfcDoorStandardCase", "IfcWindow", "IfcWindowStandardCase",
        ):
            # get_corridor_width_mm() returns the SHORTER side of the element's
            # own footprint -- correct for a room/corridor (its narrow passable
            # dimension) but not for a door/window leaf, whose own footprint is
            # a thin panel: the shorter side there is the frame/leaf thickness,
            # not the openable width. OverallWidth (the larger horizontal span)
            # is the closest available proxy for clear/passage width on these
            # elements -- see docs/ifc-property-mapping.md's ClearWidth row.
            return self.get_width_mm(element)

        if method == "corridor_width":
            return self.get_corridor_width_mm(element)

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

        if method == "volume":
            vol = self.get_volume_m3(element)
            return round(vol * 1e9, 1) if vol is not None else None  # return mm³ for consistency

        if method == "footprint_area":
            area = self.get_footprint_area_m2(element)
            return round(area * 1e6, 1) if area is not None else None  # return mm² for consistency

        if method == "surface_area":
            area = self.get_surface_area_m2(element)
            return round(area * 1e6, 1) if area is not None else None

        if method == "footprint_perimeter":
            return self.get_footprint_perimeter_mm(element)

        return None

    # ── SURFACE AREA FOR PIPE CORROSION (GC-001) ─────────────────────────────

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
        1. Outer surface area via ifcopenshell.util.shape.get_outer_surface_area()
        2. Length from IfcQuantityLength quantity set
        3. Estimation from nominal diameter and default length

        Returns dict with keys: area_m2, area_with_insulation_m2, length_m, method
        """
        result = {
            "area_m2": None,
            "area_with_insulation_m2": None,
            "length_m": None,
            "method": "unknown",
        }

        # Try actual geometry first
        area_m2 = self.get_surface_area_m2(element)
        if area_m2 and area_m2 > 0:
            result["area_m2"] = area_m2
            result["method"] = "geometry"
            circumference = math.pi * nominal_diameter_m
            if circumference > 0:
                result["length_m"] = area_m2 / circumference

        # Try quantity set for length if geometry gave nothing
        if result["length_m"] is None and element is not None:
            qset_length = self._get_quantity_length(element)
            if qset_length:
                result["length_m"] = qset_length
                result["method"] = "quantity_set"
                result["area_m2"] = math.pi * nominal_diameter_m * qset_length

        # Fall back to provided or default length
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

    def _get_quantity_length(self, element) -> Optional[float]:
        """Read pipe length from Qto_PipeSegmentBaseQuantities.Length."""
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
        if nominal_diameter_m <= 0.05:
            return 3.0
        return 6.0

    # ── AREA RATIO (GC-001 corrosion) ─────────────────────────────────────────

    def calculate_area_ratio(
        self,
        anode_area_m2: float,
        cathode_area_m2: float,
    ) -> tuple[float, str]:
        """GC-001 anode-to-cathode area ratio and risk band."""
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
    """Estimate pipe surface area from nominal dimensions (no IFC geometry needed)."""
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
    """Convert NPS (nominal pipe size in inches) to OD in metres per ASME B36.10M."""
    NPS_OD_TABLE = {
        0.125: 0.01080, 0.25: 0.01350, 0.375: 0.01730, 0.5: 0.02130,
        0.75: 0.02670, 1.0: 0.03340, 1.25: 0.04220, 1.5: 0.04830,
        2.0: 0.06030, 2.5: 0.07300, 3.0: 0.08890, 3.5: 0.10160,
        4.0: 0.11430, 5.0: 0.14130, 6.0: 0.16830, 8.0: 0.21910,
        10.0: 0.27305, 12.0: 0.32385, 14.0: 0.35560, 16.0: 0.40640,
        18.0: 0.45720, 20.0: 0.50800, 22.0: 0.55880, 24.0: 0.60960,
    }
    if nps_inch in NPS_OD_TABLE:
        return NPS_OD_TABLE[nps_inch]
    keys = sorted(NPS_OD_TABLE.keys())
    for i, k in enumerate(keys[:-1]):
        if k < nps_inch < keys[i + 1]:
            ratio = (nps_inch - k) / (keys[i + 1] - k)
            return NPS_OD_TABLE[k] + ratio * (NPS_OD_TABLE[keys[i + 1]] - NPS_OD_TABLE[k])
    return nps_inch * 0.0254


def dn_to_od_m(dn: int) -> float:
    """Convert DN to OD in metres per EN 10220 / ISO 4200."""
    DN_OD_TABLE = {
        6: 0.01080, 8: 0.01350, 10: 0.01730, 15: 0.02130, 20: 0.02670,
        25: 0.03340, 32: 0.04220, 40: 0.04830, 50: 0.06030, 65: 0.07300,
        80: 0.08890, 90: 0.10160, 100: 0.11430, 125: 0.14130, 150: 0.16830,
        200: 0.21910, 250: 0.27305, 300: 0.32385, 350: 0.35560, 400: 0.40640,
        450: 0.45720, 500: 0.50800, 600: 0.60960,
    }
    if dn in DN_OD_TABLE:
        return DN_OD_TABLE[dn]
    return dn / 1000.0 * 1.05
