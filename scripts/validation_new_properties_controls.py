#!/usr/bin/env python
"""Controlled accuracy cases for the four newly-added compliance properties:
StepFormula (stair riser+going stride formula), HandrailExtensionTop/Bottom,
DoorClearOpeningWidth, and EgressWindowClearOpening/MaxSillHeight.

Same shape as ``validation_mm001_controls.py``: each case has a KNOWN,
hand-computed expected value (either pure arithmetic, or built from a small
synthetic IFC model whose dimensions are chosen by this script, not measured
from anywhere), and the engine's actual output is compared against it. A
mesh-derived case (HandrailExtension) allows a small numeric tolerance for
tessellation/floating-point noise; every pure-arithmetic case (StepFormula,
DoorClearOpeningWidth, EgressWindowClearOpening) must match exactly, since
there is no geometry noise to allow for.

"Accuracy %" per property is 100% minus the mean relative error across that
property's cases (clamped at 0%), matching how close the engine's computed
value came to the known-correct one -- not a pass/fail rate, since these are
continuous measurements, not classification calls. A property whose cases
are all exact arithmetic will show 100.0%; the mesh-derived one shows
whatever small deviation tessellation actually introduces.

Usage::

    uv run python scripts/validation_new_properties_controls.py
    uv run python scripts/validation_new_properties_controls.py --json docs/validation/data/new-properties-accuracy.json
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402

from app.modules.ifc_reader import ifc_stair as st  # noqa: E402
from app.modules.ifc_reader.ifc_spatial import compute_egress_clear_opening  # noqa: E402

Case = dict[str, Any]


# ── StepFormula: pure arithmetic, no IFC needed ───────────────────────────────


def _step_formula_cases() -> list[Case]:
    cases: list[Case] = []

    # Uniform stair: 4 treads, riser=175mm, going=280mm -> every step's
    # 2*riser+going is exactly 630mm.
    bands = [
        {"z_mean": i * 175.0, "run_min": i * 280.0, "run_max": i * 280.0 + 280.0}
        for i in range(4)
    ]
    steps = st.derive_flight_steps(bands)
    for i, actual in enumerate(steps["step_formula_mm"]):
        cases.append({
            "property": "StepFormula", "case": f"uniform-step-{i}",
            "expected": 630.0, "actual": actual, "tolerance": 0.05, "unit": "mm",
        })

    # Non-uniform: riser grows 175->200 while going shrinks 300->260 -- the
    # per-step values (650, 660) must not be confused with the flight's own
    # extremes (2*200+300=700, which never occurs on this flight).
    bands2 = [
        {"z_mean": 0.0, "run_min": 0.0, "run_max": 300.0},
        {"z_mean": 175.0, "run_min": 300.0, "run_max": 560.0},
        {"z_mean": 375.0, "run_min": 560.0, "run_max": 820.0},
    ]
    steps2 = st.derive_flight_steps(bands2)
    for i, (expected, actual) in enumerate(zip([650.0, 660.0], steps2["step_formula_mm"])):
        cases.append({
            "property": "StepFormula", "case": f"nonuniform-step-{i}",
            "expected": expected, "actual": actual, "tolerance": 0.05, "unit": "mm",
        })

    return cases


# ── EgressWindowClearOpening: pure arithmetic, no IFC needed ─────────────────


def _egress_window_cases() -> list[Case]:
    cases: list[Case] = []
    specs = [
        # (operation_type, width_mm, height_mm, expected_w, expected_h, expected_area_m2)
        ("SIDEHUNGLEFTHAND", 900.0, 1200.0, 810.0, 1080.0, 0.8748),
        ("SLIDINGVERTICAL", 900.0, 1200.0, 810.0, 552.0, 0.44712),
        ("SLIDINGHORIZONTAL", 1500.0, 1000.0, 720.0, 900.0, 0.648),
        ("FIXEDCASEMENT", 900.0, 1200.0, 0.0, 0.0, 0.0),
    ]
    for op, w, h, exp_w, exp_h, exp_area in specs:
        result = compute_egress_clear_opening(op, w, h)
        cases.append({
            "property": "EgressWindowClearOpening", "case": f"{op}-width",
            "expected": exp_w, "actual": result["clear_width_mm"], "tolerance": 0.05, "unit": "mm",
        })
        cases.append({
            "property": "EgressWindowClearOpening", "case": f"{op}-height",
            "expected": exp_h, "actual": result["clear_height_mm"], "tolerance": 0.05, "unit": "mm",
        })
        cases.append({
            "property": "EgressWindowClearOpening", "case": f"{op}-area",
            "expected": exp_area, "actual": result["clear_area_m2"], "tolerance": 0.0005, "unit": "m2",
        })
    return cases


# ── DoorClearOpeningWidth: real ifcopenshell IfcDoor, exact arithmetic ───────


def _build_door(overall_width_mm, *, panel_width=None, number_of_panels=None):
    import ifcopenshell
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    run("root.create_entity", model, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS"})
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="B")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L1")
    run("aggregate.assign_object", model, products=[site], relating_object=model.by_type("IfcProject")[0])
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)

    door = run("root.create_entity", model, ifc_class="IfcDoor", name="D1")
    door.OverallWidth = overall_width_mm
    door.OverallHeight = 2100.0
    run("spatial.assign_container", model, products=[door], relating_structure=storey)

    if panel_width is not None:
        pset = run("pset.add_pset", model, product=door, name="Pset_DoorPanelProperties")
        run("pset.edit_pset", model, pset=pset, properties={"PanelWidth": panel_width})
    if number_of_panels is not None:
        pset = run("pset.add_pset", model, product=door, name="Pset_DoorCommon")
        run("pset.edit_pset", model, pset=pset, properties={"NumberOfPanels": number_of_panels})

    return model, door


def _resolve_property(model, target_class, property_name, tmp_dir, name) -> Any:
    from app.modules.ifc_reader import IFCReader
    from app.modules.comparator import ComplianceComparator

    path = tmp_dir / f"{name}.ifc"
    model.write(str(path))
    rule = {
        "rule_id": 1, "reference": "PROBE", "target_ifc_class": target_class,
        "property_name": property_name, "operator": "exists",
    }
    extraction = IFCReader(path).extract_for_compliance([rule])
    results = ComplianceComparator().validate_metadata(extraction)
    result = {r["rule_ref"]: r for r in results}["PROBE"]
    return result["all_elements"][0]["actual"]


def _door_clear_opening_cases(tmp_dir: Path) -> list[Case]:
    from app.modules.ifc_reader import DEFAULT_DOOR_STOP_DEDUCTION_MM

    cases: list[Case] = []
    specs = [
        ("single-leaf", dict(overall_width_mm=900.0), 900.0 - DEFAULT_DOOR_STOP_DEDUCTION_MM),
        ("declared-panel-width", dict(overall_width_mm=900.0, panel_width=0.6),
         900.0 * 0.6 - DEFAULT_DOOR_STOP_DEDUCTION_MM),
        ("two-leaf-even-split", dict(overall_width_mm=900.0, number_of_panels=2),
         900.0 * 0.5 - DEFAULT_DOOR_STOP_DEDUCTION_MM),
        ("narrow-leaf-clips-to-zero", dict(overall_width_mm=30.0), 0.0),
    ]
    for name, kwargs, expected in specs:
        model, _door = _build_door(**kwargs)
        actual = _resolve_property(model, "IfcDoor", "DoorClearOpeningWidth", tmp_dir, name)
        cases.append({
            "property": "DoorClearOpeningWidth", "case": name,
            "expected": expected, "actual": actual, "tolerance": 0.05, "unit": "mm",
        })
    return cases


# ── HandrailExtensionTop/Bottom: real ifcopenshell mesh, small tolerance ────

RISER_MM, GOING_MM, WIDTH_MM, N_TREADS = 175.0, 280.0, 800.0, 6


def _tread_quad_triangles(x0, x1, y0, y1, z):
    return [
        [(x0, y0, z), (x1, y0, z), (x1, y1, z)],
        [(x0, y0, z), (x1, y1, z), (x0, y1, z)],
    ]


def _riser_quad_triangles(x, z0, z1, y0, y1):
    return [
        [(x, y0, z0), (x, y1, z0), (x, y1, z1)],
        [(x, y0, z0), (x, y1, z1), (x, y0, z1)],
    ]


def _box_triangles(x0, x1, y0, y1, z0, z1):
    corners = {
        (0, 0, 0): (x0, y0, z0), (1, 0, 0): (x1, y0, z0),
        (1, 1, 0): (x1, y1, z0), (0, 1, 0): (x0, y1, z0),
        (0, 0, 1): (x0, y0, z1), (1, 0, 1): (x1, y0, z1),
        (1, 1, 1): (x1, y1, z1), (0, 1, 1): (x0, y1, z1),
    }
    faces = [
        [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],
        [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
        [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
        [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],
        [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],
        [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
    ]
    triangles = []
    for quad in faces:
        a, b, c, d = (corners[k] for k in quad)
        triangles.append([a, b, c])
        triangles.append([a, c, d])
    return triangles


def _tessellated_representation(model, body, triangles):
    coord_list, coord_index = [], []
    for tri in triangles:
        base = len(coord_list)
        coord_list.extend(tri)
        coord_index.append((base + 1, base + 2, base + 3))
    points = model.create_entity("IfcCartesianPointList3D", CoordList=coord_list)
    mesh = model.create_entity("IfcTriangulatedFaceSet", Coordinates=points, CoordIndex=coord_index)
    return model.create_entity(
        "IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body",
        RepresentationType="Tessellation", Items=[mesh],
    )


def _build_flight_with_extended_handrail(bottom_extension_mm: float, top_extension_mm: float):
    import ifcopenshell
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    run("root.create_entity", model, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS"})
    ctx = run("context.add_context", model, context_type="Model")
    body = run(
        "context.add_context", model, context_type="Model",
        context_identifier="Body", target_view="MODEL_VIEW", parent=ctx,
    )
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="B")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L1")
    run("aggregate.assign_object", model, products=[site], relating_object=model.by_type("IfcProject")[0])
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)

    triangles = []
    for i in range(N_TREADS):
        z = (i + 1) * RISER_MM
        x0, x1 = i * GOING_MM, i * GOING_MM + GOING_MM
        triangles += _tread_quad_triangles(x0, x1, 0.0, WIDTH_MM, z)
        triangles += _riser_quad_triangles(x0, z - RISER_MM, z, 0.0, WIDTH_MM)
    rep = _tessellated_representation(model, body, triangles)
    flight = run("root.create_entity", model, ifc_class="IfcStairFlight", name="Flight")
    run("spatial.assign_container", model, products=[flight], relating_structure=storey)
    run("geometry.assign_representation", model, product=flight, representation=rep)
    run("geometry.edit_object_placement", model, product=flight, matrix=np.eye(4), is_si=False)

    flight_top_nosing_x = (N_TREADS - 1) * GOING_MM
    rail_x0 = -bottom_extension_mm
    rail_x1 = flight_top_nosing_x + top_extension_mm
    rail_triangles = _box_triangles(rail_x0, rail_x1, WIDTH_MM, WIDTH_MM + 40.0, 880.0, 920.0)
    rail_rep = _tessellated_representation(model, body, rail_triangles)
    railing = run(
        "root.create_entity", model, ifc_class="IfcRailing", name="Handrail",
        predefined_type="HANDRAIL",
    )
    run("spatial.assign_container", model, products=[railing], relating_structure=storey)
    run("geometry.assign_representation", model, product=railing, representation=rail_rep)
    run("geometry.edit_object_placement", model, product=railing, matrix=np.eye(4), is_si=False)

    from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

    engine = st.IFCStairEngine(model, IFCGeometryExtractor(model)).build()
    return engine.get_railing(railing.GlobalId)


def _handrail_extension_cases() -> list[Case]:
    cases: list[Case] = []
    specs = [
        ("overhang-both-ends", 300.0, 450.0),
        ("flush-both-ends", 0.0, 0.0),
        ("short-both-ends", -200.0, -150.0),
    ]
    for name, bottom_ext, top_ext in specs:
        railing = _build_flight_with_extended_handrail(bottom_ext, top_ext)
        cases.append({
            "property": "HandrailExtension", "case": f"{name}-bottom",
            "expected": bottom_ext, "actual": railing.get("extension_bottom_mm"),
            "tolerance": 10.0, "unit": "mm",
        })
        cases.append({
            "property": "HandrailExtension", "case": f"{name}-top",
            "expected": top_ext, "actual": railing.get("extension_top_mm"),
            "tolerance": 10.0, "unit": "mm",
        })
    return cases


# ── Scoring and report ────────────────────────────────────────────────────────


def _score(cases: list[Case]) -> list[Case]:
    for c in cases:
        expected, actual, tol = c["expected"], c["actual"], c["tolerance"]
        if actual is None:
            c["error"] = None
            c["within_tolerance"] = False
            c["accuracy_pct"] = 0.0
            continue
        abs_error = abs(actual - expected)
        c["error"] = round(abs_error, 4)
        c["within_tolerance"] = abs_error <= tol
        # Relative-error-based accuracy, not a bare pass/fail, since these
        # are continuous measurements: a value 1% off is not equally wrong
        # as one 50% off, even if both happen to exceed a chosen tolerance.
        denom = abs(expected) if abs(expected) > 1e-9 else max(abs(actual), 1.0)
        relative_error = abs_error / denom
        c["accuracy_pct"] = round(max(0.0, 1.0 - relative_error) * 100.0, 3)
    return cases


def run(tmp_dir: Path) -> list[Case]:
    cases = (
        _step_formula_cases()
        + _egress_window_cases()
        + _door_clear_opening_cases(tmp_dir)
        + _handrail_extension_cases()
    )
    return _score(cases)


def print_report(cases: list[Case]) -> dict[str, float]:
    print("=" * 100)
    print("NEW PROPERTY ACCURACY CONTROLS")
    print("=" * 100)
    header = f"{'property':<26}{'case':<28}{'expected':>12}{'actual':>12}{'error':>10}{'accuracy':>10}"
    print(header)
    print("-" * len(header))
    by_property: dict[str, list[Case]] = {}
    for c in cases:
        by_property.setdefault(c["property"], []).append(c)
        expected = f"{c['expected']:.3f}" if isinstance(c["expected"], float) else str(c["expected"])
        actual = "MISSING" if c["actual"] is None else (
            f"{c['actual']:.3f}" if isinstance(c["actual"], float) else str(c["actual"])
        )
        error = "-" if c["error"] is None else f"{c['error']:.3f}"
        mark = "" if c["within_tolerance"] else "  <-- OUT OF TOLERANCE"
        print(f"{c['property']:<26}{c['case']:<28}{expected:>12}{actual:>12}{error:>10}{c['accuracy_pct']:>9.1f}%{mark}")

    print("-" * len(header))
    summary: dict[str, float] = {}
    for prop, prop_cases in by_property.items():
        mean_accuracy = sum(c["accuracy_pct"] for c in prop_cases) / len(prop_cases)
        summary[prop] = round(mean_accuracy, 2)
        n_within = sum(1 for c in prop_cases if c["within_tolerance"])
        print(f"{prop}: {mean_accuracy:.2f}% accuracy ({n_within}/{len(prop_cases)} cases within tolerance)")

    overall = sum(c["accuracy_pct"] for c in cases) / len(cases)
    print(f"\nOverall: {overall:.2f}% accuracy across {len(cases)} controlled cases")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", type=Path, default=None, help="Also write the record as JSON")
    args = parser.parse_args(argv)

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        cases = run(Path(tmp))

    summary = print_report(cases)
    failures = sum(1 for c in cases if not c["within_tolerance"])

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "cases_total": len(cases),
                    "cases_within_tolerance": len(cases) - failures,
                    "cases_out_of_tolerance": failures,
                    "accuracy_by_property_pct": summary,
                    "overall_accuracy_pct": round(sum(c["accuracy_pct"] for c in cases) / len(cases), 2),
                    "cases": cases,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nWrote {args.json}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
