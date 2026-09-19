"""
app/modules/blue_halo/halo_volume_generator.py

Blue Halo — Phase 1: generic, standard-agnostic seismic bracing clearance
algorithm skeleton.

Blue Halo generates a 3D clearance envelope ("halo volume") around a braced
MEP element (pipe, duct, conduit run), detects clashes between that envelope
and neighbouring building elements, and exports the result as an IFC
property set and a BCF 2.1 issue for coordination.

PHASE 1 SCOPE
    This module implements the algorithm shape only: data structures, the
    core generation/detection/export functions, and generic geometry math
    (bounding-box expansion, AABB intersection). It contains NO
    jurisdiction-specific numbers (spacing, clearance, angle limits) —
    those are supplied at runtime via ClearanceRule / ClearanceConfig,
    loaded from JSON files produced in Phase 2 (see load_clearance_config).

    Anything that genuinely requires a standard's numeric thresholds (e.g.
    "is 50mm enough clearance for a hospital in seismic zone 2") is a
    parameter, never a constant, in this file.

UNITS
    Distances:  millimetres (mm)   — fields end _mm
    Angles:     degrees            — fields end _degrees
    Volumes:    cubic millimetres (mm^3) — fields end _mm3

    IFC geometry is read in whatever length unit the model declares and
    converted to mm before it enters any data structure defined here.

DEPENDENCIES
    ifcopenshell is used only for reading element geometry/placement and is
    optional at the type-hint level (IfcElement is an Any-based alias) so
    this module can be imported and unit-tested without a loaded model.

OWNERSHIP
    Blue Halo Phase 1 (this file): generic algorithm.
    Blue Halo Phase 2 (JSON configs): clearance data, e.g.
        data/rulesets/sb001_seismic_clearance.json (authored screening
        calibration with per-threshold provenance).
    Blue Halo Phase 3+: config-driven wiring into Module 4 comparators.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, Sequence

import ifcopenshell
import ifcopenshell.util.placement
import ifcopenshell.util.unit
import numpy as np

SCHEMA_VERSION = "0.1.0"

# ifcopenshell entities have no dedicated Python type; this alias documents
# intent at call sites (an open model's IfcElement) without requiring
# ifcopenshell's C extension types to be importable for type-checking.
IfcElement = Any
IfcModel = Any


# ---------------------------------------------------------------------------
# Time helper
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """UTC timestamp in ISO 8601 (trailing Z), second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# BraceType — generic bracing hardware taxonomy
# ---------------------------------------------------------------------------
# Deliberately standard-agnostic: the bracing hardware any clearance config
# describes (angle iron, cable, rod, ...) reduces to some subset of these
# physical hardware categories. Jurisdiction-specific sub-variants
# (e.g. NFPA's "fire" vs "mechanical" angle iron) are carried on
# ClearanceRule.variant, not as separate enum members, so this taxonomy
# never needs to grow when a new standard is onboarded in Phase 2.


class BraceType(str, Enum):
    ANGLE_IRON = "angle_iron"
    CABLE = "cable"
    ROD = "rod"
    STRUT = "strut"
    OTHER = "other"


_BRACE_TYPE_KEY_PREFIXES: tuple[tuple[str, BraceType], ...] = (
    ("angle", BraceType.ANGLE_IRON),
    ("cable", BraceType.CABLE),
    ("rod", BraceType.ROD),
    ("strut", BraceType.STRUT),
)


def _classify_brace_type(config_key: str) -> BraceType:
    """Map a jurisdiction config's brace_types key to a generic BraceType.

    Args:
        config_key: Key from the config's "brace_types" object, e.g.
            "angle_fire", "angle_mechanical", "cable", "rod".

    Returns:
        The matching BraceType, or OTHER when no prefix matches.
    """
    key = config_key.lower().strip()
    for prefix, brace_type in _BRACE_TYPE_KEY_PREFIXES:
        if key.startswith(prefix):
            return brace_type
    return BraceType.OTHER


# ---------------------------------------------------------------------------
# Geometry primitives (millimetres)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Point3D:
    """A point in world space, millimetres."""

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class BoundingBox:
    """An axis-aligned bounding box, millimetres."""

    min: Point3D
    max: Point3D

    @property
    def size(self) -> tuple[float, float, float]:
        """Extent along (x, y, z), in mm. Zero or negative if empty/invalid."""
        return (
            self.max.x - self.min.x,
            self.max.y - self.min.y,
            self.max.z - self.min.z,
        )

    @property
    def volume_mm3(self) -> float:
        """Volume in mm^3. Zero if the box has a zero or negative extent."""
        sx, sy, sz = self.size
        if sx <= 0 or sy <= 0 or sz <= 0:
            return 0.0
        return sx * sy * sz

    def expanded(self, margin_mm: float) -> "BoundingBox":
        """Return a copy grown uniformly by margin_mm on every face.

        Phase 1 uses a uniform buffer as the clearance envelope shape.
        Angle-aware (wedge) envelopes for diagonal bracing are a later-phase
        refinement, not implemented here.
        """
        return BoundingBox(
            min=Point3D(self.min.x - margin_mm, self.min.y - margin_mm, self.min.z - margin_mm),
            max=Point3D(self.max.x + margin_mm, self.max.y + margin_mm, self.max.z + margin_mm),
        )

    def intersection(self, other: "BoundingBox") -> Optional["BoundingBox"]:
        """Return the overlapping region with `other`, or None if disjoint."""
        lo = Point3D(
            max(self.min.x, other.min.x),
            max(self.min.y, other.min.y),
            max(self.min.z, other.min.z),
        )
        hi = Point3D(
            min(self.max.x, other.max.x),
            min(self.max.y, other.max.y),
            min(self.max.z, other.max.z),
        )
        if lo.x >= hi.x or lo.y >= hi.y or lo.z >= hi.z:
            return None
        return BoundingBox(min=lo, max=hi)


