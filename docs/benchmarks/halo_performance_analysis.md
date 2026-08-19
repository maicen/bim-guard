# Halo spatial reservation — performance characterisation and bottleneck analysis

**The question this answers.** At examination it was noted that the report "would benefit from
more detail on how the geometric engine will handle high-poly IFC geometry when generating
thousands of 'Halo' volumes simultaneously." That is a question about cost, and the only
defensible answer is a measured one. This document reports what `performance_benchmark.py`
measures, what it does not, and where the real constraint turns out to lie — which is not where
the claim implies.

**Scope and honesty note.** The Halo generator benchmarked here is a **standalone prototype**. It
is not imported by any route or module in the live application, and generating clearance volumes
is not part of any user-facing workflow today. What follows characterises the cost of a capability
that has now been built and measured, not one that is in production. The generator reuses the
project's own `Point3D`/`BoundingBox` primitives from `piping_schema.py` and the same
`ifcopenshell.geom` ingestion path the live pipeline uses, so the ingestion figures transfer
directly to the platform as it stands; the Halo figures characterise the prototype.

**Reproduce with:**

```bash
uv sync --group bench
uv run python performance_benchmark.py --validate    # generator correctness
uv run python performance_benchmark.py               # full suite -> docs/benchmarks/
```

---

## 1. What a Halo is, computationally

A Halo is the clearance volume that must remain unobstructed around an element — for BIMGuard's
purposes, the 500 mm seismic-bracing and maintenance access allowance of the kind clause 2.4.3 in
the SS316 case study demands. Geometrically it is a **Minkowski sum**: the element's solid, swollen
by a sphere of the buffer radius.

The prototype approximates that sum from the element's axis-aligned bounding box using one of
three primitives, selected by IFC class:

| Source class | Primitive | Rationale |
|---|---|---|
| `IfcPipeSegment`, `IfcDuctSegment`, cable segments/carriers | Cylinder about the dominant bbox axis | Clearance around a linear run is a sleeve |
| Fittings, valves, junctions, terminals, flanges, accessories | Sphere | Point-like components need omnidirectional access |
| Everything else (walls, slabs, columns, beams, proxies) | Rounded box (exact box ⊕ sphere) | Prismatic elements need an offset prism with filleted edges |

**The decisive design property is in that first column: the Halo is generated from the element's
bounding box, not from its triangulation.** Halo cost is therefore O(1) in the source element's
polygon count. A 40 000-triangle imported valve and a 12-triangle extruded pipe produce identically
priced Halos. This is what makes the high-poly concern tractable: the source model's polygon count
is paid exactly once, during ingestion, and never again per Halo.

### 1.1 Generator correctness

Performance figures are worthless if the geometry is wrong, so the generator is verified before it
is timed. `--validate` asserts two properties for every primitive at every LOD:

| Primitive | LOD | Faces | Vertices | Volume (m³) | vs. analytic | Watertight |
|---|---:|---:|---:|---:|---:|---|
| box | 200 | 12 | 8 | 13.4640 | **1.1180** | yes |
| box | 300 | 112 | 74 | 11.5776 | 0.9613 | yes |
| box | 400 | 336 | 202 | 11.9224 | 0.9900 | yes |
| cylinder | 200 / 300 / 400 | 32 / 64 / 128 | 18 / 34 / 66 | 11.64 / 12.59 / 12.84 | — | yes |
| sphere | 200 / 300 / 400 | 48 / 224 / 960 | 26 / 114 / 482 | 22.08 / 26.93 / 28.27 | — | yes |

*Test element: 1.2 × 0.8 × 2.4 m box, 0.5 m buffer. Analytic ground truth is the Steiner formula
for a box Minkowski-summed with a sphere, 12.0434 m³. Watertightness is tested by matching every
directed edge against its reverse by vertex position, not index, because the generator
deliberately duplicates vertices at seams.*

Two results in that table matter for clearance work:

* **LOD 200 overstates the reserved volume by 11.8%.** A naively enlarged box has square corners
  where the true offset surface is filleted. At LOD 200 that error is systematically
  *conservative* — the volume is too large, so a clash is reported where none exists. That is the
  right direction for a coarse first pass, but it is not free: on a dense MEP model an 11.8%
  over-reservation is a meaningful source of false positives.
* **LOD 300 and 400 converge upward towards the analytic volume from below** (0.9613, 0.9900), as
  inscribed polyhedral approximations must. LOD 400 is within 1% of exact.

---

## 2. Measured results

Host: 4-core x86-64 Linux VM, 15.7 GB RAM, Python 3.12.3, IfcOpenShell 0.8.5, NumPy 2.4.6. Source
models are the repository's own IFC fixtures; `BUILDING_R4.ifc` (IFC4, 2 602 products, 2 589 with
geometry) supplies the single-model scenarios.

