"""Wire already-computed geometry/egress outputs onto a BOT graph as literals.

`bot_graph.enrich_literal()` has existed since the graph builder was added,
but nothing called it: `_run_shacl_compliance`
(`app.modules.orchestrator`) documented this as a known limitation, since a
SHACL shape targeting an engine-computed property (e.g. a door's calculated
clear opening width) could never match any element. This module closes that
gap by reusing values the analysis pipeline already computes elsewhere --
it does not recompute any geometry itself.
"""

from __future__ import annotations

from typing import Any

from rdflib import Graph

from app.modules.ifc_reader.bot_graph import enrich_literal


def enrich_bot_graph_with_engine_outputs(
    graph: Graph,
    *,
    m2_reader: Any = None,
    egress_checks: dict | None = None,
) -> None:
    """Attach engine-computed values already derived elsewhere onto `graph`.

    Two literals are wired today:

    - `bimguard:calculatedClearWidth` (mm) on every `IfcDoor`, via the same
      `M2Reader._door_clear_opening_width()` cascade the procedural
      comparator uses for the `doorClearOpeningWidth` rule property, so a
      SHACL shape and a procedural rule agree on the value.
    - `bimguard:travelDistanceM` on every space with a resolved egress
      travel distance, taken from the `travel_distance` records
      `ifc_egress.check_egress_travel_distance()` already produced.

    Each element is enriched best-effort: a reader that cannot resolve a
    value (missing geometry, a stub reader in a test) is skipped rather than
    raising, matching how the rest of the IFC-reading pipeline treats
    per-element extraction failures.
    """
    _enrich_door_clear_widths(graph, m2_reader)
    _enrich_travel_distances(graph, egress_checks)


def _enrich_door_clear_widths(graph: Graph, m2_reader: Any) -> None:
    ifc_file = getattr(m2_reader, "ifc_file", None)
    compute = getattr(m2_reader, "_door_clear_opening_width", None)
    if ifc_file is None or compute is None:
        return

    for door in ifc_file.by_type("IfcDoor"):
        guid = getattr(door, "GlobalId", None)
        if not guid:
            continue
        try:
            clear_width_mm, _detail = compute(door)
        except Exception:
            continue
        if clear_width_mm is not None:
            enrich_literal(graph, guid, "calculatedClearWidth", clear_width_mm, unit="mm")


def _enrich_travel_distances(graph: Graph, egress_checks: dict | None) -> None:
    for record in (egress_checks or {}).get("travel_distance") or []:
        space_guid = record.get("space_guid")
        distance_m = record.get("travel_distance_m")
        if space_guid and distance_m is not None:
            enrich_literal(graph, space_guid, "travelDistanceM", distance_m, unit="m")