# ---------------------------------------------------------------------------
# ClearanceRule / ClearanceConfig — pluggable, jurisdiction-specific data
# ---------------------------------------------------------------------------
# Populated exclusively by load_clearance_config() from a Phase 2 JSON file.
# No member of this dataclass has a real-world default value in Phase 1.


@dataclass
class ClearanceRule:
    """Clearance and spacing requirements for one brace hardware variant.

    Every field originates from a specific standard's clause; `citations`
    and `source_section` exist so a reviewer can trace any generated halo
    volume back to the rule (and clause) that produced it.
    """

    brace_type: BraceType
    variant: str  # raw config key, e.g. "angle_fire" — preserves sub-classification BraceType collapses

    base_clearance_mm: float
    adjacent_system_clearance_mm: float
    seismic_zone_addition_mm: float
    hospital_addition_mm: float

    spacing_transverse_m: float
    spacing_longitudinal_m: float

    angle_min_degrees: float
    angle_ideal_degrees: float
    angle_max_degrees: float
    angle_tolerance_degrees: float

    standard_sizes: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)

    def effective_clearance_mm(
        self,
        *,
        seismic_zone: bool = False,
        building_type: str = "standard",
    ) -> float:
        """Compute the total clearance to apply, mm.

        Args:
            seismic_zone: Whether the site is in a declared seismic zone
                that adds a clearance margin under this rule's standard.
            building_type: Building occupancy category as used by the
                standard's importance-factor table, e.g. "hospital".
                Anything other than "hospital" is treated as standard.

        Returns:
            base_clearance_mm plus any applicable additions. Does not
            include adjacent_system_clearance_mm, which applies between
            two braced systems rather than to a single halo volume.
        """
        clearance = self.base_clearance_mm
        if seismic_zone:
            clearance += self.seismic_zone_addition_mm
        if building_type.strip().lower() == "hospital":
            clearance += self.hospital_addition_mm
        return clearance

    def angle_in_range(self, angle_degrees: float) -> bool:
        """Whether angle_degrees falls within [angle_min, angle_max]."""
        return self.angle_min_degrees <= angle_degrees <= self.angle_max_degrees


@dataclass
class ClearanceConfig:
    """A fully-loaded jurisdiction config: one or more ClearanceRules plus
    the metadata needed to cite and audit them."""

    jurisdiction: str
    standards_cited: list[str]
    rules: dict[str, ClearanceRule]  # keyed by ClearanceRule.variant
    importance_factors: dict[str, float] = field(default_factory=dict)
    pipe_diameter_threshold_mm: Optional[float] = None
    duct_area_threshold_m2: Optional[float] = None
    data_gaps: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)  # full parsed JSON, for audit trail

    def rules_for(self, brace_type: BraceType) -> list[ClearanceRule]:
        """Return every loaded rule matching a generic BraceType.

        A jurisdiction may define multiple variants of the same hardware
        category (e.g. "angle_fire" and "angle_mechanical" both classify
        as ANGLE_IRON); callers that need one specific variant should index
        `rules` directly by its config key instead.
        """
        return [r for r in self.rules.values() if r.brace_type is brace_type]