### Table A — end-to-end scaling

| Scenario | Source | Elements | LOD | Parse (s) | Triangulate (s) | Halo gen (s) | Halos/s | µs/Halo | RSS Δ (MB) | Halo arrays (MB) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S-100 | IFC | 100 | 300 | 1.92 | 1.78 | 0.041 | 2,452 | 407.7 | 0.5 | 0.21 |
| S-500 | IFC | 500 | 300 | 1.61 | 14.21 | 0.208 | 2,399 | 416.9 | 0.0 | 1.06 |
| S-1000 | IFC | 1,000 | 300 | 1.50 | 28.96 | 0.384 | 2,605 | 383.9 | 0.0 | 2.13 |
| S-federated | IFC ×4 | 1,999 | 300 | 9.87 | 51.88 | 0.784 | 2,548 | 392.4 | 0.5 | 4.23 |
| S-lod200 | IFC | 1,000 | 200 | 1.50 | 29.80 | 0.022 | 44,964 | 22.2 | 0.0 | 0.23 |
| S-lod300 | IFC | 1,000 | 300 | 1.50 | 29.80 | 0.369 | 2,711 | 368.8 | 0.0 | 2.13 |
| S-lod400 | IFC | 1,000 | 400 | 1.50 | 29.80 | 0.497 | 2,014 | 496.6 | 0.0 | 6.16 |
| S-scale2000 | synthetic | 2,000 | 300 | — | — | 0.513 | 3,902 | 256.3 | 0.0 | 4.15 |
| S-scale5000 | synthetic | 5,000 | 300 | — | — | 1.281 | 3,904 | 256.1 | 0.0 | 10.37 |
| S-scale10000 | synthetic | 10,000 | 300 | — | — | 2.523 | 3,964 | 252.3 | 0.0 | 20.74 |
| S-scale20000 | synthetic | 20,000 | 300 | — | — | 5.089 | 3,930 | 254.5 | 0.1 | 41.47 |

The federated scenario loads four genuinely distinct IFC files (architectural, institutional,
residential and infrastructure-plumbing), allocating element quotas in proportion to what each
model can supply, and runs interference detection across model boundaries.

### Table B — geometric complexity

| Scenario | Source triangles | Halo triangles | Amplification | Mean Halo volume (m³) | Total reserved (m³) |
|---|---:|---:|---:|---:|---:|
| S-100 | 20,720 | 11,200 | 0.54× | 21.47 | 2,147 |
| S-500 | 248,504 | 56,000 | 0.23× | 15.03 | 7,516 |
| S-1000 | 533,320 | 112,000 | **0.21×** | 14.23 | 14,231 |
| S-federated | 737,661 | 222,672 | 0.30× | 49.45 | 98,857 |
| S-lod200 | 533,320 | 12,000 | 0.02× | 16.22 | 16,224 |
| S-lod400 | 533,320 | 336,000 | 0.63× | 14.60 | 14,597 |

**The amplification column is the direct answer to the examiner's question.** Generating a Halo
for every element in a 533 000-triangle model adds 112 000 triangles — the Halo layer is roughly
one fifth the size of the geometry it wraps, and at LOD 200 one fiftieth. Halos do not multiply
high-poly geometry; they *replace* it with a small, uniform-cost proxy. The amplification factor
falls as models get more detailed, because source triangle counts scale with authoring detail
while Halo triangle counts are fixed per element by LOD alone.

### Table C — interference detection

| Scenario | Halos | Broad-phase (s) | Mid-phase (s) | Naive O(n²) (s) | Speed-up | Candidate pairs | Interfering pairs | Cross-model |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S-100 | 100 | 0.010 | 0.001 | 0.002 | 0.2× | 544 | 259 | 0 |
| S-500 | 500 | 0.018 | 0.012 | 0.013 | 0.4× | 12,768 | 4,569 | 0 |
| S-1000 | 1,000 | 0.044 | 0.041 | 0.056 | 0.7× | 46,518 | 13,102 | 0 |
| S-federated | 1,999 | 0.095 | 0.070 | 0.119 | 0.7× | 81,609 | 27,434 | **3,916** |
| S-scale2000 | 2,000 | 0.027 | 0.012 | 0.121 | **3.1×** | 25,736 | 1,875 | 0 |
| S-scale5000 | 5,000 | 0.090 | 0.047 | 0.610 | 4.5× | 71,835 | 5,071 | 0 |
| S-scale10000 | 10,000 | 0.236 | 0.097 | 2.409 | 7.2× | 150,203 | 11,041 | 0 |
| S-scale20000 | 20,000 | 0.690 | 0.266 | 9.494 | **9.9×** | 304,805 | 22,869 | 0 |

---

## 3. Bottleneck analysis

