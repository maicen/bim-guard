"""
ifc_reader/ifc_stair.py
--------------------------------
Per-riser, per-tread, per-landing and per-handrail geometry analysis for
IfcStairFlight / IfcSlab(LANDING) / IfcRailing.

The generic Tier 1 extractor (``ifc_geometry.IFCGeometryExtractor``) only ever
measures a WHOLE element's bounding box -- one height, one width, one slope.
That is enough for "how tall is this door", but a stair rule almost never
asks about the whole flight: it asks about the WORST riser, the SHALLOWEST
tread, the NARROWEST point along the run. None of that is recoverable from a
bounding box, because a flight's bounding box is just its overall envelope --
it has already thrown away exactly the step-by-step detail these checks need.

This module fills that gap in two layers, the same split ``ifc_seismic.py``
uses and for the same reason -- the arithmetic that could produce a wrong
verdict should be provable without an IFC file:

  1. Pure numpy algorithms (``cluster_step_bands``, ``derive_flight_steps``,
     ``min_clear_width_by_band``, ...) that operate on plain point arrays and
     have no ifcopenshell dependency. Unit-testable with a hand-built point
     cloud representing an idealised staircase.
  2. Thin ifcopenshell-facing wrappers (``analyze_stair_flight``,
     ``analyze_landing``, ``analyze_railing``) that pull a tessellated mesh
     via the geometry extractor's existing cache and feed it to layer 1.

``IFCStairEngine`` walks the model once, runs both layers over every
flight/landing/railing, and caches the results by GlobalId so
``ifc_reader.IFCReader`` can expose them as ordinary derived properties
(``MinRiserHeight``, ``MaxTreadDepthDifference``, ``HandrailMinHeight``, ...)
through the same Pass-0 resolver shortcut ``ifc_seismic``/``ifc_supports``
already use -- see ``_STAIR_DERIVED_PROPERTIES`` in ``ifc_reader/__init__.py``.

A THIRD, engine-level pass (``IFCStairEngine._link_elements``, not part of
either layer above, since it works ACROSS elements rather than on one
element's own mesh) then cross-references flights, landings and railings
that never explicitly decompose under a shared ``IfcStair`` -- the common
case, not the exception. It matches a landing to the flight(s) it connects
(by elevation + world-bbox proximity) and a railing to the flight/landing it
runs alongside (by nearest world-bbox), producing ``ParentStairGlobalId``,
``LandingBelow``/``LandingAbove``, ``ConnectsFlightBelow``/
``ConnectsFlightAbove``, ``LandingLevelMismatch``, ``HostElementGlobalId``,
and ``HandrailCountOnFlight``/``GuardCountOnFlight``. This is the one place
in the module that works in WORLD coordinates rather than an element's own
PCA-derived local frame, since two different elements' local frames are not
directly comparable to each other.

Known v1 limitations (deliberately out of scope, not silently wrong -- each
one below is actually detected and named in the affected element's own
``warnings`` list at runtime, not just documented here):
  * Winder/curved flights: total turning angle and rise/run still resolve,
    but per-winder tread depth at inner/walking-line/outer edges is not yet
    computed. Detected via each tread band's lateral centroid drift (see
    ``analyze_stair_flight``'s curvature check) -- a straight flight's tread
    centroids stay put; a winder's rotate with it.
  * Guards (IfcRailing with PredefinedType GUARDRAIL/BALUSTRADE/FENCE, or
    unset): MaxOpening (largest horizontal infill gap, sampled at several
    heights) and BottomClearGap (typical gap under the bottom rail, via the
    median bottom elevation across run-bands so a few floor-touching posts
    don't mask a real elevated-rail gap) ARE computed -- see
    ``guard_opening_profile``. What is NOT: a true multi-directional
    sphere-passing simulation (this is single-axis: the largest horizontal
    gap at a sampled height, not the largest circle that fits through the
    actual 2D opening shape), baluster CENTRE-TO-CENTRE spacing as its own
    figure, and the triangular stair-nosing opening. Every guard's analysis
    still carries a warning naming exactly these gaps, so it rides along
    with whatever DOES resolve for that element.
  * Handrail/guard path length is a straight-line run-axis approximation.
    For a curved rail this undercounts the true swept length; a warning is
    attached whenever the mesh's lateral spread suggests real curvature.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger("bimguard.stair")

try:
    import numpy as np

    _NP_AVAILABLE = True
except ImportError:
    _NP_AVAILABLE = False

try:
    import ifcopenshell.util.element

    _IFC_AVAILABLE = True
except ImportError:
    _IFC_AVAILABLE = False

try:
    import shapely.geometry

    _SHAPELY_AVAILABLE = True
except ImportError:
    _SHAPELY_AVAILABLE = False


# ── Tunables ────────────────────────────────────────────────────────────────

#: Two tread-top point clusters closer together in Z than this are treated as
#: the SAME tread. Safely above tessellation noise (fractions of a mm to a
#: few mm) and safely below the smallest realistic riser height (~100 mm).
DEFAULT_TREAD_Z_GAP_MM = 40.0

#: A face counts as a walking surface ("tread top") when its normal's Z
#: component exceeds this. 1.0 is straight up; 0.7 ~ 45 degrees, generous
#: enough to tolerate a slightly sloped/non-slip tread surface without also
#: picking up riser faces (whose normals are near-horizontal, Z ~ 0).
DEFAULT_UP_NORMAL_THRESHOLD = 0.7

#: Width/path sampling bin size along the run axis.
DEFAULT_RUN_BAND_MM = 100.0

#: A gap this wide (mm) between consecutive occupied run-bands, inside the
#: element's own run extent, is read as a physical break (open riser, or a
#: discontinuous handrail) rather than ordinary sampling sparsity.
DEFAULT_GAP_MM = 150.0

#: A flight whose detected tread bands drift laterally by more than this (mm)
#: from the first tread to the last is read as having real plan curvature
#: (winder or curved stair), not just ordinary width. A straight flight's
#: tread centroids sit at essentially the same lateral position throughout
#: (a few mm of noise at most); a winder's rotate with the walking line, and
#: even a modest winder run typically drifts hundreds of mm. Deliberately an
#: ABSOLUTE threshold, not a ratio against the flight's width or run: a wide
#: straight stair has plenty of lateral spread from its width alone, which a
#: ratio-based check would misread as curvature.
DEFAULT_CURVATURE_DRIFT_MM = 75.0

#: A landing's own elevation must be within this many mm of a flight's start
#: or end elevation to be considered "connected" to it -- tight enough not to
#: confuse two different storeys, generous enough to tolerate a landing
#: surface modelled slightly proud of/recessed from the tread nosing line.
DEFAULT_LANDING_ELEVATION_TOLERANCE_MM = 75.0

#: Maximum plan (XY) distance, in mm, between two elements' world bounding
#: boxes for them to be considered "in the same vicinity" when matching a
#: landing or railing to the flight it connects to / runs alongside.
#: Generous enough for a wide landing or a wall-offset handrail; still tight
#: enough to rule out an unrelated stair elsewhere in a large building.
DEFAULT_HOST_PROXIMITY_MM = 3000.0


# ── Layer 1: pure numpy algorithms (no ifcopenshell) ──────────────────────────


def local_frame_from_xy(xy) -> tuple | None:
    """Return (origin, u, v): a PCA-derived local 2D frame for a footprint.

    ``u`` is the unit vector along the direction of greatest horizontal
    spread (the walking/run direction for a stair flight or handrail -- a
    flight is always much longer than it is wide, so its dominant XY spread
    IS the walking direction, regardless of how the exporter set up
    ObjectPlacement). ``v`` is the perpendicular (lateral) direction.

    Returns None when there are fewer than 3 distinct points -- not enough
    to define a plane's principal axes.
    """
    if not _NP_AVAILABLE:
        return None
    pts = np.asarray(xy, dtype=float)
    if pts.ndim != 2 or pts.shape[0] < 3 or pts.shape[1] != 2:
        return None
    origin = pts.mean(axis=0)
    centered = pts - origin
    cov = np.cov(centered, rowvar=False)
    if not np.all(np.isfinite(cov)):
        return None
    try:
        eigvals, eigvecs = np.linalg.eigh(cov)
    except np.linalg.LinAlgError:
        return None
    # eigh returns ascending eigenvalues; the last column is the dominant axis.
    u = eigvecs[:, -1]
    v = eigvecs[:, 0]
    if np.linalg.norm(u) < 1e-9:
        return None
    u = u / np.linalg.norm(u)
    v = v / np.linalg.norm(v)
    return origin, u, v


def project_local(points_xyz, origin, u, v):
    """Project (N,3) mm points onto local (run, lateral, z) via the frame above."""
    pts = np.asarray(points_xyz, dtype=float)
    xy = pts[:, :2] - origin
    run = xy @ u
    lateral = xy @ v
    z = pts[:, 2]
    return run, lateral, z


def cluster_step_bands(
    run, z, lateral=None, z_gap_mm: float = DEFAULT_TREAD_Z_GAP_MM
) -> list[dict]:
    """Group (run, z) points into step bands -- one band per detected tread top.

    Points are sorted by Z and split wherever a gap exceeds *z_gap_mm*.
    Within a band (one physical tread's worth of top-face points, which all
    sit at very nearly the same Z), reports the run extent (``run_min``,
    ``run_max`` -- the tread's own horizontal footprint) and the mean Z.
    When *lateral* is supplied (same length as *run*/*z*), each band also
    reports ``lateral_mean`` -- the tread's centroid across the flight's
    width, which a straight flight holds constant and a winder does not
    (see ``analyze_stair_flight``'s curvature check).

    Bands are returned sorted by ``run_min`` ascending, i.e. in walking
    order from the bottom of the flight to the top -- NOT by Z, because nosing
    overhang or a false split can occasionally put two bands' Z means out of
    run order; walking order is what "riser 1, riser 2, ..." means.

    Returns an empty list when there are no points at all.
    """
    run = np.asarray(run, dtype=float)
    z = np.asarray(z, dtype=float)
    lateral_arr = np.asarray(lateral, dtype=float) if lateral is not None else None
    if run.size == 0:
        return []

    order = np.argsort(z)
    z_sorted = z[order]
    run_sorted = run[order]
    lateral_sorted = lateral_arr[order] if lateral_arr is not None else None

    bands: list[dict] = []
    start = 0
    for i in range(1, len(z_sorted) + 1):
        if i == len(z_sorted) or (z_sorted[i] - z_sorted[i - 1]) > z_gap_mm:
            seg_run = run_sorted[start:i]
            seg_z = z_sorted[start:i]
            band = {
                "z_mean": float(seg_z.mean()),
                "run_min": float(seg_run.min()),
                "run_max": float(seg_run.max()),
                "point_count": int(seg_run.size),
            }
            if lateral_sorted is not None:
                band["lateral_mean"] = float(lateral_sorted[start:i].mean())
            bands.append(band)
            start = i

    bands.sort(key=lambda b: b["run_min"])
    return bands


def derive_flight_steps(bands: list[dict]) -> dict:
    """Turn sorted step bands into riser/going series plus uniformity stats.

    ``goings`` (tread depth, nosing-to-nosing) is the run distance between
    consecutive bands' leading edges (``run_min``), which is the standard
    "going" convention -- measured from one nosing to the next, not a
    tread's own physical board width (which may include material hidden
    under the nosing above it).

    ``risers`` is the Z delta between consecutive bands' means. Both series
    have length ``len(bands) - 1``: with only one detected tread there is no
    riser or going to report between treads, only within-flight boundary
    risers (against the floor/landing) which this function does not attempt
    -- see ``analyze_stair_flight`` for why those are kept separate and
    lower-confidence.
    """
    if len(bands) < 2:
        return {
            "tread_count": len(bands),
            # None (undetermined), not 0: fewer than 2 tread bands means we
            # genuinely don't know how many risers this flight has, matching
            # every other field below -- a determinate 0 would be read as
            # "no risers", a claim about the model this result never made.
            "riser_count": None,
            "goings_mm": [],
            "risers_mm": [],
            "min_going_mm": None,
            "max_going_mm": None,
            "going_difference_mm": None,
            "min_riser_mm": None,
            "max_riser_mm": None,
            "riser_difference_mm": None,
        }

    goings = [
        round(bands[i + 1]["run_min"] - bands[i]["run_min"], 1)
        for i in range(len(bands) - 1)
    ]
    risers = [
        round(bands[i + 1]["z_mean"] - bands[i]["z_mean"], 1)
        for i in range(len(bands) - 1)
    ]

    return {
        "tread_count": len(bands),
        # Mid-flight risers only (len(bands) - 1), same high-confidence scope
        # as risers_mm/goings_mm -- see the docstring above for why the two
        # boundary risers (floor-to-first-tread, last-tread-to-landing)
        # aren't counted here.
        "riser_count": len(bands) - 1,
        "goings_mm": goings,
        "risers_mm": risers,
        "min_going_mm": round(min(goings), 1),
        "max_going_mm": round(max(goings), 1),
        "going_difference_mm": round(max(goings) - min(goings), 1),
        "min_riser_mm": round(min(risers), 1),
        "max_riser_mm": round(max(risers), 1),
        "riser_difference_mm": round(max(risers) - min(risers), 1),
    }


def min_clear_width_by_band(
    run, lateral, band_mm: float = DEFAULT_RUN_BAND_MM
) -> float | None:
    """Minimum lateral extent (mm) sampled in bands along the run axis.

    Unlike a single whole-footprint min-rotated-rectangle (the generic Tier 1
    ``get_corridor_width_mm``), this samples the width AT EACH POINT along
    the flight, so a local pinch point (a mid-flight newel post, a wall that
    angles inward partway up) is caught instead of averaged away.

    Returns None when there are too few points to bin meaningfully.
    """
    run = np.asarray(run, dtype=float)
    lateral = np.asarray(lateral, dtype=float)
    if run.size < 2:
        return None

    run_min, run_max = float(run.min()), float(run.max())
    if run_max <= run_min:
        return None

    n_bands = max(1, int(math.ceil((run_max - run_min) / band_mm)))
    widths: list[float] = []
    for b in range(n_bands):
        lo = run_min + b * band_mm
        hi = lo + band_mm
        mask = (run >= lo) & (run <= hi)
        if mask.sum() < 2:
            continue
        widths.append(float(lateral[mask].max() - lateral[mask].min()))

    if not widths:
        return None
    return round(min(widths), 1)


def face_run_intervals(verts, faces, origin, u, v) -> list[tuple[float, float]]:
    """Per-face run-axis [min, max] coverage intervals, sorted ascending.

    Checking raw VERTEX positions for gaps (as an earlier version of this
    module did) is unreliable on realistically sparse meshes: a straight
    handrail segment tessellates into a handful of quads whose corner
    vertices sit only at the segment's two ends, so the segment's own
    length -- fully covered by its faces -- looks identical to a genuine
    missing section, which also has no vertices in between. A face's own
    3 corners already span its full run extent (unlike an isolated point),
    so using face-level [min, max] intervals and merging them is the
    reliable way to ask "is there material covering this stretch of run?"
    """
    if faces is None or verts is None or faces.size == 0:
        return []
    tri_verts = verts[faces.reshape(-1)]
    run_c, _lateral_c, _z_c = project_local(tri_verts, origin, u, v)
    run_c = run_c.reshape(-1, 3)
    intervals = sorted(zip(run_c.min(axis=1).tolist(), run_c.max(axis=1).tolist()))
    return intervals


def merge_run_intervals(
    intervals: list[tuple[float, float]], gap_mm: float = DEFAULT_GAP_MM
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Merge run-axis intervals, treating a separation smaller than *gap_mm*
    as still continuous (ordinary tessellation seams, not a real break).

    Returns (merged_segments, real_gaps) -- ``len(merged_segments)`` is the
    element's continuous-segment count, and each real_gaps entry is
    (end_of_previous_segment, start_of_next_segment) in mm.
    """
    if not intervals:
        return [], []
    merged: list[list[float]] = [list(intervals[0])]
    gaps: list[tuple[float, float]] = []
    for lo, hi in intervals[1:]:
        if lo <= merged[-1][1] + gap_mm:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            gaps.append((round(merged[-1][1], 1), round(lo, 1)))
            merged.append([lo, hi])
    return [(round(a, 1), round(b, 1)) for a, b in merged], gaps


def bbox_xy_distance_mm(bbox_a: dict | None, bbox_b: dict | None) -> float | None:
    """Minimum plan (XY) distance in mm between two world-space bounding
    boxes shaped like ``IFCGeometryExtractor.get_bounding_box()``'s output
    (``min_x``/``max_x``/``min_y``/``max_y``/...). 0.0 when the boxes
    overlap in plan. None when either box is unavailable -- the cross
    -referencing pass this feeds must treat that as "cannot match", not as
    "infinitely far" or "touching".

    Used to match a landing or railing to the flight it connects to / runs
    alongside, since each element's own local (run, lateral) frame is
    independently derived (PCA per element) and not comparable across
    elements -- world-space bounding boxes are the one thing every element
    shares a common coordinate system for.
    """
    if not bbox_a or not bbox_b:
        return None
    dx = max(bbox_a["min_x"] - bbox_b["max_x"], bbox_b["min_x"] - bbox_a["max_x"], 0.0)
    dy = max(bbox_a["min_y"] - bbox_b["max_y"], bbox_b["min_y"] - bbox_a["max_y"], 0.0)
    return round(math.hypot(dx, dy), 1)


# ── Layer 2: ifcopenshell-facing wrappers ─────────────────────────────────────


def _face_up_points(verts, faces, up_threshold: float = DEFAULT_UP_NORMAL_THRESHOLD):
    """Return the (K,3) subset of vertices belonging to upward-facing triangles.

    A "tread top" face has a mostly-vertical (Z-pointing) normal; a riser
    face's normal is near-horizontal. Degenerate (near-zero-area) triangles
    are skipped rather than dividing by zero.
    """
    if faces is None or verts is None or faces.size == 0:
        return None
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    normals = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-6
    if not np.any(valid):
        return None
    unit_normals = np.zeros_like(normals)
    unit_normals[valid] = normals[valid] / lengths[valid, None]
    # Upward-only (not abs): a downward-facing near-horizontal face is the
    # sloped underside (soffit) of a monolithic flight, not a walking
    # surface, and must not be allowed to contaminate tread-band clustering.
    up = (unit_normals[:, 2] >= up_threshold) & valid
    if not np.any(up):
        return None
    up_faces = faces[up]
    pts = np.vstack([verts[up_faces[:, 0]], verts[up_faces[:, 1]], verts[up_faces[:, 2]]])
    return pts


def _riser_face_bridges(
    verts, faces, origin, u, v, transition_run: float, z_low: float, z_high: float, tol_mm: float
) -> bool:
    """Whether a near-vertical mesh face bridges [z_low, z_high] at
    approximately transition_run -- i.e. a genuine closed-riser face, not
    merely two tread corners that happen to touch at the same run position.

    A face counts as "vertical" when its normal is close to horizontal
    (small Z component) -- the complement of the "up" test in
    ``_face_up_points``. Among those, one bridges the gap when ALL 3 of its
    own vertices project to a run coordinate within *tol_mm* of the
    transition, and its own Z extent covers from z_low to z_high.
    """
    if faces is None or verts is None or faces.size == 0:
        return False
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    normals = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-6
    if not np.any(valid):
        return False
    unit_z = np.zeros(len(normals))
    unit_z[valid] = normals[valid, 2] / lengths[valid]
    vertical = valid & (np.abs(unit_z) < (1.0 - DEFAULT_UP_NORMAL_THRESHOLD))
    if not np.any(vertical):
        return False

    for i in np.nonzero(vertical)[0]:
        tri = np.array([verts[faces[i, 0]], verts[faces[i, 1]], verts[faces[i, 2]]])
        run_c, _lateral_c, z_c = project_local(tri, origin, u, v)
        if np.all(np.abs(run_c - transition_run) <= tol_mm):
            if z_c.min() <= z_low + tol_mm and z_c.max() >= z_high - tol_mm:
                return True
    return False


def analyze_stair_flight(
    flight, geometry_extractor, z_gap_mm: float = DEFAULT_TREAD_Z_GAP_MM
) -> dict:
    """Per-riser / per-tread geometry analysis for one IfcStairFlight.

    Returns a dict (never raises); ``warnings`` names anything that could
    not be determined. Every numeric field is None, not 0 or a guess, when
    the geometry did not support it -- callers must treat None as
    Undetermined, matching this codebase's tri-state convention elsewhere
    (``ifc_seismic``, ``ifc_supports``).
    """
    result: dict[str, Any] = {
        "guid": getattr(flight, "GlobalId", None),
        "warnings": [],
    }
    if not (_NP_AVAILABLE and geometry_extractor):
        result["warnings"].append("numpy or geometry extractor unavailable")
        return result

    verts, faces = geometry_extractor._get_mesh_mm(flight)
    if verts is None or verts.shape[0] < 3:
        result["warnings"].append("no resolvable geometry for this flight")
        return result

    frame = local_frame_from_xy(verts[:, :2])
    if frame is None:
        result["warnings"].append("could not determine walking direction (degenerate footprint)")
        return result
    origin, u, v = frame

    bottom_z = geometry_extractor.get_bottom_z_mm(flight)
    top_z = geometry_extractor.get_top_z_mm(flight)
    if bottom_z is not None:
        result["start_elevation_mm"] = round(bottom_z, 1)
    if top_z is not None:
        result["end_elevation_mm"] = round(top_z, 1)
    if bottom_z is not None and top_z is not None:
        result["total_rise_mm"] = round(top_z - bottom_z, 1)

    all_run, all_lateral, all_z = project_local(verts, origin, u, v)
    result["total_run_mm"] = (
        round(float(all_run.max() - all_run.min()), 1) if all_run.size else None
    )
    if result.get("total_rise_mm") is not None and result.get("total_run_mm"):
        result["pitch_deg"] = round(
            math.degrees(math.atan2(result["total_rise_mm"], result["total_run_mm"])), 2
        )
        result["sloped_length_mm"] = round(
            math.hypot(result["total_rise_mm"], result["total_run_mm"]), 1
        )

    result["min_clear_width_mm"] = min_clear_width_by_band(all_run, all_lateral)

    top_pts = _face_up_points(verts, faces)
    if top_pts is None:
        result["warnings"].append(
            "could not isolate tread-top faces -- flight may lack proper "
            "step geometry (open risers, or a non-stepped ramp-like solid)"
        )
        result["open_riser"] = None
        return result

    top_run, top_lateral, top_z = project_local(top_pts, origin, u, v)
    bands = cluster_step_bands(top_run, top_z, lateral=top_lateral, z_gap_mm=z_gap_mm)
    steps = derive_flight_steps(bands)
    result.update(steps)
    result["tread_top_elevations_mm"] = [round(b["z_mean"], 1) for b in bands]

    if len(bands) < 2:
        result["warnings"].append(
            "fewer than 2 tread-top bands detected -- riser/tread series unavailable"
        )

    # Curvature check: a straight flight's tread centroids sit at (almost)
    # the same lateral position from the first tread to the last; a winder
    # or curved-plan flight's rotate with the walking line. This is an
    # ABSOLUTE-drift check, not a ratio against width -- see
    # DEFAULT_CURVATURE_DRIFT_MM for why a ratio would false-positive on
    # any ordinary wide-but-straight stair.
    lateral_means = [b["lateral_mean"] for b in bands if "lateral_mean" in b]
    if len(lateral_means) >= 2:
        lateral_drift = max(lateral_means) - min(lateral_means)
        result["tread_lateral_drift_mm"] = round(lateral_drift, 1)
        if lateral_drift > DEFAULT_CURVATURE_DRIFT_MM:
            result["winder_suspected"] = True
            result["warnings"].append(
                f"tread centroids drift {lateral_drift:.0f}mm laterally along this "
                "flight's run, suggesting real plan curvature (winder or curved "
                "stair) -- MinTreadDepth/MaxTreadDepth are measured along a single "
                "straight walking-direction axis and do NOT represent true "
                "per-position (inner/walking-line/outer) tread depth for a "
                "winder; a dedicated winder analysis is not yet implemented"
            )

    # Open-riser detection: for each tread-to-tread transition, does the
    # mesh carry a near-vertical FACE bridging the lower tread's elevation
    # up to the upper one's, at that run position? A closed riser is such a
    # face; an open riser has none there.
    #
    # Checking for nearby POINTS instead of an actual face is not enough:
    # since two consecutive treads share their boundary run-coordinate
    # whether or not a riser connects them, each tread's own top-face
    # corners already supply a point near both z_low and z_high at that
    # x-position regardless of whether a riser exists -- a point-proximity
    # check cannot tell the two cases apart. Requiring a genuine
    # near-vertical face (normal close to horizontal) whose OWN vertices
    # span the gap is what actually distinguishes them.
    if len(bands) >= 2:
        open_transitions: list[float] = []
        for i in range(len(bands) - 1):
            transition_run = (bands[i]["run_max"] + bands[i + 1]["run_min"]) / 2.0
            tol = max(z_gap_mm / 2.0, 20.0)
            z_low, z_high = bands[i]["z_mean"], bands[i + 1]["z_mean"]
            if not _riser_face_bridges(
                verts, faces, origin, u, v, transition_run, z_low, z_high, tol
            ):
                open_transitions.append(round(transition_run, 1))

        result["open_riser"] = len(open_transitions) > 0
        if open_transitions:
            result["open_riser_run_positions_mm"] = open_transitions
    else:
        result["open_riser"] = None

    return result


#: Default number of interior Z-heights sampled between a guard's top and
#: bottom elevation when measuring baluster/infill openings. Sampling
#: several heights (not just one) catches infill whose spacing varies with
#: height -- a raked/angled picket, a lattice pattern -- the way
#: min_clear_width_by_band samples several run positions rather than one.
DEFAULT_OPENING_Z_SAMPLES = 5

#: Separations below this (mm) are floating-point/tessellation noise, not a
#: real opening -- unlike DEFAULT_GAP_MM (used for continuity, where small
#: seams should be ignored as "still one piece"), an opening check wants to
#: see almost every real gap, since even a modest one can fail a sphere test.
_OPENING_NOISE_FLOOR_MM = 1.0


def _face_z_ranges(verts, faces):
    """Return (M,) arrays (z_min, z_max) per face."""
    face_z = verts[:, 2][faces]
    return face_z.min(axis=1), face_z.max(axis=1)


def guard_opening_gap_at_height(
    verts, faces, origin, u, v, z: float, run_span: tuple[float, float], band_mm: float = 20.0
) -> float | None:
    """Largest horizontal (run-axis) gap in the guard's infill coverage at
    height *z*, or None if the mesh has no faces at all (nothing to measure
    anywhere, not just at this height).

    Approximates a true horizontal cross-section: rather than computing the
    exact line where each triangle crosses the plane z=z (expensive, and
    unnecessary precision for this purpose), it selects every face whose OWN
    Z-extent overlaps a thin band around *z* and finds the run-axis gaps in
    their combined coverage. This can slightly UNDER-report a gap (a face
    spanning past the band on one side still counts as "covering" the band),
    which is the conservative direction for a safety check -- it will not
    invent an opening that is not there, though it can occasionally miss one
    genuinely at the edge of a member.

    A height where NOTHING overlaps at all (no top/bottom rail, no baluster
    anywhere near it) is not "unmeasurable" -- it is the guard being
    completely open there, the worst case this check exists to catch -- so
    it reports the full *run_span* as the opening, not None.
    """
    if faces is None or faces.size == 0:
        return None
    run_min, run_max = run_span
    z_lo, z_hi = z - band_mm / 2.0, z + band_mm / 2.0
    face_z_min, face_z_max = _face_z_ranges(verts, faces)
    overlapping = (face_z_max >= z_lo) & (face_z_min <= z_hi)
    if not np.any(overlapping):
        return round(run_max - run_min, 1)
    intervals = face_run_intervals(verts, faces[overlapping], origin, u, v)
    _segments, gaps = merge_run_intervals(intervals, gap_mm=_OPENING_NOISE_FLOOR_MM)
    if not gaps:
        return 0.0
    return round(max(hi - lo for lo, hi in gaps), 1)


def guard_opening_profile(
    verts, faces, origin, u, v,
    z_min: float, z_max: float,
    run_span: tuple[float, float],
    n_samples: int = DEFAULT_OPENING_Z_SAMPLES,
) -> dict:
    """Sample several interior heights between *z_min* and *z_max* and
    report the worst (largest) horizontal infill gap found -- the measurement
    a sphere/baluster-spacing rule checks against.

    Returns {"max_opening_mm": float | None, "samples_mm": [float, ...]}.
    ``samples_mm`` lists the gap found at every height sampled (a fully-open
    height contributes *run_span*'s full width, per
    ``guard_opening_gap_at_height`` -- see there for why that is not treated
    as missing data).
    """
    if z_max <= z_min or n_samples < 1:
        return {"max_opening_mm": None, "samples_mm": []}
    heights = np.linspace(z_min, z_max, n_samples + 2)[1:-1]
    samples = [
        gap for gap in (
            guard_opening_gap_at_height(verts, faces, origin, u, v, float(h), run_span)
            for h in heights
        )
        if gap is not None
    ]
    if not samples:
        return {"max_opening_mm": None, "samples_mm": []}
    return {"max_opening_mm": round(max(samples), 1), "samples_mm": samples}


def _min_rotated_rect_dims_mm(run, lateral) -> tuple[float, float] | None:
    """Return (short_side_mm, long_side_mm) of the min-rotated-rectangle
    enclosing the (run, lateral) point set, or None if shapely is unavailable
    or the point set is degenerate."""
    if not _SHAPELY_AVAILABLE:
        return None
    pts = list(zip(run.tolist(), lateral.tolist()))
    if len(pts) < 3:
        return None
    try:
        hull = shapely.geometry.MultiPoint(pts).convex_hull
        if hull.geom_type != "Polygon":
            return None
        mrr = hull.minimum_rotated_rectangle
        coords = list(mrr.exterior.coords)
        sides = [
            math.hypot(coords[i][0] - coords[i + 1][0], coords[i][1] - coords[i + 1][1])
            for i in range(4)
        ]
        return round(min(sides), 1), round(max(sides), 1)
    except Exception:
        return None


def analyze_landing(slab, geometry_extractor) -> dict:
    """Clear width/length/area/elevation for one landing IfcSlab.

    Deliberately does NOT read ``Qto_SlabBaseQuantities.Width`` -- see the
    landmine documented in docs/ifc-property-mapping.md: that quantity is
    slab thickness on every IfcSlab, landings included, never clear walking
    width. Clear width/length here are always derived from the slab's own
    footprint mesh.
    """
    result: dict[str, Any] = {"guid": getattr(slab, "GlobalId", None), "warnings": []}
    if not (_NP_AVAILABLE and geometry_extractor):
        result["warnings"].append("numpy or geometry extractor unavailable")
        return result

    verts, faces = geometry_extractor._get_mesh_mm(slab)
    if verts is None or verts.shape[0] < 3:
        result["warnings"].append("no resolvable geometry for this landing")
        return result

    frame = local_frame_from_xy(verts[:, :2])
    if frame is None:
        result["warnings"].append("degenerate footprint")
        return result
    origin, u, v = frame
    run, lateral, _z = project_local(verts, origin, u, v)

    dims = _min_rotated_rect_dims_mm(run, lateral)
    if dims is None:
        result["warnings"].append("shapely unavailable or degenerate footprint")
    else:
        result["clear_width_mm"], result["clear_length_mm"] = dims

    area_m2 = geometry_extractor.get_footprint_area_m2(slab)
    if area_m2 is not None:
        result["clear_area_mm2"] = round(area_m2 * 1e6, 1)

    top_z = geometry_extractor.get_top_z_mm(slab)
    if top_z is not None:
        result["elevation_mm"] = top_z

    # Walking-surface slope, NOT geometry_extractor.get_slope_deg(): that
    # generic Tier 1 method divides the WHOLE element's bounding-box Z-extent
    # by its horizontal extent, which for a landing reads its own THICKNESS
    # as slope -- a perfectly flat 200mm-thick slab over a 1200mm footprint
    # would report ~9.5 degrees. Isolating the top (upward-facing) surface
    # first, the same way analyze_stair_flight isolates tread tops, measures
    # the walking surface's own tilt instead.
    top_pts = _face_up_points(verts, faces)
    if top_pts is not None and top_pts.shape[0] >= 2:
        top_run, _top_lateral, top_z = project_local(top_pts, origin, u, v)
        run_extent = float(top_run.max() - top_run.min())
        z_extent = float(top_z.max() - top_z.min())
        result["slope_deg"] = round(math.degrees(math.atan2(z_extent, run_extent)), 2) if run_extent > 0 else 0.0

    return result


def analyze_railing(railing, geometry_extractor, floor_z_mm: float | None = None) -> dict:
    """Path/height/continuity analysis for one IfcRailing (handrail or guard).

    ``floor_z_mm``, when supplied, lets height be reported relative to the
    local walking surface (matching ``ifc_geometry``'s existing
    ``handrail_height`` convention: top elevation minus floor_z) rather than
    only as absolute world elevations. Callers without a reliable host
    flight/landing to reference can omit it; absolute elevations are still
    reported.
    """
    result: dict[str, Any] = {"guid": getattr(railing, "GlobalId", None), "warnings": []}

    # Guard-type elements (anything other than a plain HANDRAIL, including an
    # unset/NOTDEFINED PredefinedType -- safer to flag a possibly-a-guard
    # element than to assume it is a handrail with nothing missing) get a
    # warning noting the checks this module does not yet compute for them.
    # Attached here, up front, so it rides along in EVERY property this
    # element resolves (height, continuity, ...) rather than only appearing
    # if a rule happens to ask for baluster spacing by name -- which would
    # otherwise just look like an ordinary missing property, no different
    # from a genuinely unauthored one.
    predefined_type = str(getattr(railing, "PredefinedType", None) or "").upper()
    result["predefined_type"] = predefined_type or None
    is_guard_like = predefined_type != "HANDRAIL"
    if is_guard_like:
        result["warnings"].append(
            f"PredefinedType={predefined_type or 'unset'} -- MaxOpeningWidth/"
            "BottomClearGap below are single-axis approximations (largest "
            "horizontal gap per sampled height; typical under-rail gap), not "
            "a true multi-directional sphere-passing simulation, and "
            "baluster CENTRE-TO-CENTRE spacing and the triangular "
            "stair-nosing opening are not yet computed (v1 limitation); "
            "height, continuity and profile-thickness checks above are "
            "still valid"
        )

    if not (_NP_AVAILABLE and geometry_extractor):
        result["warnings"].append("numpy or geometry extractor unavailable")
        return result

    verts, faces = geometry_extractor._get_mesh_mm(railing)
    if verts is None or verts.shape[0] < 3:
        result["warnings"].append("no resolvable geometry for this railing")
        return result

    frame = local_frame_from_xy(verts[:, :2])
    if frame is None:
        result["warnings"].append("degenerate footprint (rail too short or coincident points)")
        return result
    origin, u, v = frame
    run, lateral, z = project_local(verts, origin, u, v)

    result["path_length_mm"] = round(float(run.max() - run.min()), 1) if run.size else None
    lateral_spread = float(lateral.max() - lateral.min()) if lateral.size else 0.0
    if result["path_length_mm"] and lateral_spread > 0.15 * result["path_length_mm"]:
        result["warnings"].append(
            "path_length_mm is a straight-line approximation; this rail's lateral "
            "spread suggests real curvature (winder or curved plan) that a "
            "straight run-axis projection undercounts"
        )

    # Height profile, banded along the run axis: top and bottom Z per band.
    run_min, run_max = float(run.min()), float(run.max())
    n_bands = max(1, int(math.ceil((run_max - run_min) / DEFAULT_RUN_BAND_MM))) if run_max > run_min else 0
    tops: list[float] = []
    bottoms: list[float] = []
    for b in range(n_bands):
        lo = run_min + b * DEFAULT_RUN_BAND_MM
        hi = lo + DEFAULT_RUN_BAND_MM
        mask = (run >= lo) & (run <= hi)
        if mask.sum() < 1:
            continue
        tops.append(float(z[mask].max()))
        bottoms.append(float(z[mask].min()))

    if tops:
        result["max_top_elevation_mm"] = round(max(tops), 1)
        result["min_top_elevation_mm"] = round(min(tops), 1)
        result["top_elevation_variation_mm"] = round(max(tops) - min(tops), 1)
        if floor_z_mm is not None:
            result["max_height_mm"] = round(max(tops) - floor_z_mm, 1)
            result["min_height_mm"] = round(min(tops) - floor_z_mm, 1)
    if bottoms:
        result["min_bottom_elevation_mm"] = round(min(bottoms), 1)
        # Median, not minimum: a post/baluster typically anchors AT the
        # walking surface (bottom elevation ~= floor_z there), which would
        # make the pure minimum read as "no gap" everywhere even when the
        # bottom RAIL between posts sits well clear of the floor. The median
        # across run-bands is dominated by the rail's own (more common)
        # elevation instead of the few post-footprint outliers.
        median_bottom = float(np.median(bottoms))
        reference_z = floor_z_mm if floor_z_mm is not None else float(z.min())
        result["bottom_clear_gap_mm"] = round(max(0.0, median_bottom - reference_z), 1)

    if is_guard_like:
        opening = guard_opening_profile(
            verts, faces, origin, u, v, float(z.min()), float(z.max()), (run_min, run_max)
        )
        if opening["max_opening_mm"] is not None:
            result["max_opening_mm"] = opening["max_opening_mm"]
            result["opening_samples_mm"] = opening["samples_mm"]
            candidates = [opening["max_opening_mm"]]
            if "bottom_clear_gap_mm" in result:
                candidates.append(result["bottom_clear_gap_mm"])
            result["guard_max_opening_mm"] = round(max(candidates), 1)

    intervals = face_run_intervals(verts, faces, origin, u, v)
    segments, gaps = merge_run_intervals(intervals)
    result["continuous_segments"] = len(segments) if segments else (1 if run.size else 0)
    # 0.0, not None, when there are no gaps: continuity was actually
    # evaluated (matching continuous_segments' own convention just above),
    # so "no gap found" is a real determinate answer, not a missing one.
    result["max_gap_length_mm"] = round(max(hi - lo for lo, hi in gaps), 1) if gaps else 0.0
    if gaps:
        result["gap_locations_mm"] = gaps

    # Profile thickness near mid-run: a coarse cross-section estimate, not a
    # true perpendicular slice -- adequate for a min/max profile dimension
    # check, not for certifying graspability to the mm.
    mid = (run_min + run_max) / 2.0
    mask = np.abs(run - mid) <= DEFAULT_RUN_BAND_MM / 2.0
    if mask.sum() >= 3:
        result["profile_lateral_mm"] = round(float(lateral[mask].max() - lateral[mask].min()), 1)
        result["profile_vertical_mm"] = round(float(z[mask].max() - z[mask].min()), 1)

    return result


# ── Engine: build once per model, cache by GUID ───────────────────────────────


class IFCStairEngine:
    """Builds and caches per-flight/landing/railing stair geometry analysis.

    Mirrors ``IFCEgressGraph``'s lazy-build-once pattern: constructed once in
    ``IFCReader.load_ifc_file()``, ``build()`` walks the model a single time
    regardless of how many rules subsequently ask for a stair-derived
    property.
    """

    def __init__(self, ifc_file, geometry_extractor):
        self.ifc_file = ifc_file
        self.geometry_extractor = geometry_extractor
        self._flights: dict[str, dict] = {}
        self._landings: dict[str, dict] = {}
        self._railings: dict[str, dict] = {}
        # Parent IfcStair GUID -> list of flight GUIDs, for cross-flight
        # (whole-stairway) uniformity aggregation -- codes require riser/tread
        # uniformity across the WHOLE stairway, not just within one flight.
        self._stair_flight_guids: dict[str, list[str]] = {}
        self._built = False

    def build(self) -> "IFCStairEngine":
        if self._built or not self.ifc_file:
            self._built = True
            return self

        flights = self._flights_with_fallback()
        for flight in flights:
            try:
                analysis = analyze_stair_flight(flight, self.geometry_extractor)
            except Exception as exc:
                logger.debug("Stair flight analysis failed for %s: %s", flight, exc)
                analysis = {"guid": getattr(flight, "GlobalId", None), "warnings": [str(exc)]}
            guid = getattr(flight, "GlobalId", None)
            if guid:
                analysis["world_bbox"] = self.geometry_extractor.get_bounding_box(flight)
                self._flights[guid] = analysis
                stair_guid = self._parent_stair_guid(flight) or guid
                self._stair_flight_guids.setdefault(stair_guid, []).append(guid)

        try:
            slabs = self.ifc_file.by_type("IfcSlab")
        except Exception:
            slabs = []
        for slab in slabs:
            if str(getattr(slab, "PredefinedType", None) or "").upper() != "LANDING":
                continue
            try:
                analysis = analyze_landing(slab, self.geometry_extractor)
            except Exception as exc:
                logger.debug("Landing analysis failed for %s: %s", slab, exc)
                analysis = {"guid": getattr(slab, "GlobalId", None), "warnings": [str(exc)]}
            guid = getattr(slab, "GlobalId", None)
            if guid:
                analysis["world_bbox"] = self.geometry_extractor.get_bounding_box(slab)
                self._landings[guid] = analysis

        railings = self._railings_with_fallback()
        for railing in railings:
            try:
                analysis = analyze_railing(railing, self.geometry_extractor)
            except Exception as exc:
                logger.debug("Railing analysis failed for %s: %s", railing, exc)
                analysis = {"guid": getattr(railing, "GlobalId", None), "warnings": [str(exc)]}
            guid = getattr(railing, "GlobalId", None)
            if guid:
                analysis["world_bbox"] = self.geometry_extractor.get_bounding_box(railing)
                self._railings[guid] = analysis

        self._link_elements()

        self._built = True
        return self

    def _flights_with_fallback(self) -> list:
        try:
            flights = list(self.ifc_file.by_type("IfcStairFlight"))
        except Exception:
            flights = []
        if flights:
            return flights
        try:
            stairs = list(self.ifc_file.by_type("IfcStair"))
        except Exception:
            stairs = []
        return stairs

    def _railings_with_fallback(self) -> list:
        try:
            railings = list(self.ifc_file.by_type("IfcRailing"))
        except Exception:
            railings = []
        if railings:
            return railings
        try:
            return list(self.ifc_file.by_type("IfcHandRail"))
        except Exception:
            return []

    @staticmethod
    def _parent_stair_guid(flight) -> str | None:
        try:
            for rel in getattr(flight, "Decomposes", []):
                parent = rel.RelatingObject
                if parent.is_a("IfcStair"):
                    return parent.GlobalId
        except Exception:
            pass
        return None

    # ── Cross-referencing: flight <-> landing <-> railing <-> stair ─────────

    def _link_elements(self) -> None:
        """Second pass, run once after every flight/landing/railing has been
        analysed: match landings to the flight(s) they connect, and railings
        to the flight/landing they run alongside, via world-bbox proximity
        (IFC decomposition already gives flight->stair in pass one, but
        rarely goes further -- landings and railings are usually siblings in
        the file, not children of a shared parent, so proximity is the
        primary signal here, not a fallback).

        Every flight/landing/railing ends up carrying its own ``stair_guid``
        directly on its analysis dict (not just in the separate
        ``_stair_flight_guids`` grouping), so it can be exposed as an
        ordinary derived property the same way as everything else.
        """
        flight_stair: dict[str, str] = {}
        for stair_guid, members in self._stair_flight_guids.items():
            for fguid in members:
                flight_stair[fguid] = stair_guid
                self._flights[fguid]["stair_guid"] = stair_guid
                # Determinate zero, not absent: every railing in the model
                # gets a nearest-flight match attempt below, so "none matched
                # this flight" is a real finding (no handrail/guard here),
                # not a case this pass never got to.
                self._flights[fguid]["handrail_count"] = 0
                self._flights[fguid]["guard_count"] = 0

        # -- Landings: match by elevation (the strong signal -- a landing's
        # surface should sit almost exactly at a flight's start/end
        # elevation) AND plan proximity (the weak signal, mainly to rule out
        # an unrelated stair elsewhere with a coincidentally similar
        # elevation). A landing typically borders TWO flights -- the one you
        # just climbed (its END elevation matches) and the one you're about
        # to climb (its START elevation matches) -- so both are checked and
        # can both match, independently.
        for lguid, landing in self._landings.items():
            lbbox = landing.get("world_bbox")
            lelev = landing.get("elevation_mm")
            if lelev is None:
                continue
            best_below, best_below_dist = None, None
            best_above, best_above_dist = None, None
            for fguid, flight in self._flights.items():
                dist = bbox_xy_distance_mm(lbbox, flight.get("world_bbox"))
                if dist is None or dist > DEFAULT_HOST_PROXIMITY_MM:
                    continue
                end_elev = flight.get("end_elevation_mm")
                if (
                    end_elev is not None
                    and abs(end_elev - lelev) <= DEFAULT_LANDING_ELEVATION_TOLERANCE_MM
                    and (best_below_dist is None or dist < best_below_dist)
                ):
                    best_below, best_below_dist = fguid, dist
                start_elev = flight.get("start_elevation_mm")
                if (
                    start_elev is not None
                    and abs(start_elev - lelev) <= DEFAULT_LANDING_ELEVATION_TOLERANCE_MM
                    and (best_above_dist is None or dist < best_above_dist)
                ):
                    best_above, best_above_dist = fguid, dist

            mismatches: list[float] = []
            if best_below is not None:
                landing["connects_flight_below_guid"] = best_below
                self._flights[best_below]["landing_above_guid"] = lguid
                mismatches.append(abs(self._flights[best_below]["end_elevation_mm"] - lelev))
            if best_above is not None:
                landing["connects_flight_above_guid"] = best_above
                self._flights[best_above]["landing_below_guid"] = lguid
                mismatches.append(abs(self._flights[best_above]["start_elevation_mm"] - lelev))
            if mismatches:
                # The worst of the two: a landing is only as good as its
                # least-aligned connection.
                landing["level_mismatch_mm"] = round(max(mismatches), 1)

            host_flight = best_below or best_above
            if host_flight is not None:
                stair_guid = flight_stair.get(host_flight)
                if stair_guid:
                    landing["stair_guid"] = stair_guid

        # -- Railings: nearest flight OR landing by plan proximity, whichever
        # is closer. A handrail/guard almost always runs immediately beside
        # its host, so "nearest" is a reasonable, mounting-style-agnostic
        # match (works whether it's fixed to the flight's own edge or offset
        # to a wall) without requiring exact footprint overlap.
        for rguid, railing in self._railings.items():
            rbbox = railing.get("world_bbox")
            best_guid, best_type, best_dist = None, None, None
            for fguid, flight in self._flights.items():
                dist = bbox_xy_distance_mm(rbbox, flight.get("world_bbox"))
                if dist is not None and (best_dist is None or dist < best_dist):
                    best_guid, best_type, best_dist = fguid, "IfcStairFlight", dist
            for lguid, landing in self._landings.items():
                dist = bbox_xy_distance_mm(rbbox, landing.get("world_bbox"))
                if dist is not None and (best_dist is None or dist < best_dist):
                    best_guid, best_type, best_dist = lguid, "IfcSlab", dist

            if best_guid is None or best_dist is None or best_dist > DEFAULT_HOST_PROXIMITY_MM:
                continue
            railing["host_element_guid"] = best_guid
            railing["host_element_type"] = best_type
            if best_type == "IfcStairFlight":
                stair_guid = flight_stair.get(best_guid)
            else:
                stair_guid = self._landings[best_guid].get("stair_guid")
            if stair_guid:
                railing["stair_guid"] = stair_guid
            if best_type == "IfcStairFlight":
                key = (
                    "handrail_count"
                    if str(railing.get("predefined_type") or "").upper() == "HANDRAIL"
                    else "guard_count"
                )
                self._flights[best_guid][key] = self._flights[best_guid].get(key, 0) + 1

    # ── Accessors ──────────────────────────────────────────────────────────

    def get_flight(self, guid: str) -> dict | None:
        return self._flights.get(guid)

    def get_landing(self, guid: str) -> dict | None:
        return self._landings.get(guid)

    def get_railing(self, guid: str) -> dict | None:
        return self._railings.get(guid)

    def stair_flights(self, stair_guid: str) -> list[str]:
        """Flight GUIDs grouped under *stair_guid* (an IfcStair's GlobalId),
        or under its own GUID as a fallback key when a flight has no parent
        IfcStair (see ``_parent_stair_guid``). Empty list if unknown."""
        return list(self._stair_flight_guids.get(stair_guid) or [])

    def get_stair_uniformity(self, flight_guid: str) -> dict | None:
        """Whole-stairway riser/tread uniformity for the stair this flight
        belongs to -- pooling every flight's risers/treads, not just this
        one's. Returns None if the flight is unknown.
        """
        stair_guid = None
        for sguid, members in self._stair_flight_guids.items():
            if flight_guid in members:
                stair_guid = sguid
                break
        if stair_guid is None:
            return None

        all_risers: list[float] = []
        all_goings: list[float] = []
        for guid in self._stair_flight_guids[stair_guid]:
            analysis = self._flights.get(guid) or {}
            all_risers.extend(analysis.get("risers_mm") or [])
            all_goings.extend(analysis.get("goings_mm") or [])

        if not all_risers and not all_goings:
            return None

        result: dict[str, Any] = {
            "stair_guid": stair_guid,
            "flight_count": len(self._stair_flight_guids[stair_guid]),
        }
        if all_risers:
            result["riser_difference_mm"] = round(max(all_risers) - min(all_risers), 1)
            result["min_riser_mm"] = round(min(all_risers), 1)
            result["max_riser_mm"] = round(max(all_risers), 1)
        if all_goings:
            result["going_difference_mm"] = round(max(all_goings) - min(all_goings), 1)
            result["min_going_mm"] = round(min(all_goings), 1)
            result["max_going_mm"] = round(max(all_goings), 1)
        return result


def stair_context(el, engine: "IFCStairEngine | None") -> dict:
    """Return the cached stair-derived data for one element, or {}.

    Dispatches on the element's own IFC class so ``ifc_reader``'s resolver
    can call this uniformly for IfcStairFlight, IfcStair, IfcSlab(LANDING)
    and IfcRailing without needing to know which cache to look in.
    """
    if engine is None:
        return {}
    guid = getattr(el, "GlobalId", None)
    if not guid:
        return {}

    try:
        is_a = el.is_a
    except Exception:
        return {}

    if is_a("IfcStairFlight"):
        flight = engine.get_flight(guid) or {}
        context = dict(flight)
        uniformity = engine.get_stair_uniformity(guid)
        if uniformity:
            context["stair_uniformity"] = uniformity
        return context

    if is_a("IfcStair"):
        # A rule targeting the IfcStair container itself (rather than one of
        # its flights) gets the pooled whole-stairway uniformity directly --
        # look it up via any one of this stair's own flights.
        members = engine.stair_flights(guid)
        if members:
            uniformity = engine.get_stair_uniformity(members[0])
            return {"stair_uniformity": uniformity} if uniformity else {}
        return {}

    if is_a("IfcSlab"):
        return dict(engine.get_landing(guid) or {})

    if is_a("IfcRailing") or is_a("IfcHandRail"):
        return dict(engine.get_railing(guid) or {})

    return {}
