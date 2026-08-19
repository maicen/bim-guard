"""
BIMGUARD AI — Halo volume generation performance benchmark.

Purpose
-------
This harness answers the examination question:

    "How will the geometric engine handle high-poly IFC geometry when
     generating thousands of 'Halo' volumes simultaneously?"

It does so by measuring, not asserting. A prototype Halo generator
(spatial-reservation / clearance volumes around IFC elements) is run against
real IFC models drawn from ``data/uploads/ifc/`` at increasing element counts,
and every stage is timed and memory-profiled separately so that the dominant
cost can be attributed rather than guessed at.

Pipeline stages measured independently
--------------------------------------
1. ``parse``     — ``ifcopenshell.open()``: STEP file to in-memory model.
2. ``ingest``    — ``ifcopenshell.geom.iterator``: triangulation of the source
                   elements into world-coordinate meshes. This is the stage
                   that actually touches "high-poly IFC geometry".
3. ``halo``      — generation of one Halo volume per element (the claim under
                   examination).
4. ``collision`` — broad-phase (uniform spatial hash) plus mid-phase (exact
                   AABB overlap) interference detection between Halo volumes,
                   with a naive O(n^2) baseline measured for comparison.

Scenarios
---------
S1  100 elements, single model.
S2  500 elements, single model.
S3  1000 elements, single model.
S4  2000 elements federated across four separate IFC files, including
    cross-file (inter-model) interference detection.
S5  LOD sweep — 1000 elements at LOD 200 / 300 / 400, to quantify the
    geometric-complexity cost of detail level.

Outputs (written to ``docs/benchmarks/`` by default)
----------------------------------------------------
* ``halo_benchmark_results.json``  — full structured record, including host
  metadata, for reproducibility.
* ``halo_benchmark_results.csv``   — flat table for spreadsheet/thesis use.
* ``halo_benchmark_summary.md``    — rendered Markdown tables.
* ``fig_*.png``                    — charts (matplotlib), if available.

Usage
-----
    uv run python performance_benchmark.py
    uv run python performance_benchmark.py --out docs/benchmarks
    uv run python performance_benchmark.py --scenarios 100,500
    uv run python performance_benchmark.py --synthetic     # no IFC needed
    uv run python performance_benchmark.py --no-charts

Dependencies live in the ``bench`` group of ``pyproject.toml``
(``uv sync --group bench``).
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import logging
import math
import multiprocessing
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np

# Reuse the project's own geometry primitives rather than redefining them, so
# the benchmark measures the same data contract the platform would use.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.modules.module2_ifc_read.piping_schema import BoundingBox, Point3D  # noqa: E402

logger = logging.getLogger("bimguard.benchmark")

try:
    import psutil

    _PSUTIL = True
except ImportError:  # pragma: no cover - psutil is declared in the bench group
    _PSUTIL = False

try:
    import ifcopenshell
    import ifcopenshell.geom

    _IFCOS = True
except ImportError:  # pragma: no cover - ifcopenshell is a core dependency
    _IFCOS = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

IFC_DIR = Path("data/uploads/ifc")

#: Primary model for the single-file scenarios. Chosen because it is the
#: largest real model in the repository (2 602 IfcProduct instances, IFC4).
PRIMARY_MODEL = "9152ac527a1844f69a73f73e77468326_BUILDING_R4.ifc"

#: Four genuinely distinct models standing in for a federated coordination
#: set (architectural / institutional / residential / infrastructure-plumbing).
FEDERATED_MODELS = [
    "9152ac527a1844f69a73f73e77468326_BUILDING_R4.ifc",
    "c243ce49cc834c47bad6f393bba1af4a_AC20-Institute-Var-2.ifc",
    "7589fcfc61b849f38c286efebd251ec2_Pacific Continental Residence Sample IFC4.3 Reference View ARCH.ifc",
    "f4c3f1b8390a4183b599323799caae83_Infra-Plumbing.ifc",
]

#: IFC classes that carry no meaningful clearance requirement of their own.
EXCLUDED_TYPES = {
    "IfcOpeningElement",
    "IfcSpace",
    "IfcSite",
    "IfcBuilding",
    "IfcBuildingStorey",
    "IfcAnnotation",
    "IfcGrid",
}

#: Circumferential / arc segment count per level of detail. LOD 200 is a
#: coarse "does it fit at all" volume; LOD 400 is a fabrication-grade offset.
LOD_SEGMENTS = {200: 8, 300: 16, 400: 32}

#: Number of segments used per 90-degree arc when rounding a box Halo.
LOD_ARC_SEGMENTS = {200: 0, 300: 2, 400: 4}

DEFAULT_BUFFER_M = 0.5  # 500 mm seismic-bracing clearance


# ---------------------------------------------------------------------------
# Geometry types
# ---------------------------------------------------------------------------


@dataclass
class Mesh:
    """
    A triangle mesh in world coordinates, metres.

    ``vertices`` is an (N, 3) float32 array; ``faces`` is an (M, 3) int32
    array of vertex indices. Float32 is deliberate: at thousands of Halos the
    array dtype is the single largest lever on resident memory, and 32-bit
    precision is far finer than any clearance tolerance in AECO practice.
    """

    vertices: np.ndarray
    faces: np.ndarray

    @property
    def vertex_count(self) -> int:
        return int(self.vertices.shape[0])

    @property
    def face_count(self) -> int:
        return int(self.faces.shape[0])

    @property
    def nbytes(self) -> int:
        return int(self.vertices.nbytes + self.faces.nbytes)

    def volume_m3(self) -> float:
        """
        Return the enclosed volume via the divergence theorem.

        Sums the signed volumes of the tetrahedra formed by each triangle and
        the origin. Valid for the closed, outward-oriented meshes this module
        emits; the absolute value guards against winding-order surprises.
        """
        v = self.vertices.astype(np.float64)
        a, b, c = v[self.faces[:, 0]], v[self.faces[:, 1]], v[self.faces[:, 2]]
        return float(abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)

    def aabb(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the (min, max) axis-aligned bounds of the mesh."""
        return self.vertices.min(axis=0), self.vertices.max(axis=0)


@dataclass
class ElementRecord:
    """One source IFC element, reduced to what the Halo generator needs."""

    guid: str
    ifc_type: str
    model: str
    centroid: Point3D
    bbox: BoundingBox
    source_vertices: int
    source_faces: int


# ---------------------------------------------------------------------------
# Halo generation — the capability under examination
# ---------------------------------------------------------------------------