### 3.1 Where the time actually goes

| Scenario | Parse | Triangulate | Halo generation | Interference |
|---|---:|---:|---:|---:|
| S-100 | 51.2% | 47.5% | 1.1% | 0.3% |
| S-1000 | 4.9% | **93.6%** | 1.2% | 0.3% |
| S-federated | 15.7% | **82.7%** | 1.3% | 0.3% |

**Halo generation is not the bottleneck, and is not close to being the bottleneck.** On the
1 000-element scenario it accounts for 1.2% of wall-clock. IFC triangulation accounts for 93.6%.
The 2 000-element federated coordination run completes in 62.7 s end-to-end, of which 0.78 s is
Halo generation.

This inverts the premise of the original concern. The risk in "generating thousands of Halo
volumes simultaneously" is not the Halos. It is that you must first read thousands of high-poly
elements out of IFC, and *that* is a cost the platform already pays today for every compliance
check, Halos or not.

### 3.2 The three regimes

1. **Ingestion-bound (any IFC-backed run).** `ifcopenshell.geom.iterator` triangulates ~34.5
   elements/s on 4 cores against `BUILDING_R4.ifc`. This is the constraint on every figure in
   Table A that has a Triangulate column.
2. **Generation-bound (cached ingestion).** Halo generation is strictly linear: 254 µs/element at
   LOD 300, flat from 2 000 to 20 000 elements (3,902 → 3,930 Halos/s, a 0.7% spread across a 10×
   range). Throughput is *higher* on synthetic elements than on IFC ones (3,900 vs. 2,600/s)
   because the synthetic mix contains more pipes and fittings, whose cylinder and sphere
   primitives are cheaper than the rounded box that architectural elements receive.
3. **Interference-bound (very large populations).** Only past ~20 000 volumes does pair-finding
   approach the cost of generation.

### 3.3 The broad-phase crossover — a negative result worth reporting

At the scales the real fixtures supply, **the uniform spatial hash grid is slower than exhaustive
pair testing** (0.2×–0.7× in Table C). This is not a defect in the grid; it is a consequence of
comparing a pure-Python O(n) algorithm against a NumPy-vectorised O(n²) one. Below roughly 1 500
volumes, the vectorised exhaustive test wins on constant factors alone.

The crossover sits between 1 000 and 2 000 volumes, after which the asymptotics assert themselves:
3.1× at 2 000, 7.2× at 10 000, 9.9× at 20 000. The practical recommendation is therefore a
**hybrid**: exhaustive vectorised AABB testing below ~2 000 Halos, hash-grid broad-phase above it.
Choosing the grid unconditionally would make small coordination runs measurably slower, and this
is only visible because both were measured rather than one being assumed.

### 3.4 Memory is not a constraint

Halo meshes are stored as float32 vertices and int32 faces, giving 2.13 MB per 1 000 Halos at
LOD 300 — 41.5 MB at 20 000. Process RSS growth during generation was at or below 0.5 MB in every
IFC scenario, because the source triangulations are discarded as they are consumed: only the
bounding box and centroid are retained per element, roughly 100 bytes against the tens of
kilobytes a high-poly mesh occupies. **Peak memory tracks element count, not source polygon
count** — the second half of the answer to the high-poly question.

### 3.5 Level of detail is the main cost lever

| LOD | Triangles per box Halo | Time per 1 000 Halos | Volume error vs. exact |
|---:|---:|---:|---:|
| 200 | 12 | 0.022 s | +11.8% (over-reserves) |
| 300 | 112 | 0.369 s | −3.9% |
| 400 | 336 | 0.497 s | −1.0% |

LOD 200 is **17× faster** than LOD 300 and produces a ninth of the triangles, at the cost of
systematically over-reserving space. This maps cleanly onto a two-pass strategy: LOD 200 for a
whole-model first pass, LOD 400 only on the elements that first pass flags. On the 1 000-element
model that is 0.022 s plus a rounding error, instead of 0.497 s.

---

## 4. Extrapolation to "thousands of Halo volumes"

Taking the measured per-element costs and holding hardware constant:

| Halo volumes | Generation, LOD 300 | Generation, LOD 200 | Interference (grid) | Halo memory | Cold ingestion (measured rate) |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.38 s | 0.02 s | 0.09 s | 2.1 MB | ~29 s |
| 5,000 | 1.28 s | 0.08 s | 0.14 s | 10.4 MB | ~145 s |
| 10,000 | 2.52 s | 0.15 s | 0.33 s | 20.7 MB | ~290 s |
| 20,000 | 5.09 s | 0.31 s | 0.96 s | 41.5 MB | ~580 s |
| 50,000 | ~12.7 s (linear) | ~0.8 s | ~2.5 s | ~104 MB | ~24 min |