def load_clearance_config(config_path: str | Path) -> ClearanceConfig:
    """Load a jurisdiction-specific clearance config from JSON.

    Expects the Blue Halo Phase 2 config shape (see
    data/rulesets/sb001_seismic_clearance.json): a top-level "metadata"
    object, a "brace_types" object keyed by hardware variant, a "clearance_rules" object of shared clearance
    additions, and an "angle_constraints" object. The shipped SB-001
    config is the reference instance of that shape.

    Args:
        config_path: Path to the jurisdiction's JSON config file.

    Returns:
        A ClearanceConfig with one ClearanceRule per "brace_types" entry.

    Raises:
        FileNotFoundError: If config_path does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        KeyError: If a required top-level section is missing.
    """
    path = Path(config_path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    metadata = raw.get("metadata", {})
    clearance_shared = raw.get("clearance_rules", {})
    angle = raw.get("angle_constraints", {})
    thresholds = raw.get("thresholds", {})
    seismic = raw.get("seismic_parameters", {})

    rules: dict[str, ClearanceRule] = {}
    for variant_key, brace_data in raw.get("brace_types", {}).items():
        rules[variant_key] = ClearanceRule(
            brace_type=_classify_brace_type(variant_key),
            variant=variant_key,
            base_clearance_mm=float(
                brace_data.get("clearance_mm", clearance_shared.get("base_from_structure_mm", 0.0))
            ),
            adjacent_system_clearance_mm=float(clearance_shared.get("adjacent_system_mm", 0.0)),
            seismic_zone_addition_mm=float(clearance_shared.get("seismic_zone_addition_mm", 0.0)),
            hospital_addition_mm=float(clearance_shared.get("hospital_addition_mm", 0.0)),
            spacing_transverse_m=float(brace_data.get("spacing_transverse_m", 0.0)),
            spacing_longitudinal_m=float(brace_data.get("spacing_longitudinal_m", 0.0)),
            angle_min_degrees=float(angle.get("min_degrees", 0.0)),
            angle_ideal_degrees=float(angle.get("ideal_degrees", 0.0)),
            angle_max_degrees=float(angle.get("max_degrees", 0.0)),
            angle_tolerance_degrees=float(angle.get("tolerance_degrees", 0.0)),
            standard_sizes=list(brace_data.get("standard_sizes", [])),
            citations=list(raw.get("standards_full_citations", [])),
        )

    return ClearanceConfig(
        jurisdiction=str(metadata.get("jurisdiction", path.stem)),
        standards_cited=list(metadata.get("standards_cited", [])),
        rules=rules,
        importance_factors=dict(seismic.get("importance_factors", {})),
        pipe_diameter_threshold_mm=(
            float(thresholds["pipe_diameter_mm"]) if thresholds.get("pipe_diameter_mm") is not None else None
        ),
        duct_area_threshold_m2=(
            float(thresholds["duct_area_sqm"]) if thresholds.get("duct_area_sqm") is not None else None
        ),
        data_gaps=list(metadata.get("data_gaps", [])),
        raw=raw,
    )


# ---------------------------------------------------------------------------
# HaloVolume / ClashReport — algorithm outputs
# ---------------------------------------------------------------------------


@dataclass
class HaloVolume:
    """A generated seismic bracing clearance envelope for one element."""

    id: str
    source_element_id: str  # IFC GlobalId of the braced element
    source_ifc_class: str
    brace_type: BraceType
    element_bbox_mm: BoundingBox  # the braced element's own geometry
    halo_bbox_mm: BoundingBox  # element_bbox_mm expanded by clearance_mm
    clearance_mm: float  # effective clearance actually applied
    rule_variant: Optional[str] = None  # ClearanceRule.variant that produced this
    generated_at: str = field(default_factory=_now_iso)
    metadata: dict = field(default_factory=dict)


ClashSeverity = Literal["minor", "major", "critical"]


@dataclass
class ClashReport:
    """One detected intrusion into a HaloVolume by another element."""

    id: str
    halo_id: str
    halo_source_element_id: str
    clashing_element_id: str
    clashing_element_class: str
    overlap_bbox_mm: BoundingBox
    overlap_volume_mm3: float
    severity: ClashSeverity
    description: str
    detected_at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class ElementGeometry:
    """The minimum geometry input the core Blue Halo algorithm needs.

    Decouples halo generation/clash detection from ifcopenshell: produced
    either from a real IFC entity via element_bbox_mm (see
    generate_halo_volume / detect_halo_clash), or directly by a caller —
    a test harness, or a producer that already computed an element's
    bounding box (e.g. ifc_reader/piping_producer.py) — that has no
    need to re-extract geometry from a live model.
    """

    element_id: str
    ifc_class: str
    bbox_mm: BoundingBox

    #: Cross-section declared by the element's swept profile, mm, where it
    #: declares one. Read via element_diameter_mm rather than inferred from
    #: bbox_mm, because a swept solid's box collapses to its extrusion axis and
    #: carries no thickness. None when the element declares no profile
    #: dimension; optional so existing callers that build geometry by hand are
    #: unaffected.
    nominal_diameter_mm: Optional[float] = None


# ---------------------------------------------------------------------------
# IFC geometry helpers
# ---------------------------------------------------------------------------
# Vertex-based bounding box extraction, not full ifcopenshell.geom
# tessellation — adequate for a clearance envelope and far cheaper on
# whole-model runs. Mirrors the approach in ifc_reader/piping_producer.py,
# but reads leaf geometry as raw arguments and shares mapped sources across
# elements (see the note above _as_points) so a large model stays tractable.


def unit_scale_to_mm(model: IfcModel) -> float:
    """Return the factor converting model length units to millimetres.

    Args:
        model: An open ifcopenshell model.

    Returns:
        The scale factor, or 1.0 (assume the model is already in mm) if it
        cannot be determined.
    """
    try:
        metres_scale = float(ifcopenshell.util.unit.calculate_unit_scale(model))
        if math.isfinite(metres_scale) and metres_scale > 0:
            return metres_scale * 1000.0
    except Exception:
        pass
    return 1.0


def _placement_matrix(entity: IfcElement) -> Optional[Any]:
    """Return the entity's 4x4 local-placement matrix, or None."""
    placement = getattr(entity, "ObjectPlacement", None)
    if placement is None:
        return None
    try:
        return ifcopenshell.util.placement.get_local_placement(placement)
    except Exception:
        return None


def _apply_many(matrix: Any, points: np.ndarray) -> np.ndarray:
    """Transform an ``(N, 3)`` array of local points by a 4x4 placement matrix.

    The arithmetic is ``m00*x + m01*y + m02*z + m03`` applied elementwise, in
    that order, and deliberately not a matrix product: BLAS is free to reorder
    and fuse the sums of a product, and a bounding box that moves in its last
    digit can flip a clash that only just touches. The same operations in the
    same order give the result of transforming one point at a time, bit for bit.

    Args:
        matrix: A 4x4 transform, indexable as ``matrix[row][col]``.
        points: Local coordinates, one point per row.

    Returns:
        The transformed points, same shape as *points*.
    """
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    return np.column_stack(
        [
            matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
            matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
            matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
        ]
    )


#: How deep the walker follows nested IfcMappedItem references. Real exports
#: nest one level, occasionally two; the cap exists only so a malformed model
#: that maps a representation onto itself cannot recurse forever.
_MAX_MAPPED_DEPTH = 4

#: The result for an item that contributes no vertices. Read-only because it is
#: shared: callers concatenate it, and none may write to it.
_NO_POINTS = np.empty((0, 3), dtype=np.float64)
_NO_POINTS.flags.writeable = False

#: Vertices of one mapped source, keyed ``(MappedRepresentation step id, depth)``.
#: One per model: step ids are only unique within a file.
MappedSourceCache = dict[tuple[int, int], np.ndarray]


# WHY THE LEAF WALKERS READ RAW ARGUMENTS
#
#     ``entity_instance.__getattr__`` costs about six wrapper calls per
#     attribute (category, index, method table, ``get_argument``, ``wrap_value``
#     and a recursive Python ``walk`` that builds a wrapper object for every
#     point in a tuple). Walking a faceted brep that way is per-vertex Python,
#     and a hospital architecture model holds millions of vertices: an 80 MB
#     file took ~580 ms per proxy element, ~2.5 h projected for the model, with
#     the seismic run sitting at "IFC Parsing" the whole time.
#
#     The walkers below therefore read ``wrapped_data.get_argument(0)``
#     directly. Index 0 is the attribute wanted on every entity they touch --
#     Outer, CfsFaces, FbsmFaces, SbsmBoundary, Bounds, Bound, Polygon,
#     Coordinates, CoordList -- in IFC2X3, IFC4 and IFC4X3, and
#     IfcRepresentationItem declares no attributes ahead of them.


def _as_points(rows: Sequence[Sequence[float]]) -> np.ndarray:
    """Return ``(x, y[, z])`` rows as an ``(N, 3)`` float array; 2D points get z=0.

    Raises:
        ValueError: The rows are ragged or neither 2D nor 3D. The caller's
            ``except`` turns that into "no vertices", as an unreadable item
            always was.
    """
    if not len(rows):
        return _NO_POINTS
    points = np.asarray(rows, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] not in (2, 3):
        raise ValueError(f"unusable point rows of shape {points.shape}")
    if points.shape[1] == 2:
        points = np.column_stack([points, np.zeros(len(points))])
    return points


def _brep_faces(item: Any) -> Any:
    """Return the raw ``IfcFace`` sequence behind a boundary-representation item.

    Args:
        item: A representation item.

    Returns:
        The faces the item is built from as raw ``wrapped_data`` instances, or
        an empty tuple when the item is not a boundary representation.
    """
    raw = item.wrapped_data
    if item.is_a("IfcManifoldSolidBrep"):
        # Covers IfcFacetedBrep and IfcAdvancedBrep: the outer shell's faces.
        outer = raw.get_argument(0)
        return (outer.get_argument(0) or ()) if outer is not None else ()
    if item.is_a("IfcFaceBasedSurfaceModel"):
        faces: list[Any] = []
        for face_set in raw.get_argument(0) or ():
            faces.extend(face_set.get_argument(0) or ())
        return faces
    if item.is_a("IfcShellBasedSurfaceModel"):
        faces = []
        for shell in raw.get_argument(0) or ():
            faces.extend(shell.get_argument(0) or ())
        return faces
    if item.is_a("IfcConnectedFaceSet"):
        return raw.get_argument(0) or ()
    return ()


def _face_vertices(faces: Any) -> np.ndarray:
    """Collect the polyloop points of a sequence of raw ``IfcFace`` instances.

    Args:
        faces: Raw faces from :func:`_brep_faces`.

    Returns:
        Every explicit vertex on every bound of every face. A bound that is not
        a polyloop (an edge loop, say) contributes nothing rather than
        raising: for a clearance envelope a missing curve is a slightly small
        box, not a failure.
    """
    rows: list[tuple[float, float, float]] = []
    for face in faces:
        for bound in face.get_argument(0) or ():
            loop = bound.get_argument(0)
            if loop is None or not loop.is_a("IfcPolyLoop"):
                continue
            for point in loop.get_argument(0) or ():
                coords = point.get_argument(0)
                if not coords:
                    continue
                rows.append((coords[0], coords[1], coords[2] if len(coords) > 2 else 0.0))
    return _as_points(rows)


def _item_vertices(
    item: Any, depth: int = 0, cache: MappedSourceCache | None = None
) -> np.ndarray:
    """Collect the local vertices of one representation item.

    Handles the shapes real exports actually use: tessellated face sets,
    boundary representations (the faceted breps and face-based surface models
    that dominate Revit and ArchiCAD output), explicit curves, swept solids
    reduced to their extrusion axis, and -- the reason this function is
    recursive -- ``IfcMappedItem``.

    A mapped item is a reference to a shared representation plus a placement.
    Reading only the top level of a representation therefore sees nothing at
    all on a model that maps its geometry, which is most of them: Duplex_MEP
    holds 942 mapped items and 42 directly-placed solids. The vertices come
    back from the mapping source and are transformed into the referencing
    element's own space before being returned, so nesting composes.

    Args:
        item: The representation item to read.
        depth: Current ``IfcMappedItem`` nesting level, used only to bound
            recursion.
        cache: Vertices already read for a mapped source, shared across the
            elements of one model. A source is read once however many elements
            instantiate it -- one door type mapped onto a few hundred doors
            was being walked a few hundred times -- and the mapping transform
            is applied per instance to the cached result. The depth is part of
            the key because it decides whether the recursion cap cuts the
            source short. ``None`` reads every source afresh.

    Returns:
        Vertices in the item's local coordinate system, one per row. An item
        whose shape is not understood yields none, which the caller reports as
        missing geometry rather than as a clearance verdict.
    """
    try:
        kind = item.is_a()

        if kind in ("IfcTriangulatedFaceSet", "IfcPolygonalFaceSet"):
            coordinates = item.wrapped_data.get_argument(0)
            coord_list = coordinates.get_argument(0) or ()
            points = np.asarray(coord_list, dtype=np.float64) if len(coord_list) else _NO_POINTS
            if points.size and (points.ndim != 2 or points.shape[1] != 3):
                raise ValueError("a face set's points must be 3D")
            return points

        if kind == "IfcPolyline":
            rows = []
            for point in item.Points or []:
                c = point.Coordinates
                rows.append((float(c[0]), float(c[1]), float(c[2]) if len(c) > 2 else 0.0))
            return _as_points(rows)

        if kind == "IfcExtrudedAreaSolid":
            # Reduced to the extrusion axis: the profile is not read, so the
            # box this contributes is a line along the sweep. Adequate for a
            # first-pass envelope and unchanged from the original behaviour.
            origin = (0.0, 0.0, 0.0)
            if item.Position is not None:
                c = item.Position.Location.Coordinates
                origin = (float(c[0]), float(c[1]), float(c[2]))
            ratios = item.ExtrudedDirection.DirectionRatios
            depth_m = float(item.Depth)
            return np.array(
                [
                    origin,
                    (
                        origin[0] + float(ratios[0]) * depth_m,
                        origin[1] + float(ratios[1]) * depth_m,
                        origin[2] + float(ratios[2]) * depth_m,
                    ),
                ],
                dtype=np.float64,
            )

        if kind == "IfcMappedItem":
            if depth >= _MAX_MAPPED_DEPTH:
                return _NO_POINTS
            source = getattr(item, "MappingSource", None)
            mapped = getattr(source, "MappedRepresentation", None)
            if mapped is None:
                return _NO_POINTS

            key = (mapped.id(), depth)
            local = cache.get(key) if cache is not None else None
            if local is None:
                parts = [
                    _item_vertices(sub_item, depth + 1, cache)
                    for sub_item in getattr(mapped, "Items", []) or []
                ]
                parts = [part for part in parts if len(part)]
                local = np.concatenate(parts) if parts else _NO_POINTS
                if cache is not None:
                    cache[key] = local
            if not len(local):
                return _NO_POINTS
            matrix = ifcopenshell.util.placement.get_mappeditem_transformation(item)
            if matrix is None:
                # A 2D transformation operator, which the helper does not
                # parse. The untransformed vertices still bound the shape's
                # size, so they are better than discarding the element.
                return local
            return _apply_many(matrix, local)

        if kind in ("IfcBooleanResult", "IfcBooleanClippingResult"):
            # The result of a difference or clip is contained in its first
            # operand, so the operand's extent is a conservative envelope --
            # never smaller than the true shape, which is the safe direction
            # for a clearance check.
            first = getattr(item, "FirstOperand", None)
            return _item_vertices(first, depth, cache) if first is not None else _NO_POINTS

        if kind == "IfcGeometricSet":
            parts = []
            rows = []
            for element in getattr(item, "Elements", []) or []:
                if element.is_a("IfcCartesianPoint"):
                    c = element.Coordinates
                    rows.append((float(c[0]), float(c[1]), float(c[2]) if len(c) > 2 else 0.0))
                else:
                    parts.append(_item_vertices(element, depth, cache))
            if rows:
                parts.append(_as_points(rows))
            parts = [part for part in parts if len(part)]
            return np.concatenate(parts) if parts else _NO_POINTS

        return _face_vertices(_brep_faces(item))
    except Exception:
        return _NO_POINTS


def _local_vertices(entity: IfcElement, cache: MappedSourceCache | None = None) -> np.ndarray:
    """Collect raw vertices from an entity's shape representation.

    Walks every item of every representation through :func:`_item_vertices`,
    which resolves mapped items and boundary representations. Anything it does
    not understand yields no vertices.

    Args:
        entity: The IFC entity to read.
        cache: Mapped-source cache, as for :func:`_item_vertices`.

    Returns:
        The vertices in the entity's local space, one per row.
    """
    representation = getattr(entity, "Representation", None)
    if representation is None:
        return _NO_POINTS

    parts = []
    for shape in getattr(representation, "Representations", []) or []:
        for item in getattr(shape, "Items", []) or []:
            part = _item_vertices(item, 0, cache)
            if len(part):
                parts.append(part)
    if not parts:
        return _NO_POINTS
    return np.concatenate(parts) if len(parts) > 1 else parts[0]


def element_bbox_mm(
    entity: IfcElement, scale_to_mm: float, cache: MappedSourceCache | None = None
) -> Optional[BoundingBox]:
    """Compute an element's world-space axis-aligned bounding box, in mm.

    Args:
        entity: The IFC entity to measure.
        scale_to_mm: Factor converting the model's length unit to mm, from
            unit_scale_to_mm(model).
        cache: Mapped-source cache to share with the other elements of the same
            model, as for :func:`_item_vertices`. Pass one dict per model when
            measuring a whole model; leave ``None`` for a one-off measurement.

    Returns:
        The bounding box, or None if the entity has no placement or no
        usable shape representation.
    """
    matrix = _placement_matrix(entity)
    if matrix is None:
        return None

    local = _local_vertices(entity, cache)
    if not len(local):
        return None

    world = _apply_many(matrix, local) * scale_to_mm
    low = world.min(axis=0)
    high = world.max(axis=0)

    return BoundingBox(
        min=Point3D(x=float(low[0]), y=float(low[1]), z=float(low[2])),
        max=Point3D(x=float(high[0]), y=float(high[1]), z=float(high[2])),
    )


def _profile_diameter(profile: Any) -> Optional[float]:
    """Return the governing cross-section of a swept profile, model units.

    Circular profiles give a true diameter. A rectangular profile has no
    diameter, so its smaller side is returned as the dimension a size threshold
    should compare against. A profile whose shape is arbitrary yields None
    rather than a guess.
    """
    try:
        kind = profile.is_a()
        if kind in ("IfcCircleProfileDef", "IfcCircleHollowProfileDef"):
            radius = getattr(profile, "Radius", None)
            return float(radius) * 2.0 if radius else None
        if kind in ("IfcRectangleProfileDef", "IfcRectangleHollowProfileDef"):
            x_dim = getattr(profile, "XDim", None)
            y_dim = getattr(profile, "YDim", None)
            if x_dim and y_dim:
                return float(min(x_dim, y_dim))
            return None
        if kind == "IfcDerivedProfileDef":
            return _profile_diameter(getattr(profile, "ParentProfile", None))
    except Exception:  # pragma: no cover - malformed profile
        return None
    return None


def _item_diameter(item: Any, depth: int = 0) -> Optional[float]:
    """Return the largest cross-section declared by one representation item.

    Mirrors :func:`_item_vertices` in the shapes it understands, and recurses
    through ``IfcMappedItem`` for the same reason.
    """
    if depth >= _MAX_MAPPED_DEPTH:
        return None
    try:
        kind = item.is_a()

        if kind == "IfcExtrudedAreaSolid":
            return _profile_diameter(getattr(item, "SweptArea", None))

        if kind == "IfcSweptDiskSolid":
            radius = getattr(item, "Radius", None)
            return float(radius) * 2.0 if radius else None

        if kind == "IfcMappedItem":
            source = getattr(item, "MappingSource", None)
            representation = getattr(source, "MappedRepresentation", None)
            found = [
                _item_diameter(sub, depth + 1)
                for sub in (getattr(representation, "Items", []) or [])
            ]
            measured = [d for d in found if d]
            return max(measured) if measured else None

        if kind == "IfcBooleanResult" or kind == "IfcBooleanClippingResult":
            # The first operand carries the body being clipped; the clipping
            # volume is not the pipe.
            return _item_diameter(getattr(item, "FirstOperand", None), depth + 1)
    except Exception:  # pragma: no cover - malformed item
        return None
    return None


def element_diameter_mm(entity: IfcElement, scale_to_mm: float) -> Optional[float]:
    """Return an element's declared cross-section in mm, or None.

    Reads the dimension off the swept profile rather than inferring it from the
    bounding box. This matters because :func:`_item_vertices` reduces a swept
    solid to its extrusion axis, so a pipe modelled as an
    ``IfcExtrudedAreaSolid`` -- which is how Revit and ArchiCAD normally export
    one -- has a bounding box with no thickness at all. Its
    ``IfcCircleProfileDef`` still carries an exact radius, and that is the
    number a diameter threshold should be tested against.

    Args:
        entity: The IFC entity to measure.
        scale_to_mm: Factor converting the model's length unit to mm, from
            :func:`unit_scale_to_mm`.

    Returns:
        The largest cross-section declared by any of the element's
        representation items, in mm, or None where no item declares one.
    """
    representation = getattr(entity, "Representation", None)
    if representation is None:
        return None

    measured: list[float] = []
    for shape in getattr(representation, "Representations", []) or []:
        for item in getattr(shape, "Items", []) or []:
            diameter = _item_diameter(item)
            if diameter:
                measured.append(diameter)

    return max(measured) * scale_to_mm if measured else None


# ---------------------------------------------------------------------------
# Core function 1 — generate_halo_volume
# ---------------------------------------------------------------------------


def generate_halo_volume_from_geometry(
    geometry: ElementGeometry,
    brace_type: BraceType,
    rule: ClearanceRule,
    *,
    seismic_zone: bool = False,
    building_type: str = "standard",
) -> HaloVolume:
    """Core halo-generation algorithm, independent of IFC I/O.

    Phase 1 envelope shape is a uniform buffer: the element's own bounding
    box expanded on every face by the rule's effective clearance. Angle-
    aware (wedge) envelopes for diagonal cable/rod bracing are deferred to
    a later phase.

    Args:
        geometry: The braced element's id, IFC class, and bounding box.
        brace_type: The hardware category being installed on this element.
        rule: The jurisdiction-specific clearance rule to apply. Callers
            typically select this via ClearanceConfig.rules_for(brace_type)
            or by variant key.
        seismic_zone: Whether the site is in a declared seismic zone.
        building_type: Building occupancy category, e.g. "hospital".

    Returns:
        The generated HaloVolume.
    """
    clearance_mm = rule.effective_clearance_mm(seismic_zone=seismic_zone, building_type=building_type)
    halo_bbox = geometry.bbox_mm.expanded(clearance_mm)

    return HaloVolume(
        id=str(uuid.uuid4()),
        source_element_id=geometry.element_id,
        source_ifc_class=geometry.ifc_class,
        brace_type=brace_type,
        element_bbox_mm=geometry.bbox_mm,
        halo_bbox_mm=halo_bbox,
        clearance_mm=clearance_mm,
        rule_variant=rule.variant,
        metadata={
            "seismic_zone": seismic_zone,
            "building_type": building_type,
        },
    )


def generate_halo_volume(
    element: IfcElement,
    brace_type: BraceType,
    rule: ClearanceRule,
    *,
    model: Optional[IfcModel] = None,
    scale_to_mm: Optional[float] = None,
    seismic_zone: bool = False,
    building_type: str = "standard",
) -> Optional[HaloVolume]:
    """Generate a seismic bracing clearance envelope for one braced element.

    Thin IFC-reading wrapper around generate_halo_volume_from_geometry: see
    that function for the actual generation algorithm.

    Args:
        element: The braced IFC element (pipe segment, duct segment, ...).
        brace_type: The hardware category being installed on this element.
        rule: The jurisdiction-specific clearance rule to apply. Callers
            typically select this via ClearanceConfig.rules_for(brace_type)
            or by variant key.
        model: The open IFC model, needed only to derive scale_to_mm when
            it is not passed explicitly.
        scale_to_mm: Precomputed model-unit-to-mm factor. Pass this when
            generating many halo volumes from the same model to avoid
            recomputing it per call.
        seismic_zone: Whether the site is in a declared seismic zone.
        building_type: Building occupancy category, e.g. "hospital".

    Returns:
        The generated HaloVolume, or None if the element's geometry could
        not be resolved (no placement or no usable shape representation).
    """
    if scale_to_mm is None:
        if model is None:
            raise ValueError("generate_halo_volume requires either model or scale_to_mm")
        scale_to_mm = unit_scale_to_mm(model)

    bbox = element_bbox_mm(element, scale_to_mm)
    if bbox is None:
        return None

    global_id = getattr(element, "GlobalId", None) or "unknown"
    ifc_class = element.is_a() if hasattr(element, "is_a") else "Unknown"
    geometry = ElementGeometry(element_id=str(global_id), ifc_class=str(ifc_class), bbox_mm=bbox)

    return generate_halo_volume_from_geometry(
        geometry, brace_type, rule, seismic_zone=seismic_zone, building_type=building_type
    )


# ---------------------------------------------------------------------------
# Core function 2 — detect_halo_clash
# ---------------------------------------------------------------------------
# Severity buckets below are a generic spatial-overlap heuristic (overlap
# volume as a fraction of the halo volume), not sourced from any specific
# standard. Jurisdiction-specific severity mapping is a Phase 2+ concern;
# revisit these thresholds once real case-study data is available.

_CLASH_SEVERITY_THRESHOLDS: tuple[tuple[float, ClashSeverity], ...] = (
    (0.25, "critical"),
    (0.05, "major"),
)


def _classify_clash_severity(overlap_ratio: float) -> ClashSeverity:
    for threshold, severity in _CLASH_SEVERITY_THRESHOLDS:
        if overlap_ratio >= threshold:
            return severity
    return "minor"


def detect_halo_clash_against_geometry(
    halo: HaloVolume,
    candidates: Iterable[ElementGeometry],
) -> list[ClashReport]:
    """Core clash-detection algorithm, independent of IFC I/O.

    Args:
        halo: The clearance envelope to test against.
        candidates: Resolved geometry for candidate elements to test —
            typically every structural/MEP element in the halo's vicinity
            (e.g. from a spatial index or a bounding-box pre-filter
            upstream of this call; Phase 1 does not perform that
            pre-filtering itself).

    Returns:
        One ClashReport per candidate whose bounding box overlaps
        halo.halo_bbox_mm. A candidate matching halo.source_element_id
        (the braced element itself) is skipped. Empty list if nothing
        clashes.
    """
    halo_volume_mm3 = halo.halo_bbox_mm.volume_mm3
    reports: list[ClashReport] = []

    for candidate in candidates:
        if not candidate.element_id or candidate.element_id == halo.source_element_id:
            continue

        overlap = halo.halo_bbox_mm.intersection(candidate.bbox_mm)
        if overlap is None:
            continue

        overlap_volume = overlap.volume_mm3
        if overlap_volume <= 0:
            continue

        overlap_ratio = overlap_volume / halo_volume_mm3 if halo_volume_mm3 > 0 else 1.0
        severity = _classify_clash_severity(overlap_ratio)

        reports.append(
            ClashReport(
                id=str(uuid.uuid4()),
                halo_id=halo.id,
                halo_source_element_id=halo.source_element_id,
                clashing_element_id=candidate.element_id,
                clashing_element_class=candidate.ifc_class,
                overlap_bbox_mm=overlap,
                overlap_volume_mm3=overlap_volume,
                severity=severity,
                description=(
                    f"{candidate.ifc_class} ({candidate.element_id}) intrudes into the seismic "
                    f"bracing clearance halo of {halo.source_ifc_class} ({halo.source_element_id}) "
                    f"by {overlap_volume:,.0f} mm^3 ({overlap_ratio:.1%} of the halo volume)."
                ),
            )
        )

    return reports


def detect_halo_clash(
    halo: HaloVolume,
    candidates: Iterable[IfcElement],
    *,
    model: Optional[IfcModel] = None,
    scale_to_mm: Optional[float] = None,
) -> list[ClashReport]:
    """Detect intrusions of neighbouring elements into a halo volume.

    Thin IFC-reading wrapper around detect_halo_clash_against_geometry: see
    that function for the actual detection algorithm.

    Args:
        halo: The clearance envelope to test against.
        candidates: Candidate IFC elements to test.
        model: The open IFC model, needed only to derive scale_to_mm when
            it is not passed explicitly.
        scale_to_mm: Precomputed model-unit-to-mm factor.

    Returns:
        One ClashReport per candidate whose bounding box overlaps
        halo.halo_bbox_mm. Candidates matching halo.source_element_id
        (the braced element itself) or with unresolvable geometry are
        skipped. Empty list if nothing clashes.
    """
    if scale_to_mm is None:
        if model is None:
            raise ValueError("detect_halo_clash requires either model or scale_to_mm")
        scale_to_mm = unit_scale_to_mm(model)

    geometries: list[ElementGeometry] = []
    for candidate in candidates:
        candidate_id = str(getattr(candidate, "GlobalId", None) or "")
        if not candidate_id:
            continue
        candidate_bbox = element_bbox_mm(candidate, scale_to_mm)
        if candidate_bbox is None:
            continue
        ifc_class = candidate.is_a() if hasattr(candidate, "is_a") else "Unknown"
        geometries.append(ElementGeometry(element_id=candidate_id, ifc_class=str(ifc_class), bbox_mm=candidate_bbox))

    return detect_halo_clash_against_geometry(halo, geometries)


# ---------------------------------------------------------------------------
# Core function 3 — export_halo_to_ifc_property_set
# ---------------------------------------------------------------------------

HALO_PSET_NAME = "BlueHalo_ClearanceVolume"

#: The property set written onto an exported clearance-zone element.
#:
#: Defined here rather than in reporter/blue_halo_bcf_exporter.py, which used to
#: own it, because two exporters now need the same properties: the BCF path and
#: the standalone IFC path (reporter/halo_ifc_exporter.py). Module 2 is upstream
#: of Module 5, so the shared definition belongs on this side of the boundary
#: and reporter re-exports it under its original name.
PSET_HALO_RESERVATION = "Pset_HaloReservation"


def halo_reservation_properties(
    *,
    source_element_id: str,
    source_ifc_class: str,
    brace_type: str,
    rule_variant: str,
    clearance_mm: float,
    halo_volume_mm3: float,
    element_bbox_min_mm: Sequence[float],
    element_bbox_max_mm: Sequence[float],
    halo_bbox_min_mm: Sequence[float],
    halo_bbox_max_mm: Sequence[float],
    generated_at: str,
) -> dict:
    """Build the Pset_HaloReservation property values from primitives.

    Takes plain values rather than a :class:`HaloVolume` so that the same
    property names and types are produced from either end: from a live halo
    (the BCF path, via ``blue_halo_bcf_exporter.generate_pset_halo_reservation``)
    or from a finding's stored metadata, long after the HaloVolume itself has
    gone (the IFC path). One definition, so the two exports cannot drift.

    Returns:
        ``{property_name: value}`` -- the inner mapping only. Callers wrap it
        under :data:`PSET_HALO_RESERVATION` or hand it to ifcopenshell.
    """
    return {
        "SchemaVersion": SCHEMA_VERSION,
        "SourceElementGlobalId": source_element_id,
        "SourceIfcClass": source_ifc_class,
        "BraceType": brace_type,
        "RuleVariant": rule_variant or "",
        "ClearanceMm": float(clearance_mm),
        "HaloVolumeMm3": float(halo_volume_mm3),
        "ElementBBoxMinMm": [float(v) for v in element_bbox_min_mm],
        "ElementBBoxMaxMm": [float(v) for v in element_bbox_max_mm],
        "HaloBBoxMinMm": [float(v) for v in halo_bbox_min_mm],
        "HaloBBoxMaxMm": [float(v) for v in halo_bbox_max_mm],
        "GeneratedAt": generated_at,
    }


def export_halo_to_ifc_property_set(halo: HaloVolume) -> dict:
    """Build a Pset-shaped dict describing a halo volume for IFC round-trip.

    Phase 1 returns the property data only, in the {pset_name: {prop:
    value}} shape used elsewhere in this codebase (see
    ifc_reader.__init__.extract_rich_properties). Writing an actual
    IfcPropertySet back onto the model via ifcopenshell is deferred to the
    phase that wires this into the IFC egress path
    (ifc_reader/ifc_egress.py).

    Args:
        halo: The halo volume to export.

    Returns:
        {HALO_PSET_NAME: {property_name: value, ...}}
    """
    return {
        HALO_PSET_NAME: {
            "SchemaVersion": SCHEMA_VERSION,
            "BraceType": halo.brace_type.value,
            "RuleVariant": halo.rule_variant or "",
            "ClearanceMm": halo.clearance_mm,
            "ElementBBoxMinMm": [halo.element_bbox_mm.min.x, halo.element_bbox_mm.min.y, halo.element_bbox_mm.min.z],
            "ElementBBoxMaxMm": [halo.element_bbox_mm.max.x, halo.element_bbox_mm.max.y, halo.element_bbox_mm.max.z],
            "HaloBBoxMinMm": [halo.halo_bbox_mm.min.x, halo.halo_bbox_mm.min.y, halo.halo_bbox_mm.min.z],
            "HaloBBoxMaxMm": [halo.halo_bbox_mm.max.x, halo.halo_bbox_mm.max.y, halo.halo_bbox_mm.max.z],
            "GeneratedAt": halo.generated_at,
        }
    }


# ---------------------------------------------------------------------------
# Core function 4 — export_halo_to_bcf
# ---------------------------------------------------------------------------
# Returns a plain dict rather than importing
# reporter.bcf_generator.BCFIssue directly: Module 2 (this file) is
# upstream of Module 5 in the pipeline, and Module 5 owns BCF-ZIP packaging.
# The dict's keys deliberately match BCFIssue's fields 1:1 so a later phase
# can construct one via BCFIssue(**export_halo_to_bcf(...)).

_SEVERITY_TO_BCF_PRIORITY: dict[ClashSeverity, str] = {
    "critical": "Critical",
    "major": "Major",
    "minor": "Minor",
}

# Days-until-due by severity. Mirrors the banding reporter's
# bcf_generator.issues_from_results already applies to corrosion issues
# (critical=2, medium=21) so Blue Halo issues sort into a coordination
# backlog the same way. BCF's DueDate element requires a full date, so an
# empty due_date is not an option — see the DueDate line in
# reporter.bcf_generator._markup_xml.
_SEVERITY_TO_DUE_DAYS: dict[ClashSeverity, int] = {
    "critical": 2,
    "major": 7,
    "minor": 21,
}


def _due_date_for_severity(severity: ClashSeverity) -> str:
    """Return an ISO 8601 date (YYYY-MM-DD) due by, from today, for severity."""
    days = _SEVERITY_TO_DUE_DAYS.get(severity, 21)
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def export_halo_to_bcf(clash: ClashReport, halo: HaloVolume) -> dict:
    """Build a BCF-issue-shaped dict for one detected halo clash.

    Args:
        clash: The clash to report.
        halo: The halo volume the clash was detected against (for
            component/brace context in the issue text).

    Returns:
        A dict whose keys match reporter.bcf_generator.BCFIssue's
        fields, ready to hand to Module 5 for BCF-ZIP packaging.
    """
    return {
        "guid": str(uuid.uuid4()).upper(),
        "title": (
            f"Seismic bracing clearance clash — {halo.brace_type.value} on "
            f"{halo.source_ifc_class}"
        ),
        "description": clash.description,
        "priority": _SEVERITY_TO_BCF_PRIORITY.get(clash.severity, "Normal"),
        "status": "Active",
        "assigned_to": "Unassigned",
        "due_date": _due_date_for_severity(clash.severity),
        "labels": ["blue_halo", "seismic_bracing", halo.brace_type.value],
        "component_guid": clash.clashing_element_id,
        "component_name": clash.clashing_element_class,
        "service_type": halo.source_ifc_class,
        "floor": "",
        "risk_band": clash.severity.upper(),
        "mechanism": "blue_halo_seismic_clearance",
        "risk_score": 0.0,
        "mitigation": (
            "Relocate or resize the clashing element, or select a brace "
            "variant with a smaller footprint, so the clearance envelope "
            "no longer intersects it."
        ),
    }