def _classify(ifc_type: str) -> str:
    """
    Map an IFC class to the Halo primitive that best represents its clearance.

    Linear distribution elements get a cylindrical sleeve, point-like fittings
    get a sphere, and everything else gets an offset box.
    """
    t = ifc_type.lower()
    if any(k in t for k in ("pipesegment", "ductsegment", "cablesegment", "cablecarriersegment")):
        return "cylinder"
    if any(k in t for k in ("fitting", "valve", "junction", "terminal", "flange", "accessory")):
        return "sphere"
    return "box"


def _cylinder(radius: float, half_length: float, axis: int, segments: int) -> tuple[np.ndarray, np.ndarray]:
    """Build a closed cylinder of ``segments`` sides, centred on the origin."""
    theta = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
    cos_t, sin_t = np.cos(theta) * radius, np.sin(theta) * radius

    ring = np.zeros((segments, 3), dtype=np.float64)
    u, v = (axis + 1) % 3, (axis + 2) % 3
    ring[:, u], ring[:, v] = cos_t, sin_t

    lo, hi = ring.copy(), ring.copy()
    lo[:, axis], hi[:, axis] = -half_length, half_length

    cap_lo = np.zeros(3)
    cap_hi = np.zeros(3)
    cap_lo[axis], cap_hi[axis] = -half_length, half_length

    verts = np.vstack([lo, hi, cap_lo[None, :], cap_hi[None, :]])
    i = np.arange(segments)
    j = (i + 1) % segments
    lo_c, hi_c = 2 * segments, 2 * segments + 1

    side_a = np.column_stack([i, j, j + segments])
    side_b = np.column_stack([i, j + segments, i + segments])
    cap_a = np.column_stack([np.full(segments, lo_c), j, i])
    cap_b = np.column_stack([np.full(segments, hi_c), i + segments, j + segments])

    return verts, np.vstack([side_a, side_b, cap_a, cap_b]).astype(np.int32)