*Generation, interference and memory figures at and below 20 000 are measured; the 50 000 row is a
linear extrapolation, justified by the flat per-element cost across the measured decade. Ingestion
figures are extrapolated from the measured 34.5 elements/s and are the least reliable column here,
since triangulation cost varies with per-element geometric complexity, not just element count.*

**Verdict on the claim.** Generating tens of thousands of Halo volumes is comfortably tractable:
20 000 volumes in 5.1 s and 41.5 MB, with interference detection in under a second. The claim
survives the scrutiny. What does *not* survive is the implicit assumption that generation is the
hard part — at 10 000 elements, a cold run spends ~290 s in IFC triangulation and 2.5 s making
Halos, a ratio of roughly 115:1.

---

## 5. What to build, in priority order

1. **Cache the ingestion, not the meshes.** Halo generation needs only `(guid, centroid, bbox,
   ifc_type)` — about 100 bytes per element. Persisting that per model version turns every run
   after the first from ~290 s into ~2.5 s for 10 000 elements. This is the single highest-value
   optimisation available, it removes 93% of the wall-clock, and it needs no new geometry code.
2. **Re-triangulate only changed GUIDs between model drops.** In the weekly coordination cycle the
   inter-drop delta is a small fraction of the model, so incremental ingestion compounds with (1).
3. **Adopt the hybrid interference strategy** of §3.3 with the crossover at ~2 000 volumes, rather
   than committing to either algorithm unconditionally.
4. **Default to LOD 200 for the first pass**, escalating to LOD 400 only on flagged elements, and
   document the +11.8% conservative bias so users understand why the coarse pass over-reports.
5. **Add exact narrow-phase testing.** The current mid-phase is an AABB overlap test, which is
   conservative: it reports overlapping bounding boxes, not overlapping volumes. Separating-axis
   or triangle-intersection testing on the pairs that survive the mid-phase would eliminate the
   remaining false positives, and would run on a small fraction of pairs.
6. **Only then consider a different geometry backend.** The main report lists evaluating `trimesh`
   for Halo work as a possible future addition. On this evidence that is premature: the current
   `ifcopenshell.geom` + NumPy stack generates 3 900 watertight Halos/s and the bottleneck is
   elsewhere entirely. `trimesh` would earn its place for exact boolean narrow-phase work
   (item 5), not for generation.

---

## 6. Threats to validity

Stated plainly, because these bound how far the figures above can be pushed.

1. **Single-run measurements.** Each scenario was run once; no repetitions, no variance or
   confidence intervals. Sub-second figures in particular should be read as indicative. Repeating
   each scenario 5–10 times and reporting medians is the obvious next step.
2. **One host, four cores.** Triangulation is the parallel stage and uses `cpu_count()`, so the
   ingestion figures should improve close to linearly with core count — untested here.
3. **The source models are architectural, not MEP-dense.** `BUILDING_R4.ifc` is walls, columns,
   windows and slabs, so most Halos took the rounded-box path. A real plant room dominated by pipe
   segments and fittings would be *faster* per element (cylinders and spheres are cheaper) but
   spatially far denser, which raises the candidate-pair count.
4. **Synthetic elements sit on a uniform lattice.** Real buildings are spatially clustered, which
   degrades uniform-grid performance relative to the S-scale figures. The crossover point of
   §3.3 should be re-measured on a genuinely large real model before being treated as settled.
5. **AABB mid-phase, not exact intersection.** Interfering-pair counts in Table C are upper
   bounds.
6. **Bounding-box Halos are an approximation of the Minkowski sum of the true solid.** For a
   diagonal brace or a swept bend, the bbox-derived Halo over-reserves — correct in direction for
   a clearance check, but a source of false positives that a swept-solid Halo would avoid.
7. **The 2 000-element federated set is four architectural models, not a real multi-discipline
   federation.** It exercises the cross-model code path (3 916 cross-model interfering pairs) but
   is not a substitute for validating on a real coordinated data-centre or hospital model.

---

## 7. Figures

| File | Content |
|---|---|
| `fig1_stage_cost.png` | Stage cost vs. element count (log scale) — the separation between triangulation and Halo generation |
| `fig2_throughput.png` | Halo generation throughput by element count |
| `fig3_memory.png` | Halo array footprint and process RSS delta |
| `fig4_collision.png` | Grid vs. exhaustive interference detection on IFC-backed runs |
| `fig5_lod.png` | Triangle count and generation cost by LOD |
| `fig6_bottleneck.png` | Stage share of wall-clock across every scenario |
| `fig7_scaleout.png` | Scale-out to 20 000 volumes and the broad-phase crossover |

Raw data: `halo_benchmark_results.json` (with host metadata), `halo_benchmark_results.csv`,
`halo_benchmark_summary.md`.
