#!/usr/bin/env python
"""Full-schedule smoke scan: does every door/window/stair property BIM-Guard
claims to support actually resolve a value?

This is deliberately a RESOLUTION check, not an accuracy check (that's
``validation_new_properties_controls.py``, which scores four properties'
computed VALUES against known-correct geometry). Here the question is
narrower and broader at once: for every property named in the published
schedule, given a model that plausibly authors it, does the pipeline
actually produce a value at all -- or does it silently come back MISSING,
which would mean the schedule is documenting something that doesn't
actually work?

Two families of property need two different proof strategies:

* Per-element properties (the majority: every direct Pset/attribute read,
  every stair/landing/railing derived property, DoorClearOpeningWidth) are
  run through the REAL pipeline -- ``IFCReader.extract_for_compliance()`` ->
  ``ComplianceComparator`` -- with an ``exists`` rule, on a small synthetic
  IFC model built to plausibly carry that property. A resolved property
  reports PASS; a missing one reports FAIL with reason "property missing".
* Space-boundary-driven checks (ConnectedSpaces family via the door-space
  pass-0 shortcut, plus DaylightRatio, FireSeparation, GarageSeparation,
  ExitCount, EgressTravelDistance, EgressWindow, which are never per-element
  Pset reads at all) are proven against one small model with REAL
  ``IfcRelSpaceBoundary`` relationships -- the same relationship these
  functions parse in production, not a duck-typed stand-in.

Stair/landing/railing DERIVED (engine) properties are already exhaustively
covered by tests/test_ifc_stair.py (dozens of cases per property) and are
not re-proven here beyond a brief tally -- this script's own job is the
properties that had no end-to-end proof anywhere before now: every direct
Door/Window Pset property, the stair's own DIRECT Pset properties, and the
five space-boundary check functions.

Usage::

    uv run python scripts/validation_property_schedule_scan.py
    uv run python scripts/validation_property_schedule_scan.py --json docs/validation/data/property-schedule-scan.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import ifcopenshell  # noqa: E402
from ifcopenshell.api import run  # noqa: E402

Case = dict[str, Any]


# ── Shared geometry helpers (mesh so geometry-fallback properties resolve) ──


def _box_triangles(x0, x1, y0, y1, z0, z1):
    x0, x1, y0, y1, z0, z1 = float(x0), float(x1), float(y0), float(y1), float(z0), float(z1)
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


def _base_model():
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
    return model, body, storey


def _place_box(model, body, storey, ifc_class, name, x0, x1, y0, y1, z0, z1, predefined_type=None):
    triangles = _box_triangles(x0, x1, y0, y1, z0, z1)
    rep = _tessellated_representation(model, body, triangles)
    kwargs = {"predefined_type": predefined_type} if predefined_type else {}
    entity = run("root.create_entity", model, ifc_class=ifc_class, name=name, **kwargs)
    run("spatial.assign_container", model, products=[entity], relating_structure=storey)
    run("geometry.assign_representation", model, product=entity, representation=rep)
    run("geometry.edit_object_placement", model, product=entity, matrix=np.eye(4), is_si=False)
    return entity


def _add_pset(model, product, name, properties):
    pset = run("pset.add_pset", model, product=product, name=name)
    run("pset.edit_pset", model, pset=pset, properties=properties)
    return pset


def _space_boundary(model, space, element, physical="PHYSICAL"):
    import ifcopenshell.guid

    return model.create_entity(
        "IfcRelSpaceBoundary",
        GlobalId=ifcopenshell.guid.new(),
        RelatingSpace=space,
        RelatedBuildingElement=element,
        PhysicalOrVirtualBoundary=physical,
    )


def _resolve(model, target_class, property_name, tmp_dir: Path, name: str) -> tuple[str, Any]:
    """Run one `exists` rule through the real pipeline. Returns (status, actual)."""
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
    result = {r["rule_ref"]: r for r in results}.get("PROBE")
    if not result or not result["all_elements"]:
        return "NO_ELEMENT", None
    el = result["all_elements"][0]
    return el["status"], el.get("actual")


# ── Section A/B: Door properties ─────────────────────────────────────────────


def _build_rich_door(tmp_dir: Path):
    model, body, storey = _base_model()
    door = _place_box(model, body, storey, "IfcDoor", "D-101", 0, 900, 0, 45, 0, 2100)
    door.OverallWidth = 900.0
    door.OverallHeight = 2100.0
    door.PredefinedType = "DOOR"
    door.OperationType = "SINGLE_SWING_LEFT"
    _add_pset(model, door, "Pset_DoorCommon", {
        "FireRating": "60min", "AcousticRating": "35dB", "ThermalTransmittance": 1.8,
        "SecurityRating": "Grade 2", "SmokeStop": True, "SelfClosing": True,
        "Infiltration": 0.5, "HandicapAccessible": True, "NumberOfPanels": 1.0,
        "IsExternal": True, "FireExit": True,
    })
    return model


def _build_bare_door(tmp_dir: Path):
    """No Pset/attribute width -- forces the geometry-fallback route."""
    model, body, storey = _base_model()
    _place_box(model, body, storey, "IfcDoor", "D-Bare", 0, 900, 0, 45, 0, 2100)
    return model


def _build_door_with_alias_only_field(tmp_dir: Path):
    model, body, storey = _base_model()
    door = _place_box(model, body, storey, "IfcDoor", "D-Alias", 0, 900, 0, 45, 0, 2100)
    door.OverallWidth = 900.0
    # "EmergencyExit" only -- proves the FireExit alias table entry, not a
    # direct Pass-1 hit under the canonical name.
    _add_pset(model, door, "Pset_DoorCommon", {"EmergencyExit": True})
    return model


def door_cases(tmp_dir: Path) -> list[Case]:
    cases: list[Case] = []
    rich = _build_rich_door(tmp_dir)
    for prop in [
        "OverallWidth", "OverallHeight", "PredefinedType", "OperationType",
        "FireRating", "AcousticRating", "ThermalTransmittance", "SecurityRating",
        "SmokeStop", "SelfClosing", "Infiltration", "HandicapAccessible",
        "NumberOfPanels", "IsExternal", "FireExit",
        "DoorClearOpeningWidth", "Volume", "FootprintArea", "SurfaceArea",
        "FootprintPerimeter", "SillHeight",
    ]:
        status, actual = _resolve(rich, "IfcDoor", prop, tmp_dir, f"door-rich-{prop}")
        cases.append({"group": "Door", "property": prop, "status": status, "actual": actual})

    # Alias resolution: "Width" should resolve via alias to OverallWidth.
    status, actual = _resolve(rich, "IfcDoor", "Width", tmp_dir, "door-alias-width")
    cases.append({"group": "Door (alias)", "property": "Width -> OverallWidth", "status": status, "actual": actual})

    alias_model = _build_door_with_alias_only_field(tmp_dir)
    status, actual = _resolve(alias_model, "IfcDoor", "FireExit", tmp_dir, "door-alias-fireexit")
    cases.append({"group": "Door (alias)", "property": "FireExit -> EmergencyExit", "status": status, "actual": actual})

    bare = _build_bare_door(tmp_dir)
    for prop in ["Width", "Height", "ClearWidth", "Slope"]:
        status, actual = _resolve(bare, "IfcDoor", prop, tmp_dir, f"door-bare-{prop}")
        cases.append({"group": "Door (geometry fallback)", "property": prop, "status": status, "actual": actual})

    return cases


# ── Section C/D: Window properties ──────────────────────────────────────────


def _build_rich_window(tmp_dir: Path):
    model, body, storey = _base_model()
    window = _place_box(model, body, storey, "IfcWindow", "W-101", 0, 1200, 0, 100, 900, 2100)
    window.OverallWidth = 1200.0
    window.OverallHeight = 1200.0
    window.PredefinedType = "WINDOW"
    _add_pset(model, window, "Pset_WindowCommon", {
        "FireRating": "30min", "AcousticRating": "30dB", "ThermalTransmittance": 1.4,
        "GlazingAreaFraction": 0.85, "Infiltration": 0.3, "SecurityRating": "Grade 1",
        "SmokeStop": False, "IsExternal": True,
    })
    # Unlike IfcDoor, IfcWindow has no direct OperationType schema attribute
    # -- sash operation only ever lives in a Pset (Pset_WindowPanelProperties
    # in a real export). Finding surfaced by this very scan; see the report.
    _add_pset(model, window, "Pset_WindowPanelProperties", {"OperationType": "SLIDINGVERTICAL"})
    return model


def _build_bare_window(tmp_dir: Path):
    model, body, storey = _base_model()
    _place_box(model, body, storey, "IfcWindow", "W-Bare", 0, 1200, 0, 100, 900, 2100)
    return model


def window_cases(tmp_dir: Path) -> list[Case]:
    cases: list[Case] = []
    rich = _build_rich_window(tmp_dir)
    for prop in [
        "OverallWidth", "OverallHeight", "PredefinedType", "OperationType",
        "FireRating", "AcousticRating", "ThermalTransmittance", "GlazingAreaFraction",
        "Infiltration", "SecurityRating", "SmokeStop", "IsExternal",
        "Volume", "FootprintArea", "SurfaceArea", "FootprintPerimeter", "SillHeight",
    ]:
        status, actual = _resolve(rich, "IfcWindow", prop, tmp_dir, f"window-rich-{prop}")
        cases.append({"group": "Window", "property": prop, "status": status, "actual": actual})

    bare = _build_bare_window(tmp_dir)
    for prop in ["Width", "Height", "ClearWidth", "Slope"]:
        status, actual = _resolve(bare, "IfcWindow", prop, tmp_dir, f"window-bare-{prop}")
        cases.append({"group": "Window (geometry fallback)", "property": prop, "status": status, "actual": actual})

    return cases


# ── Section E: Stair direct Pset properties (derived ones are already ──────
# exhaustively covered by tests/test_ifc_stair.py) ──────────────────────────


def _build_rich_stair_flight(tmp_dir: Path):
    model, body, storey = _base_model()
    riser, going, width, n = 175.0, 280.0, 900.0, 4
    triangles = []
    for i in range(n):
        z = (i + 1) * riser
        x0, x1 = i * going, i * going + going
        triangles += [
            [(x0, 0.0, z), (x1, 0.0, z), (x1, width, z)],
            [(x0, 0.0, z), (x1, width, z), (x0, width, z)],
        ]
        triangles += [
            [(x0, 0.0, z - riser), (x0, width, z - riser), (x0, width, z)],
            [(x0, 0.0, z - riser), (x0, width, z), (x0, 0.0, z)],
        ]
    rep = _tessellated_representation(model, body, triangles)
    flight = run("root.create_entity", model, ifc_class="IfcStairFlight", name="Flight 1")
    run("spatial.assign_container", model, products=[flight], relating_structure=storey)
    run("geometry.assign_representation", model, product=flight, representation=rep)
    run("geometry.edit_object_placement", model, product=flight, matrix=np.eye(4), is_si=False)
    _add_pset(model, flight, "Pset_StairFlightCommon", {
        "RiserHeight": riser, "TreadLength": going, "NumberOfRiser": float(n),
        "NumberOfTreads": float(n - 1), "NosingLength": 25.0, "WaistThickness": 200.0,
    })
    _add_pset(model, flight, "Pset_BIMGuardStairFlight", {
        "WalkingLineOffset": 300.0, "HandicapAccessible": True, "HasNonSkidSurface": True,
        "RequiredHeadroom": 2100.0,
    })
    return model, flight


def stair_direct_cases(tmp_dir: Path) -> list[Case]:
    cases: list[Case] = []
    model, _flight = _build_rich_stair_flight(tmp_dir)
    for prop in [
        "RiserHeight", "TreadLength", "NumberOfRiser", "NumberOfTreads",
        "NosingLength", "WaistThickness", "WalkingLineOffset",
        "HandicapAccessible", "HasNonSkidSurface", "RequiredHeadroom",
        # Already-verified derived properties, re-probed here only as a
        # cheap sanity tripwire (full coverage lives in test_ifc_stair.py).
        "MinRiserHeight", "MinClearStairWidth", "StepFormulaMax",
    ]:
        status, actual = _resolve(model, "IfcStairFlight", prop, tmp_dir, f"stair-{prop}")
        cases.append({"group": "Stair Flight (direct)", "property": prop, "status": status, "actual": actual})

    # Alias resolution: "TreadDepth" should resolve via alias to TreadLength.
    status, actual = _resolve(model, "IfcStairFlight", "TreadDepth", tmp_dir, "stair-alias-treaddepth")
    cases.append({"group": "Stair Flight (alias)", "property": "TreadDepth -> TreadLength", "status": status, "actual": actual})

    return cases


# ── Section F: Space-boundary-driven checks (real IfcRelSpaceBoundary) ─────


def _build_space_boundary_model():
    """One small building: a Bedroom (sleeping room) with an exterior door
    and window, a Living Room sharing a party wall with a neighbouring Unit,
    and a Garage sharing a wall+door with the Bedroom -- real
    IfcRelSpaceBoundary relationships throughout, the same relationship
    every function in this section actually parses in production."""
    model, body, storey = _base_model()

    def space(name, x0, x1, y0, y1, area_m2):
        triangles = _box_triangles(x0, x1, y0, y1, 0.0, 10.0)  # thin slab-like volume
        rep = _tessellated_representation(model, body, triangles)
        sp = run("root.create_entity", model, ifc_class="IfcSpace", name=name)
        run("aggregate.assign_object", model, products=[sp], relating_object=storey)
        run("geometry.assign_representation", model, product=sp, representation=rep)
        run("geometry.edit_object_placement", model, product=sp, matrix=np.eye(4), is_si=False)
        _add_pset(model, sp, "Qto_SpaceBaseQuantities", {"NetFloorArea": area_m2})
        return sp

    bedroom = space("Master Bedroom", 0, 4000, 0, 3500, 14.0)
    unit2 = space("Unit 2", 4200, 8200, 0, 3500, 14.0)
    garage = space("Garage", 0, 4000, -6000, -3000, 18.0)

    ext_wall = _place_box(model, body, storey, "IfcWall", "Exterior Wall", -100, 0, 0, 3500, 0, 2700)
    front_door = _place_box(model, body, storey, "IfcDoor", "Front Door", -50, 850, 0, 45, 0, 2100)
    front_door.OverallWidth, front_door.OverallHeight = 900.0, 2100.0
    _add_pset(model, front_door, "Pset_DoorCommon", {"IsExternal": True})

    window = _place_box(model, body, storey, "IfcWindow", "Bedroom Window", 1000, 2200, -50, 50, 900, 2100)
    window.OverallWidth, window.OverallHeight = 1200.0, 1200.0
    _add_pset(model, window, "Pset_WindowCommon", {"IsExternal": True})
    _add_pset(model, window, "Pset_WindowPanelProperties", {"OperationType": "SLIDINGVERTICAL"})
    # check_daylight_ratios sums window area from Pset keys (_get_area_from_
    # psets), not from geometry -- a window with no authored area
    # contributes 0 m² regardless of its real mesh size.
    _add_pset(model, window, "BIMGuard_WindowQuantities", {"GlazingArea": 1.44})

    party_wall = _place_box(model, body, storey, "IfcWall", "Party Wall", 4000, 4200, 0, 3500, 0, 2700)
    _add_pset(model, party_wall, "Pset_WallCommon", {"FireRating": "45min"})

    garage_wall = _place_box(model, body, storey, "IfcWall", "Garage Wall", 0, 4000, -3100, -3000, 0, 2700)
    _add_pset(model, garage_wall, "Pset_WallCommon", {"FireRating": "30min"})
    garage_door = _place_box(model, body, storey, "IfcDoor", "Garage Door", 1500, 2400, -3100, -3050, 0, 2100)
    _add_pset(model, garage_door, "Pset_DoorCommon", {"IsExternal": False, "FireRating": "20min"})

    interior_door = _place_box(model, body, storey, "IfcDoor", "Bedroom-Unit2 Door", 4000, 4100, 1500, 1545, 0, 2100)
    _add_pset(model, interior_door, "Pset_DoorCommon", {"IsExternal": False})

    _space_boundary(model, bedroom, ext_wall)
    _space_boundary(model, bedroom, front_door)
    _space_boundary(model, bedroom, window)
    _space_boundary(model, bedroom, party_wall)
    _space_boundary(model, unit2, party_wall)
    _space_boundary(model, bedroom, garage_wall)
    _space_boundary(model, garage, garage_wall)
    _space_boundary(model, bedroom, garage_door)
    _space_boundary(model, garage, garage_door)
    _space_boundary(model, bedroom, interior_door)
    _space_boundary(model, unit2, interior_door)

    return {
        "model": model, "bedroom": bedroom, "unit2": unit2, "garage": garage,
        "front_door": front_door, "window": window, "party_wall": party_wall,
        "garage_wall": garage_wall, "garage_door": garage_door, "interior_door": interior_door,
    }


def space_boundary_cases(tmp_dir: Path) -> list[Case]:
    from app.modules.ifc_reader.ifc_spatial import (
        IFCSpatialAdjacency, check_daylight_ratios, check_fire_separation,
        check_garage_separation, check_door_space_connection, check_egress_window_openings,
    )
    from app.modules.ifc_reader.ifc_egress import check_exit_count, check_egress_travel_distance, IFCEgressGraph
    from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

    parts = _build_space_boundary_model()
    model = parts["model"]
    cases: list[Case] = []

    adjacency = IFCSpatialAdjacency(model).build()
    cases.append({
        "group": "Space boundaries", "property": "IFCSpatialAdjacency parses real IfcRelSpaceBoundary",
        "status": "PASS" if adjacency.has_boundaries and adjacency.space_count() == 3 else "FAIL",
        "actual": adjacency.space_count(),
    })

    daylight = check_daylight_ratios(adjacency, min_ratio=0.10)
    bedroom_daylight = next((r for r in daylight if r["space_name"] == "Master Bedroom"), None)
    cases.append({
        "group": "Space boundaries", "property": "DaylightRatio (check_daylight_ratios)",
        "status": "PASS" if bedroom_daylight and bedroom_daylight["total_window_area_m2"] > 0 else "FAIL",
        "actual": bedroom_daylight,
    })

    fire_sep = check_fire_separation(adjacency, min_rating_min=30.0)
    cases.append({
        "group": "Space boundaries", "property": "FireSeparation (check_fire_separation)",
        "status": "PASS" if fire_sep and fire_sep[0]["fire_rating_min"] == 45.0 else "FAIL",
        "actual": fire_sep,
    })

    garage_sep = check_garage_separation(adjacency)
    cases.append({
        "group": "Space boundaries", "property": "GarageSeparation (check_garage_separation)",
        "status": "PASS" if garage_sep else "FAIL",
        "actual": garage_sep,
    })

    door_space = check_door_space_connection(adjacency, model)
    interior_result = next(
        (r for r in door_space if r["door_name"] == "Bedroom-Unit2 Door"), None
    )
    cases.append({
        "group": "Space boundaries", "property": "ConnectedSpaces/ConnectedSpaceCount (check_door_space_connection)",
        "status": "PASS" if interior_result and interior_result["connected_space_count"] == 2 else "FAIL",
        "actual": interior_result,
    })

    # ConnectedSpaceCount via the REAL pipeline's Pass-0 shortcut (proves
    # the wiring into extract_for_compliance, not just the bare function).
    status, actual = _resolve(model, "IfcDoor", "ConnectedSpaceCount", tmp_dir, "space-connectedcount")
    cases.append({"group": "Space boundaries", "property": "ConnectedSpaceCount (via extract_for_compliance)", "status": status, "actual": actual})

    exit_count = check_exit_count(model, min_exits=1)
    cases.append({
        "group": "Space boundaries", "property": "ExitCount (check_exit_count)",
        "status": "PASS" if exit_count["total_exterior_doors"] == 1 else "FAIL",
        "actual": exit_count["total_exterior_doors"],
    })

    geo = IFCGeometryExtractor(model)
    graph = IFCEgressGraph(adjacency, geometry_extractor=geo).build()
    travel = check_egress_travel_distance(graph, max_distance_m=45.0)
    cases.append({
        "group": "Space boundaries", "property": "EgressTravelDistance (check_egress_travel_distance)",
        "status": "PASS" if travel else "FAIL",
        "actual": travel,
    })

    egress_windows = check_egress_window_openings(
        adjacency, geo, min_clear_area_m2=0.35, min_clear_width_mm=380.0,
        min_clear_height_mm=380.0, max_sill_height_mm=1100.0,
    )
    cases.append({
        "group": "Space boundaries", "property": "EgressWindowClearOpening (check_egress_window_openings)",
        "status": "PASS" if egress_windows else "FAIL",
        "actual": egress_windows,
    })

    return cases


# ── Report ────────────────────────────────────────────────────────────────────


def run_all(tmp_dir: Path) -> list[Case]:
    return (
        door_cases(tmp_dir)
        + window_cases(tmp_dir)
        + stair_direct_cases(tmp_dir)
        + space_boundary_cases(tmp_dir)
    )


def print_report(cases: list[Case]) -> int:
    print("=" * 100)
    print("PROPERTY SCHEDULE RESOLUTION SCAN")
    print("=" * 100)
    header = f"{'group':<28}{'property':<48}{'status':<10}"
    print(header)
    print("-" * len(header))
    failures = 0
    for c in cases:
        resolved = c["status"] in ("PASS",)
        if not resolved:
            failures += 1
        mark = "" if resolved else "  <-- NOT RESOLVED"
        print(f"{c['group']:<28}{c['property']:<48}{c['status']:<10}{mark}")
    print("-" * len(header))
    print(f"{len(cases) - failures}/{len(cases)} properties resolved")
    if failures:
        print(f"{failures} property(ies) did NOT resolve -- see NOT RESOLVED rows above")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        cases = run_all(Path(tmp))

    failures = print_report(cases)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "cases_total": len(cases),
                    "cases_resolved": len(cases) - failures,
                    "cases_not_resolved": failures,
                    "cases": [
                        {**c, "actual": c["actual"] if not isinstance(c["actual"], (list, dict)) else "see console"}
                        for c in cases
                    ],
                },
                indent=2, default=str,
            ),
            encoding="utf-8",
        )
        print(f"\nWrote {args.json}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