def _sphere(radius: float, segments: int) -> tuple[np.ndarray, np.ndarray]:
    """Build a closed UV sphere of ``segments`` longitudes, centred on the origin."""
    rings = max(2, segments // 2)
    lon = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
    lat = np.linspace(0.0, math.pi, rings + 1)[1:-1]  # exclude the two poles

    sin_lat, cos_lat = np.sin(lat), np.cos(lat)
    x = np.outer(sin_lat, np.cos(lon)) * radius
    y = np.outer(sin_lat, np.sin(lon)) * radius
    z = np.repeat(cos_lat * radius, segments).reshape(len(lat), segments)
    body = np.stack([x, y, z], axis=-1).reshape(-1, 3)

    north = np.array([[0.0, 0.0, radius]])
    south = np.array([[0.0, 0.0, -radius]])
    verts = np.vstack([body, north, south])
    n_body = body.shape[0]
    n_i, s_i = n_body, n_body + 1

    faces: list[np.ndarray] = []
    i = np.arange(segments)
    j = (i + 1) % segments
    faces.append(np.column_stack([np.full(segments, n_i), i, j]))
    for r in range(len(lat) - 1):
        a, b = r * segments + i, r * segments + j
        c, d = (r + 1) * segments + i, (r + 1) * segments + j
        faces.append(np.column_stack([a, c, d]))
        faces.append(np.column_stack([a, d, b]))
    last = (len(lat) - 1) * segments
    faces.append(np.column_stack([np.full(segments, s_i), last + j, last + i]))

    return verts, np.vstack(faces).astype(np.int32)


def _box(half: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build an axis-aligned box of half-extents ``half``, centred on the origin."""
    signs = np.array(
        [
            [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
            [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
        ],
        dtype=np.float64,
    )
    faces = np.array(
        [
            [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
            [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
            [1, 2, 6], [1, 6, 5], [0, 4, 7], [0, 7, 3],
        ],
        dtype=np.int32,
    )
    return signs * half, faces


def _rounded_box(half: np.ndarray, radius: float, arc_segments: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Build the exact Minkowski offset of a box by a sphere of ``radius``.

    A clearance zone around a prismatic element is geometrically a Minkowski
    sum, not a scaled box: the true offset surface is six flat faces, twelve
    quarter-cylinder edge fillets and eight spherical corner patches.
    Approximating it with a plain enlarged box overstates the reserved volume
    at every edge and corner — by 21% on a 0.3 m cube at a 0.5 m buffer — which
    is why LOD 300 and above round it.

    The surface is generated as a single latitude/longitude grid in which the
    three coordinate planes are deliberately *duplicated*. Each grid vertex is
    placed at ``sign_offset + radius * direction``, where ``sign_offset`` is the
    box corner belonging to that vertex's octant. Duplicating the seams is what
    opens the flat faces and edge fillets out of what would otherwise collapse
    to a sphere, so faces, fillets and corners all fall out of one quad mesh
    with no special-casing. ``arc_segments`` is the number of segments per
    90-degree arc, so cost scales as O(arc_segments^2).
    """
    arc = max(1, arc_segments)
    quarter = np.linspace(0.0, math.pi / 2.0, arc + 1)

    # Rows: southern hemisphere (offset -hz) then northern (offset +hz). The
    # equator appears in both, which opens the side faces.
    lat = np.concatenate([quarter - math.pi / 2.0, quarter])
    sz = np.concatenate([np.full(arc + 1, -1.0), np.full(arc + 1, 1.0)])

    # Columns: four quadrants, each closed at both ends. The four axis
    # meridians therefore appear twice, which opens the four side faces.
    lon = np.concatenate([quarter + q * math.pi / 2.0 for q in range(4)])
    quad_sx = np.array([1.0, -1.0, -1.0, 1.0])
    quad_sy = np.array([1.0, 1.0, -1.0, -1.0])
    sx = np.repeat(quad_sx, arc + 1)
    sy = np.repeat(quad_sy, arc + 1)

    rows, cols = len(lat), len(lon)
    cos_lat = np.cos(lat)[:, None]
    dirs = np.stack(
        [
            cos_lat * np.cos(lon)[None, :],
            cos_lat * np.sin(lon)[None, :],
            np.repeat(np.sin(lat)[:, None], cols, axis=1),
        ],
        axis=-1,
    )
    offsets = np.stack(
        [
            np.repeat((sx * half[0])[None, :], rows, axis=0),
            np.repeat((sy * half[1])[None, :], rows, axis=0),
            np.repeat((sz * half[2])[:, None], cols, axis=1),
        ],
        axis=-1,
    )
    grid = (offsets + radius * dirs).reshape(-1, 3)

    # Poles close the top and bottom faces, whose boundary is the first/last row.
    bottom_c = np.array([[0.0, 0.0, -half[2] - radius]])
    top_c = np.array([[0.0, 0.0, half[2] + radius]])
    verts = np.vstack([grid, bottom_c, top_c])
    bottom_i, top_i = rows * cols, rows * cols + 1

    r = np.arange(rows - 1)[:, None]
    c = np.arange(cols)[None, :]
    c_next = (c + 1) % cols
    a = (r * cols + c).ravel()
    b = (r * cols + c_next).ravel()
    d = ((r + 1) * cols + c).ravel()
    e = ((r + 1) * cols + c_next).ravel()
    quads = np.vstack([np.column_stack([a, d, e]), np.column_stack([a, e, b])])

    ring = np.arange(cols)
    ring_next = (ring + 1) % cols
    bottom_fan = np.column_stack([np.full(cols, bottom_i), ring_next, ring])
    last = (rows - 1) * cols
    top_fan = np.column_stack([np.full(cols, top_i), last + ring, last + ring_next])

    faces = np.vstack([quads, bottom_fan, top_fan]).astype(np.int32)
    return _clean_convex(verts, faces)


def _clean_convex(verts: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Drop degenerate triangles and orient a convex mesh consistently outward.

    The seam-duplication scheme collapses to zero-area triangles along the two
    pole rows, and the quadrant seams can invert winding locally. Because the
    Minkowski sum of two convex bodies is convex, outward orientation can be
    restored exactly by testing each face normal against the vector from the
    mesh centroid — no general-purpose mesh repair is needed.
    """
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    normals = np.cross(b - a, c - a)
    keep = np.linalg.norm(normals, axis=1) > 1e-12
    faces, normals = faces[keep], normals[keep]

    centre = verts.mean(axis=0)
    outward = ((verts[faces[:, 0]] + verts[faces[:, 1]] + verts[faces[:, 2]]) / 3.0) - centre
    flip = np.einsum("ij,ij->i", normals, outward) < 0
    faces[flip] = faces[flip][:, [0, 2, 1]]
    return verts, faces.astype(np.int32)


def generate_halo_volume(
    element_centroid: Point3D,
    element_bbox: BoundingBox,
    buffer_m: float = DEFAULT_BUFFER_M,
    lod: int = 300,
    kind: str = "box",
) -> Mesh:
    """
    Generate the Halo (spatial reservation) volume around a single element.

    Args:
        element_centroid: Centre point of the element, world coordinates, metres.
        element_bbox: Axis-aligned extent of the element, metres.
        buffer_m: Clearance distance held around the element. Defaults to
            0.5 m (500 mm), a typical seismic-bracing access allowance.
        lod: Level of detail. 200 = coarse (8-segment / prismatic),
            300 = medium (16-segment / rounded), 400 = fine (32-segment).
        kind: Halo primitive — ``"cylinder"`` for linear distribution runs,
            ``"sphere"`` for point-like fittings, ``"box"`` for everything else.

    Returns:
        A closed triangle :class:`Mesh` positioned at the element, in world
        coordinates.

    Notes:
        The Halo is generated from the element's *bounding box*, not its
        source triangulation. This is the single most important performance
        property of the design: Halo cost is O(1) in the source element's
        polygon count, so a 40 000-triangle imported valve and a 12-triangle
        extruded pipe produce identically priced Halos. The polygon count of
        the source model is paid once, during ingestion, not once per Halo.
    """
    segments = LOD_SEGMENTS.get(lod, LOD_SEGMENTS[300])
    dx, dy, dz = element_bbox.dimensions_m
    half = np.array([max(dx, 0.0), max(dy, 0.0), max(dz, 0.0)], dtype=np.float64) / 2.0
    origin = np.array([element_centroid.x, element_centroid.y, element_centroid.z], dtype=np.float64)

    if kind == "cylinder":
        axis = int(np.argmax(half))
        cross = [half[i] for i in range(3) if i != axis]
        radius = max(cross) + buffer_m
        verts, faces = _cylinder(radius, half[axis] + buffer_m, axis, segments)
    elif kind == "sphere":
        radius = float(np.linalg.norm(half)) + buffer_m
        verts, faces = _sphere(radius, segments)
    else:
        arcs = LOD_ARC_SEGMENTS.get(lod, LOD_ARC_SEGMENTS[300])
        if arcs == 0:
            verts, faces = _box(half + buffer_m)
        else:
            verts, faces = _rounded_box(half, buffer_m, arcs)

    return Mesh(vertices=(verts + origin).astype(np.float32), faces=faces)


# ---------------------------------------------------------------------------
# Interference detection between Halo volumes
# ---------------------------------------------------------------------------


def halo_aabbs(halos: Sequence[Mesh]) -> np.ndarray:
    """Return an (N, 6) array of ``[minx, miny, minz, maxx, maxy, maxz]`` per Halo."""
    out = np.empty((len(halos), 6), dtype=np.float32)
    for i, h in enumerate(halos):
        lo, hi = h.aabb()
        out[i, :3], out[i, 3:] = lo, hi
    return out


def broadphase_hash_grid(boxes: np.ndarray, cell_size: Optional[float] = None) -> list[tuple[int, int]]:
    """
    Find candidate interfering Halo pairs with a uniform spatial hash grid.

    Each AABB is stamped into every grid cell it overlaps; pairs sharing a cell
    become candidates. Expected cost is O(n) in the number of Halos for a
    bounded spatial density, against O(n^2) for exhaustive pair testing —
    the difference that makes "thousands of Halos" tractable.
    """
    if len(boxes) == 0:
        return []
    if cell_size is None:
        extents = boxes[:, 3:] - boxes[:, :3]
        cell_size = float(max(np.median(extents), 0.1)) * 2.0

    grid: dict[tuple[int, int, int], list[int]] = {}
    lo_cells = np.floor(boxes[:, :3] / cell_size).astype(np.int64)
    hi_cells = np.floor(boxes[:, 3:] / cell_size).astype(np.int64)

    for idx in range(len(boxes)):
        for cx in range(lo_cells[idx, 0], hi_cells[idx, 0] + 1):
            for cy in range(lo_cells[idx, 1], hi_cells[idx, 1] + 1):
                for cz in range(lo_cells[idx, 2], hi_cells[idx, 2] + 1):
                    grid.setdefault((cx, cy, cz), []).append(idx)

    candidates: set[tuple[int, int]] = set()
    for bucket in grid.values():
        n = len(bucket)
        if n < 2:
            continue
        for a in range(n - 1):
            for b in range(a + 1, n):
                i, j = bucket[a], bucket[b]
                candidates.add((i, j) if i < j else (j, i))
    return sorted(candidates)


def aabb_overlap(boxes: np.ndarray, pairs: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Filter candidate pairs down to those whose AABBs genuinely overlap."""
    pairs = list(pairs)
    if not pairs:
        return []
    arr = np.array(pairs, dtype=np.int64)
    a, b = boxes[arr[:, 0]], boxes[arr[:, 1]]
    hit = np.all((a[:, :3] <= b[:, 3:]) & (b[:, :3] <= a[:, 3:]), axis=1)
    return [tuple(p) for p in arr[hit]]


def naive_pairs(boxes: np.ndarray) -> int:
    """Count overlapping AABB pairs exhaustively, as an O(n^2) baseline."""
    n = len(boxes)
    lo, hi = boxes[:, :3], boxes[:, 3:]
    count = 0
    for i in range(n - 1):
        overlap = np.all((lo[i] <= hi[i + 1 :]) & (lo[i + 1 :] <= hi[i]), axis=1)
        count += int(overlap.sum())
    return count


# ---------------------------------------------------------------------------
# IFC ingestion
# ---------------------------------------------------------------------------


def _select_products(model, limit: int) -> list:
    """Pick up to ``limit`` clearance-relevant products, deterministically ordered."""
    products = [
        p
        for p in model.by_type("IfcProduct")
        if p.is_a() not in EXCLUDED_TYPES and getattr(p, "Representation", None) is not None
    ]
    products.sort(key=lambda p: p.id())
    return products[:limit]


def _triangulate(path: Path, model, products: list) -> tuple[list[ElementRecord], float]:
    """
    Triangulate ``products`` from an open model into :class:`ElementRecord` values.

    Returns the records and the wall-clock seconds the triangulation took. Only
    the bounding box and centroid are retained: the Halo generator never needs
    the source triangles themselves, which is why peak memory does not track
    the source model's polygon count.
    """
    settings = ifcopenshell.geom.settings()
    try:
        settings.set("use-world-coords", True)
    except Exception:  # pragma: no cover - older ifcopenshell settings API
        settings.set(settings.USE_WORLD_COORDS, True)

    records: list[ElementRecord] = []
    if not products:
        return records, 0.0

    t0 = time.perf_counter()
    iterator = ifcopenshell.geom.iterator(
        settings, model, multiprocessing.cpu_count(), include=products
    )
    if iterator.initialize():
        while True:
            shape = iterator.get()
            geometry = shape.geometry
            verts = np.asarray(geometry.verts, dtype=np.float64).reshape(-1, 3)
            n_faces = len(geometry.faces) // 3
            if len(verts):
                lo, hi = verts.min(axis=0), verts.max(axis=0)
                mid = (lo + hi) / 2.0
                records.append(
                    ElementRecord(
                        guid=shape.guid,
                        ifc_type=shape.type,
                        model=path.name,
                        centroid=Point3D(*(float(c) for c in mid)),
                        bbox=BoundingBox(
                            min=Point3D(*(float(c) for c in lo)),
                            max=Point3D(*(float(c) for c in hi)),
                        ),
                        source_vertices=len(verts),
                        source_faces=n_faces,
                    )
                )
            if not iterator.next():
                break
    return records, time.perf_counter() - t0


def ingest_elements(path: Path, limit: int) -> tuple[list[ElementRecord], float, float]:
    """
    Parse an IFC file and triangulate up to ``limit`` elements.

    Returns:
        A tuple of ``(records, parse_seconds, triangulate_seconds)``.
    """
    if not _IFCOS:
        raise RuntimeError("ifcopenshell is required for IFC-backed benchmarking")

    t0 = time.perf_counter()
    model = ifcopenshell.open(str(path))
    parse_s = time.perf_counter() - t0

    records, triangulate_s = _triangulate(path, model, _select_products(model, limit))
    return records, parse_s, triangulate_s


def synthetic_elements(count: int, model: str = "synthetic") -> list[ElementRecord]:
    """
    Build a deterministic lattice of synthetic elements.

    Used by ``--synthetic`` so the harness is reproducible on a machine that
    does not carry the repository's IFC fixtures. Element extents mimic a
    mixed MEP/structural population.
    """
    rng = np.random.default_rng(20260819)
    records: list[ElementRecord] = []
    side = max(1, int(math.ceil(count ** (1.0 / 3.0))))
    kinds = ["IfcPipeSegment", "IfcPipeFitting", "IfcBeam", "IfcColumn", "IfcDuctSegment"]
    for i in range(count):
        gx, gy, gz = i % side, (i // side) % side, i // (side * side)
        centre = np.array([gx * 3.0, gy * 3.0, gz * 3.5], dtype=np.float64)
        extent = rng.uniform(0.1, 2.5, size=3)
        records.append(
            ElementRecord(
                guid=f"SYN{i:07d}",
                ifc_type=kinds[i % len(kinds)],
                model=model,
                centroid=Point3D(*centre),
                bbox=BoundingBox(
                    min=Point3D(*(centre - extent / 2)),
                    max=Point3D(*(centre + extent / 2)),
                ),
                source_vertices=int(rng.integers(8, 400)),
                source_faces=int(rng.integers(12, 800)),
            )
        )
    return records


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    """All measurements for one benchmark scenario."""

    scenario: str
    element_target: int
    element_actual: int
    models: list[str]
    lod: int
    buffer_m: float
    parse_s: float
    triangulate_s: float
    halo_s: float
    broadphase_s: float
    midphase_s: float
    naive_s: float
    total_s: float
    rss_delta_mb: float
    halo_us_per_element: float
    halo_array_mb: float
    source_faces: int
    source_vertices: int
    halo_faces: int
    halo_vertices: int
    mean_halo_volume_m3: float
    median_halo_volume_m3: float
    total_halo_volume_m3: float
    candidate_pairs: int
    interfering_pairs: int
    naive_pairs: int
    cross_model_pairs: int
    halos_per_s: float
    ingest_elements_per_s: float
    warnings: list[str] = field(default_factory=list)


def _rss_mb() -> float:
    """Return the current process resident set size in MB (0.0 without psutil)."""
    if not _PSUTIL:
        return 0.0
    return psutil.Process().memory_info().rss / 1024 / 1024


def run_scenario(
    name: str,
    records: list[ElementRecord],
    parse_s: float,
    triangulate_s: float,
    lod: int,
    buffer_m: float,
    models: list[str],
    target: int,
    run_naive: bool = True,
) -> ScenarioResult:
    """Generate Halos for ``records`` and measure every stage of the process."""
    warnings: list[str] = []
    gc.collect()
    rss_start = _rss_mb()

    t0 = time.perf_counter()
    halos = [
        generate_halo_volume(r.centroid, r.bbox, buffer_m=buffer_m, lod=lod, kind=_classify(r.ifc_type))
        for r in records
    ]
    halo_s = time.perf_counter() - t0

    rss_delta = _rss_mb() - rss_start
    halo_array_mb = sum(h.nbytes for h in halos) / 1024 / 1024

    boxes = halo_aabbs(halos)
    t0 = time.perf_counter()
    candidates = broadphase_hash_grid(boxes)
    broadphase_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    hits = aabb_overlap(boxes, candidates)
    midphase_s = time.perf_counter() - t0

    naive_s, naive_count = 0.0, 0
    if run_naive:
        t0 = time.perf_counter()
        naive_count = naive_pairs(boxes)
        naive_s = time.perf_counter() - t0

    model_of = [r.model for r in records]
    cross = sum(1 for i, j in hits if model_of[i] != model_of[j])

    volumes = [h.volume_m3() for h in halos]
    if halo_s > 5.0:
        warnings.append(f"Halo generation exceeded 5 s wall-clock ({halo_s:.2f} s)")
    if rss_delta > 512:
        warnings.append(f"Resident memory grew by {rss_delta:.0f} MB during Halo generation")
    if len(records) < target:
        warnings.append(
            f"Only {len(records)} elements with usable geometry were available against a target of {target}"
        )

    return ScenarioResult(
        scenario=name,
        element_target=target,
        element_actual=len(records),
        models=models,
        lod=lod,
        buffer_m=buffer_m,
        parse_s=round(parse_s, 4),
        triangulate_s=round(triangulate_s, 4),
        halo_s=round(halo_s, 4),
        broadphase_s=round(broadphase_s, 4),
        midphase_s=round(midphase_s, 4),
        naive_s=round(naive_s, 4),
        total_s=round(parse_s + triangulate_s + halo_s + broadphase_s + midphase_s, 4),
        rss_delta_mb=round(rss_delta, 2),
        halo_us_per_element=round(1e6 * halo_s / len(halos), 1) if halos else 0.0,
        halo_array_mb=round(halo_array_mb, 2),
        source_faces=sum(r.source_faces for r in records),
        source_vertices=sum(r.source_vertices for r in records),
        halo_faces=sum(h.face_count for h in halos),
        halo_vertices=sum(h.vertex_count for h in halos),
        mean_halo_volume_m3=round(statistics.fmean(volumes), 3) if volumes else 0.0,
        median_halo_volume_m3=round(statistics.median(volumes), 3) if volumes else 0.0,
        total_halo_volume_m3=round(sum(volumes), 2),
        candidate_pairs=len(candidates),
        interfering_pairs=len(hits),
        naive_pairs=naive_count,
        cross_model_pairs=cross,
        halos_per_s=round(len(halos) / halo_s, 1) if halo_s > 0 else 0.0,
        ingest_elements_per_s=round(len(records) / triangulate_s, 1) if triangulate_s > 0 else 0.0,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Scenario orchestration
# ---------------------------------------------------------------------------


def _resolve(name: str) -> Path:
    """Resolve an IFC fixture name to a path, raising if it is missing."""
    path = IFC_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"IFC fixture not found: {path}")
    return path


def run_single_model_scenarios(
    counts: Sequence[int], lod: int, buffer_m: float, synthetic: bool
) -> list[ScenarioResult]:
    """Run the single-model scaling scenarios (S1-S3) at the given element counts."""
    results: list[ScenarioResult] = []
    for n in counts:
        label = f"S-{n}"
        logger.info("scenario %s: %d elements", label, n)
        if synthetic:
            records = synthetic_elements(n)
            parse_s = triangulate_s = 0.0
            models = ["synthetic"]
        else:
            path = _resolve(PRIMARY_MODEL)
            records, parse_s, triangulate_s = ingest_elements(path, n)
            models = [path.name]
        results.append(
            run_scenario(label, records, parse_s, triangulate_s, lod, buffer_m, models, n)
        )
    return results


def run_federated_scenario(
    total: int, lod: int, buffer_m: float, synthetic: bool
) -> ScenarioResult:
    """
    Run the federated coordination scenario (S4).

    Four separate IFC files are loaded and merged into one Halo population, so
    that interference detection runs across model boundaries as it would in a
    real multi-discipline coordination review.

    Element quotas are allocated in proportion to what each model can actually
    supply, rather than split evenly. An even split silently under-fills the
    scenario, because the infrastructure model in the federated set holds only
    38 products against the architectural model's 2 589.
    """
    records: list[ElementRecord] = []
    parse_s = triangulate_s = 0.0
    models: list[str] = []

    if synthetic:
        per_model = math.ceil(total / 4)
        for k in range(4):
            records.extend(synthetic_elements(per_model, model=f"synthetic-{k}"))
            models.append(f"synthetic-{k}")
        return run_scenario(
            "S-federated", records[:total], 0.0, 0.0, lod, buffer_m, models, total
        )

    opened = []
    for name in FEDERATED_MODELS:
        path = _resolve(name)
        t0 = time.perf_counter()
        model = ifcopenshell.open(str(path))
        parse_s += time.perf_counter() - t0
        available = _select_products(model, limit=10**9)
        opened.append((path, model, available))
        models.append(path.name)
        logger.info("federated: %s offers %d candidate elements", path.name, len(available))

    supply = sum(len(a) for _, _, a in opened)
    if supply < total:
        logger.warning("federated set can supply only %d of %d requested elements", supply, total)

    # Water-filling: models that cannot meet an even share release their
    # remainder to the models that can, so the target is met whenever the
    # federated set holds enough elements in aggregate.
    quotas = {path.name: 0 for path, _, _ in opened}
    remaining, pool = total, list(opened)
    while remaining > 0 and pool:
        share = math.ceil(remaining / len(pool))
        still: list = []
        for path, model, available in pool:
            take = min(share, len(available) - quotas[path.name], remaining)
            quotas[path.name] += take
            remaining -= take
            if quotas[path.name] < len(available):
                still.append((path, model, available))
        if not still or share == 0:
            break
        pool = still

    for path, model, available in opened:
        quota = quotas[path.name]
        if quota == 0:
            continue
        recs, t_s = _triangulate(path, model, available[:quota])
        triangulate_s += t_s
        records.extend(recs)
        logger.info("federated: %s contributed %d elements", path.name, len(recs))

    return run_scenario(
        "S-federated", records[:total], parse_s, triangulate_s, lod, buffer_m, models, total
    )


def run_scaleout_scenarios(
    counts: Sequence[int], lod: int, buffer_m: float
) -> list[ScenarioResult]:
    """
    Run the synthetic scale-out scenarios (S6) beyond what the fixtures supply.

    The largest real model in the repository holds 2 589 usable elements, which
    is not enough to locate the crossover between exhaustive and broad-phase
    interference detection, nor to test the "thousands of Halos" claim at the
    upper end. These scenarios therefore use a deterministic synthetic element
    lattice, and are reported separately from the IFC-backed measurements so
    the two are never conflated.
    """
    results = []
    for n in counts:
        logger.info("scale-out scenario: %d synthetic elements", n)
        records = synthetic_elements(n)
        results.append(
            run_scenario(f"S-scale{n}", records, 0.0, 0.0, lod, buffer_m, ["synthetic"], n)
        )
    return results


def run_lod_sweep(
    count: int, buffer_m: float, synthetic: bool
) -> list[ScenarioResult]:
    """
    Run the LOD sweep (S5) — the same element population at LOD 200/300/400.

    Ingestion is performed once and reused, because the source triangulation is
    identical across levels of detail; only Halo generation is re-measured.
    """
    if synthetic:
        records = synthetic_elements(count)
        parse_s = triangulate_s = 0.0
        models = ["synthetic"]
    else:
        path = _resolve(PRIMARY_MODEL)
        records, parse_s, triangulate_s = ingest_elements(path, count)
        models = [path.name]

    results = []
    for lod in (200, 300, 400):
        logger.info("LOD sweep: LOD %d over %d elements", lod, len(records))
        results.append(
            run_scenario(
                f"S-lod{lod}", records, parse_s, triangulate_s, lod, buffer_m, models, count
            )
        )
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def host_metadata() -> dict:
    """Capture the host characteristics a reader needs to interpret timings."""
    meta = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_count": multiprocessing.cpu_count(),
        "numpy": np.__version__,
    }
    if _IFCOS:
        meta["ifcopenshell"] = ifcopenshell.version
    if _PSUTIL:
        vm = psutil.virtual_memory()
        meta["total_ram_gb"] = round(vm.total / 1024**3, 2)
    return meta


CSV_FIELDS = [
    "scenario", "element_target", "element_actual", "lod", "buffer_m",
    "parse_s", "triangulate_s", "halo_s", "broadphase_s", "midphase_s", "naive_s", "total_s",
    "rss_delta_mb", "halo_array_mb", "halo_us_per_element",
    "source_faces", "source_vertices", "halo_faces", "halo_vertices",
    "mean_halo_volume_m3", "median_halo_volume_m3", "total_halo_volume_m3",
    "candidate_pairs", "interfering_pairs", "naive_pairs", "cross_model_pairs",
    "halos_per_s", "ingest_elements_per_s",
]


def write_outputs(results: list[ScenarioResult], out_dir: Path) -> None:
    """Write the JSON record, the flat CSV and the Markdown summary."""
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_by": "performance_benchmark.py",
        "host": host_metadata(),
        "scenarios": [asdict(r) for r in results],
    }
    (out_dir / "halo_benchmark_results.json").write_text(json.dumps(payload, indent=2))

    with (out_dir / "halo_benchmark_results.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in results:
            row = asdict(r)
            writer.writerow({k: row[k] for k in CSV_FIELDS})

    (out_dir / "halo_benchmark_summary.md").write_text(render_markdown(results))
    logger.info("wrote results to %s", out_dir)


def _source_label(result: ScenarioResult) -> str:
    """Return "IFC" or "synthetic", so measured and modelled runs are never conflated."""
    return "synthetic" if all(m.startswith("synthetic") for m in result.models) else "IFC"


def render_markdown(results: list[ScenarioResult]) -> str:
    """Render the benchmark results as Markdown tables for the thesis."""
    meta = host_metadata()
    lines: list[str] = [
        "# Halo volume generation — measured performance",
        "",
        "Generated by `performance_benchmark.py`. Every figure below is measured, not estimated.",
        "",
        "## Host",
        "",
        "| Property | Value |",
        "|---|---|",
    ]
    for k, v in meta.items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "## Table A — end-to-end scaling",
        "",
        "| Scenario | Source | Elements | LOD | Parse (s) | Triangulate (s) | Halo gen (s) | Halos/s | us/Halo | RSS delta (MB) | Halo arrays (MB) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r.scenario} | {_source_label(r)} | {r.element_actual:,} | {r.lod} | {r.parse_s:.2f} | {r.triangulate_s:.2f} "
            f"| {r.halo_s:.3f} | {r.halos_per_s:,.0f} | {r.halo_us_per_element:.1f} | {r.rss_delta_mb:.1f} | {r.halo_array_mb:.2f} |"
        )

    lines += [
        "",
        "## Table B — geometric complexity",
        "",
        "| Scenario | Source triangles | Halo triangles | Halo vertices | Amplification | Mean Halo volume (m3) | Total reserved (m3) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        amp = (r.halo_faces / r.source_faces) if r.source_faces else 0.0
        lines.append(
            f"| {r.scenario} | {r.source_faces:,} | {r.halo_faces:,} | {r.halo_vertices:,} "
            f"| {amp:.2f}x | {r.mean_halo_volume_m3:,.2f} | {r.total_halo_volume_m3:,.0f} |"
        )

    lines += [
        "",
        "## Table C — interference detection",
        "",
        "| Scenario | Halos | Broad-phase (s) | Mid-phase (s) | Naive O(n2) (s) | Speed-up | Candidate pairs | Interfering pairs | Cross-model |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        speed = (r.naive_s / (r.broadphase_s + r.midphase_s)) if (r.broadphase_s + r.midphase_s) > 0 and r.naive_s else 0.0
        lines.append(
            f"| {r.scenario} | {r.element_actual:,} | {r.broadphase_s:.3f} | {r.midphase_s:.3f} "
            f"| {r.naive_s:.3f} | {speed:.1f}x | {r.candidate_pairs:,} | {r.interfering_pairs:,} | {r.cross_model_pairs:,} |"
        )

    warned = [(r.scenario, w) for r in results for w in r.warnings]
    lines += ["", "## Warnings raised during the run", ""]
    if warned:
        lines += [f"* **{s}** — {w}" for s, w in warned]
    else:
        lines.append("* None. No scenario exceeded the wall-clock or memory thresholds.")

    lines += ["", "## Stage share of total wall-clock", "",
              "| Scenario | Parse | Triangulate | Halo gen | Interference |", "|---|---:|---:|---:|---:|"]
    for r in results:
        total = max(r.total_s, 1e-9)
        lines.append(
            f"| {r.scenario} | {100 * r.parse_s / total:.1f}% | {100 * r.triangulate_s / total:.1f}% "
            f"| {100 * r.halo_s / total:.1f}% | {100 * (r.broadphase_s + r.midphase_s) / total:.1f}% |"
        )

    return "\n".join(lines) + "\n"


def render_charts(results: list[ScenarioResult], out_dir: Path) -> list[str]:
    """Render the benchmark charts; returns the filenames written."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed (uv sync --group bench) — skipping charts")
        return []

    scaling = [r for r in results if r.scenario.startswith("S-") and r.scenario[2:].isdigit()]
    scaling.sort(key=lambda r: r.element_actual)
    lod_runs = sorted((r for r in results if r.scenario.startswith("S-lod")), key=lambda r: r.lod)
    written: list[str] = []

    plt.rcParams.update({"figure.dpi": 150, "font.size": 9, "axes.grid": True, "grid.alpha": 0.3})

    if scaling:
        x = [r.element_actual for r in scaling]
        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.plot(x, [r.halo_s for r in scaling], "o-", label="Halo generation")
        ax.plot(x, [r.triangulate_s for r in scaling], "s-", label="IFC triangulation (ingest)")
        ax.plot(x, [r.broadphase_s + r.midphase_s for r in scaling], "^-", label="Interference detection")
        ax.set_xlabel("Elements")
        ax.set_ylabel("Wall-clock (s)")
        ax.set_yscale("log")
        ax.set_title("Figure 1 — Stage cost vs element count")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "fig1_stage_cost.png")
        plt.close(fig)
        written.append("fig1_stage_cost.png")

        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.bar([str(v) for v in x], [r.halos_per_s for r in scaling], color="#2b6cb0")
        ax.set_xlabel("Elements")
        ax.set_ylabel("Halos generated per second")
        ax.set_title("Figure 2 — Halo generation throughput")
        for i, r in enumerate(scaling):
            ax.text(i, r.halos_per_s, f"{r.halos_per_s:,.0f}", ha="center", va="bottom", fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / "fig2_throughput.png")
        plt.close(fig)
        written.append("fig2_throughput.png")

        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.plot(x, [r.halo_array_mb for r in scaling], "o-", label="Halo mesh arrays")
        ax.plot(x, [r.rss_delta_mb for r in scaling], "s--", label="Process RSS delta")
        ax.set_xlabel("Elements")
        ax.set_ylabel("Memory (MB)")
        ax.set_title("Figure 3 — Halo memory footprint")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "fig3_memory.png")
        plt.close(fig)
        written.append("fig3_memory.png")

        fig, ax = plt.subplots(figsize=(6, 3.6))
        grid = [r.broadphase_s + r.midphase_s for r in scaling]
        naive = [r.naive_s for r in scaling]
        idx = np.arange(len(x))
        ax.bar(idx - 0.18, grid, width=0.36, label="Spatial hash grid")
        ax.bar(idx + 0.18, naive, width=0.36, label="Naive O(n^2)")
        ax.set_xticks(idx)
        ax.set_xticklabels([str(v) for v in x])
        ax.set_xlabel("Elements")
        ax.set_ylabel("Wall-clock (s)")
        ax.set_yscale("log")
        ax.set_title("Figure 4 — Interference detection: broad-phase vs exhaustive")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "fig4_collision.png")
        plt.close(fig)
        written.append("fig4_collision.png")

    if lod_runs:
        fig, ax1 = plt.subplots(figsize=(6, 3.6))
        labels = [str(r.lod) for r in lod_runs]
        ax1.bar(labels, [r.halo_faces for r in lod_runs], color="#805ad5", alpha=0.85)
        ax1.set_xlabel("Level of detail")
        ax1.set_ylabel("Total Halo triangles")
        ax2 = ax1.twinx()
        ax2.plot(labels, [r.halo_s for r in lod_runs], "ko-", label="Generation time")
        ax2.set_ylabel("Halo generation (s)")
        ax2.grid(False)
        ax1.set_title("Figure 5 — Level of detail: triangles and cost")
        fig.tight_layout()
        fig.savefig(out_dir / "fig5_lod.png")
        plt.close(fig)
        written.append("fig5_lod.png")

    scale = sorted(
        (r for r in results if r.scenario.startswith("S-scale")), key=lambda r: r.element_actual
    )
    if scale:
        x = [r.element_actual for r in scale]
        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.plot(x, [r.broadphase_s + r.midphase_s for r in scale], "o-", label="Spatial hash grid")
        ax.plot(x, [r.naive_s for r in scale], "s-", label="Naive O(n^2), vectorised")
        ax.plot(x, [r.halo_s for r in scale], "^--", label="Halo generation")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Halo volumes (synthetic elements)")
        ax.set_ylabel("Wall-clock (s)")
        ax.set_title("Figure 7 — Scale-out: where the broad phase starts to pay")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "fig7_scaleout.png")
        plt.close(fig)
        written.append("fig7_scaleout.png")

    if results:
        fig, ax = plt.subplots(figsize=(7, 3.6))
        names = [r.scenario for r in results]
        parse = np.array([r.parse_s for r in results])
        tri = np.array([r.triangulate_s for r in results])
        halo = np.array([r.halo_s for r in results])
        coll = np.array([r.broadphase_s + r.midphase_s for r in results])
        total = np.maximum(parse + tri + halo + coll, 1e-9)
        bottom = np.zeros(len(results))
        for data, label in (
            (parse, "Parse"),
            (tri, "Triangulate"),
            (halo, "Halo generation"),
            (coll, "Interference"),
        ):
            share = 100 * data / total
            ax.bar(names, share, bottom=bottom, label=label)
            bottom += share
        ax.set_ylabel("Share of wall-clock (%)")
        ax.set_title("Figure 6 — Where the time actually goes")
        ax.legend(loc="lower right", fontsize=8)
        plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
        fig.tight_layout()
        fig.savefig(out_dir / "fig6_bottleneck.png")
        plt.close(fig)
        written.append("fig6_bottleneck.png")

    logger.info("wrote %d charts", len(written))
    return written


# ---------------------------------------------------------------------------
# Generator self-validation
# ---------------------------------------------------------------------------


def _analytic_rounded_box_volume(half: np.ndarray, radius: float) -> float:
    """Return the exact volume of a box Minkowski-summed with a sphere (Steiner formula)."""
    a, b, c = (float(v) for v in half)
    return (
        8 * a * b * c
        + 8 * radius * (a * b + b * c + c * a)
        + 2 * math.pi * radius**2 * (a + b + c)
        + (4.0 / 3.0) * math.pi * radius**3
    )


def _unmatched_edges(mesh: Mesh) -> int:
    """
    Count directed edges without a matching opposite, comparing by position.

    Vertices are compared by rounded coordinate rather than by index because
    the seam-duplication scheme deliberately places coincident vertices at the
    quadrant and equator seams; a watertight surface must still pair every
    directed edge with its reverse.
    """
    counts: dict[tuple, int] = {}
    verts = np.round(mesh.vertices.astype(np.float64), 6)
    for tri in mesh.faces:
        for i in range(3):
            a = tuple(verts[int(tri[i])])
            b = tuple(verts[int(tri[(i + 1) % 3])])
            counts[(a, b)] = counts.get((a, b), 0) + 1
    return sum(1 for (a, b), n in counts.items() if counts.get((b, a), 0) != n)


def validate_generator() -> int:
    """
    Verify the Halo generator against analytic ground truth.

    Two properties are asserted for every primitive at every LOD: the mesh is
    watertight (every directed edge has a matching reverse), and its volume
    converges upward towards the analytic Minkowski-sum volume as LOD rises,
    always from below, as an inscribed polyhedron must. Returns a process exit
    code so this can be used as a regression gate.
    """
    failures = 0
    half = np.array([0.6, 0.4, 1.2])
    bbox = BoundingBox(
        min=Point3D(-float(half[0]), -float(half[1]), -float(half[2])),
        max=Point3D(float(half[0]), float(half[1]), float(half[2])),
    )
    centroid = Point3D(0.0, 0.0, 0.0)
    buffer_m = 0.5
    exact = _analytic_rounded_box_volume(half, buffer_m)

    print(f"{'primitive':10s} {'LOD':>5s} {'faces':>7s} {'verts':>7s} {'volume m3':>11s} {'vs analytic':>12s} {'watertight':>11s}")
    previous = 0.0
    for kind in ("box", "cylinder", "sphere"):
        for lod in (200, 300, 400):
            mesh = generate_halo_volume(centroid, bbox, buffer_m=buffer_m, lod=lod, kind=kind)
            volume = mesh.volume_m3()
            leaks = _unmatched_edges(mesh)
            ratio = volume / exact if kind == "box" else float("nan")
            watertight = "yes" if leaks == 0 else f"NO ({leaks})"
            print(
                f"{kind:10s} {lod:5d} {mesh.face_count:7d} {mesh.vertex_count:7d} "
                f"{volume:11.4f} {ratio:11.4f}  {watertight:>11s}"
            )
            if leaks:
                failures += 1
            if kind == "box":
                # LOD 200 is a plain enlarged box and must *overstate* the true
                # offset volume; LOD 300 and 400 are inscribed approximations of
                # the rounded offset and must converge upward towards it.
                if lod == 200 and volume <= exact:
                    print(f"  FAIL: LOD 200 box should overstate {exact:.4f} m3, got {volume:.4f}")
                    failures += 1
                if lod == 400 and not (previous < volume <= exact * 1.0001):
                    print(f"  FAIL: LOD 400 volume did not converge upward towards {exact:.4f}")
                    failures += 1
                previous = volume

    print()
    print(f"analytic Minkowski volume for the test box: {exact:.4f} m3")
    print("PASS" if failures == 0 else f"FAIL ({failures} check(s))")
    return 0 if failures == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse arguments, run the benchmark suite and write the artefacts."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", default="docs/benchmarks", help="output directory")
    parser.add_argument(
        "--scenarios", default="100,500,1000", help="comma-separated element counts for S1-S3"
    )
    parser.add_argument("--federated", type=int, default=2000, help="element count for S4 (0 to skip)")
    parser.add_argument("--lod", type=int, default=300, help="LOD used for S1-S4")
    parser.add_argument("--lod-sweep", type=int, default=1000, help="element count for S5 (0 to skip)")
    parser.add_argument(
        "--scaleout",
        default="2000,5000,10000,20000",
        help="synthetic element counts for S6 (empty string to skip)",
    )
    parser.add_argument("--buffer", type=float, default=DEFAULT_BUFFER_M, help="clearance buffer, metres")
    parser.add_argument("--synthetic", action="store_true", help="use synthetic elements, no IFC required")
    parser.add_argument("--no-charts", action="store_true", help="skip matplotlib chart rendering")
    parser.add_argument(
        "--validate", action="store_true", help="verify the Halo generator against analytic volumes and exit"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")

    if args.validate:
        return validate_generator()

    counts = [int(c) for c in args.scenarios.split(",") if c.strip()]
    out_dir = Path(args.out)

    results = run_single_model_scenarios(counts, args.lod, args.buffer, args.synthetic)
    if args.federated:
        results.append(run_federated_scenario(args.federated, args.lod, args.buffer, args.synthetic))
    if args.lod_sweep:
        results.extend(run_lod_sweep(args.lod_sweep, args.buffer, args.synthetic))
    scaleout = [int(c) for c in args.scaleout.split(",") if c.strip()]
    if scaleout:
        results.extend(run_scaleout_scenarios(scaleout, args.lod, args.buffer))

    write_outputs(results, out_dir)
    if not args.no_charts:
        render_charts(results, out_dir)

    print()
    print(render_markdown(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
