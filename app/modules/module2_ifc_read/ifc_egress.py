"""
module2_ifc_read/ifc_egress.py
--------------------------------
Tier 3 egress path engine using NetworkX.

Builds a space-connectivity graph from IfcRelSpaceBoundary door relationships,
identifies exits (exterior doors), and computes travel distances from every
habitable space to the nearest exit.

Compliance checks:
  check_exit_count()              OBC 9.9.4.1   exterior door count per floor
  check_egress_travel_distance()  OBC 9.9.10.1  travel distance ≤ 25 m per room

Both functions return dicts / lists compatible with the analyse-route rendering.
"""

import logging
import math

logger = logging.getLogger("bimguard.egress")

try:
    import networkx as nx

    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False
    logger.warning("networkx not available — egress travel-distance check will be skipped")

try:
    import ifcopenshell.util.element

    _IFC_AVAILABLE = True
except ImportError:
    _IFC_AVAILABLE = False


# OBC Part 9 residential limits
OBC_MAX_TRAVEL_DISTANCE_M = 25.0  # 9.9.10.1 — max walking distance to exit
OBC_MIN_EXITS_PER_FLOOR = 1       # 9.9.4.1  — every occupied storey needs an exit

# Space-name keywords for classifying habitable vs non-habitable rooms.
# Habitable rooms are those OBC 9.9.10 limits apply to.
_HABITABLE_KW = frozenset([
    "bedroom", "living", "dining", "kitchen", "study", "office",
    "lounge", "recreation", "family", "playroom", "den", "library",
    "master", "loft", "great room", "guest", "media", "gym",
])

_NON_HABITABLE_KW = frozenset([
    "bathroom", "toilet", "wc", "closet", "utility", "laundry",
    "storage", "hallway", "corridor", "foyer", "lobby", "stair",
    "mechanical", "electrical", "garage", "balcony", "crawl", "attic",
    "pantry", "mudroom",
])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_exterior_door(door_element) -> bool:
    """Return True when a door has IsExternal=True in any Pset."""
    if not _IFC_AVAILABLE:
        return False
    try:
        psets = ifcopenshell.util.element.get_psets(door_element, psets_only=False)
        for ps in psets.values():
            if isinstance(ps, dict):
                v = ps.get("IsExternal")
                if v is True or str(v).upper() in ("TRUE", "1", "YES"):
                    return True
    except Exception:
        pass
    return False


def _get_area_m2(space) -> float | None:
    """Read floor area (m²) from Psets / Qto sets of an IfcSpace."""
    if not _IFC_AVAILABLE:
        return None
    try:
        psets = ifcopenshell.util.element.get_psets(space, psets_only=False)
        for ps in psets.values():
            if not isinstance(ps, dict):
                continue
            for key in ("NetFloorArea", "GrossFloorArea", "NetArea", "GrossArea", "Area"):
                v = ps.get(key)
                if v is not None:
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        pass
    except Exception:
        pass
    return None


def _space_display_name(space) -> str:
    return (
        getattr(space, "LongName", None)
        or getattr(space, "Name", None)
        or space.GlobalId
    )


def _is_habitable(name: str) -> bool:
    """
    Classify a space as habitable (OBC travel-distance limit applies).
    Defaults to True (conservative) for spaces whose name matches neither list.
    """
    n = name.lower()
    for kw in _NON_HABITABLE_KW:
        if kw in n:
            return False
    for kw in _HABITABLE_KW:
        if kw in n:
            return True
    return True  # unknown → treat as habitable


def _get_storey_from_element(element) -> str:
    """Return the IfcBuildingStorey name for any element via ContainedInStructure."""
    try:
        for rel in getattr(element, "ContainedInStructure", []):
            container = rel.RelatingStructure
            if container.is_a("IfcBuildingStorey"):
                return getattr(container, "Name", None) or "Unnamed Storey"
    except Exception:
        pass
    return "Unassigned"


# ── Graph builder ──────────────────────────────────────────────────────────────

class IFCEgressGraph:
    """
    Space-connectivity graph for egress-path analysis.

    Nodes  : IfcSpace GUIDs
    Edges  : space pairs that share a physical IfcDoor boundary
    Weight : estimated traversal distance (m) = sqrt(floor area of the space being left)
    Exits  : spaces that contain at least one exterior door (IsExternal=True)
    """

    def __init__(self, adjacency):
        """
        Args:
            adjacency: IFCSpatialAdjacency instance (already built).
        """
        self.adjacency = adjacency
        self.graph: "nx.Graph | None" = None
        self._exit_spaces: set[str] = set()
        self._habitable_spaces: set[str] = set()
        self._space_names: dict[str, str] = {}
        self._space_storeys: dict[str, str] = {}
        self._built = False

    def build(self) -> "IFCEgressGraph":
        """Populate graph nodes and edges from the spatial adjacency map."""
        if self._built or not _NX_AVAILABLE:
            self._built = True
            return self

        adj = self.adjacency
        if not adj.has_boundaries:
            self._built = True
            return self

        G: nx.Graph = nx.Graph()

        # ── Step 1: add one node per IfcSpace ─────────────────────────────────
        from .ifc_spatial import _get_storey_name  # reuse existing helper

        for sguid, data in adj._space_data.items():
            space = data["space"]
            name = _space_display_name(space)
            storey = _get_storey_name(space) or "—"
            area = _get_area_m2(space) or 9.0  # default 9 m² ≈ 3×3 room
            traversal_m = max(1.5, math.sqrt(area))  # rough walk-through cost

            G.add_node(
                sguid,
                name=name,
                storey=storey,
                area_m2=area,
                traversal_m=traversal_m,
                is_exit=False,
            )
            self._space_names[sguid] = name
            self._space_storeys[sguid] = storey
            if _is_habitable(name):
                self._habitable_spaces.add(sguid)

        # ── Step 2: map door GUIDs → space GUIDs and detect exterior doors ────
        door_to_spaces: dict[str, list[str]] = {}
        exterior_door_guids: set[str] = set()

        for sguid, data in adj._space_data.items():
            for b in data["boundaries"]:
                if b["element_type"] != "IfcDoor" or not b["physical"]:
                    continue
                door_guid = b["element_guid"]
                door_el = b["element"]

                if door_guid not in door_to_spaces:
                    door_to_spaces[door_guid] = []
                    if _is_exterior_door(door_el):
                        exterior_door_guids.add(door_guid)

                if sguid not in door_to_spaces[door_guid]:
                    door_to_spaces[door_guid].append(sguid)

        # ── Step 3: add edges and mark exit spaces ────────────────────────────
        for door_guid, space_guids in door_to_spaces.items():
            if door_guid in exterior_door_guids:
                for sg in space_guids:
                    if sg in G:
                        self._exit_spaces.add(sg)
                        G.nodes[sg]["is_exit"] = True

            # Connect every pair of spaces sharing this door
            for i in range(len(space_guids)):
                for j in range(i + 1, len(space_guids)):
                    a, b_ = space_guids[i], space_guids[j]
                    if a not in G or b_ not in G:
                        continue
                    # Edge weight = average traversal cost of both spaces
                    w = (G.nodes[a]["traversal_m"] + G.nodes[b_]["traversal_m"]) / 2.0
                    if G.has_edge(a, b_):
                        if G[a][b_]["weight"] > w:
                            G[a][b_]["weight"] = w
                    else:
                        G.add_edge(a, b_, weight=w)

        self.graph = G
        self._built = True
        return self


# ── Check 1: exit count ────────────────────────────────────────────────────────

def check_exit_count(ifc_file) -> dict:
    """
    OBC 9.9.4.1 — count exterior doors per storey and flag floors with zero exits.

    Does NOT require IfcRelSpaceBoundary data.

    Returns:
        {
          total_exterior_doors : int,
          exits_per_storey     : {storey_name: count},
          results              : [{storey, count, passes, obc_ref}],
          warnings             : [str],
        }
    """
    if ifc_file is None:
        return {
            "total_exterior_doors": 0,
            "exits_per_storey": {},
            "results": [],
            "warnings": ["No IFC file loaded."],
        }

    exits_per_storey: dict[str, int] = {}
    warnings: list[str] = []

    try:
        doors = ifc_file.by_type("IfcDoor")
        for door in doors:
            if not _is_exterior_door(door):
                continue
            storey = _get_storey_from_element(door)
            exits_per_storey[storey] = exits_per_storey.get(storey, 0) + 1
    except Exception as exc:
        warnings.append(f"Could not read IfcDoor elements: {exc}")

    total = sum(exits_per_storey.values())

    results = []
    for storey, count in sorted(exits_per_storey.items()):
        passes = count >= OBC_MIN_EXITS_PER_FLOOR
        results.append({
            "obc_ref": "OBC 9.9.4.1",
            "storey": storey,
            "exit_count": count,
            "required_min": OBC_MIN_EXITS_PER_FLOOR,
            "passes": passes,
        })

    if total == 0:
        warnings.append(
            "No exterior doors detected (IsExternal=True not set on any IfcDoor). "
            "Tag exterior doors in the authoring tool and re-export."
        )

    return {
        "total_exterior_doors": total,
        "exits_per_storey": exits_per_storey,
        "results": results,
        "warnings": warnings,
    }


# ── Check 2: egress travel distance ───────────────────────────────────────────

def check_egress_travel_distance(egress_graph: IFCEgressGraph) -> list[dict]:
    """
    OBC 9.9.10.1 — travel distance from any habitable room to the nearest exit ≤ 25 m.

    Uses Dijkstra shortest-path on the space-connectivity graph.

    Returns one result dict per habitable space.
    """
    if not _NX_AVAILABLE:
        return []

    G = egress_graph.graph
    if G is None or G.number_of_nodes() == 0:
        return []

    if not egress_graph._exit_spaces:
        return []

    results: list[dict] = []

    for sguid in egress_graph._habitable_spaces:
        if sguid not in G:
            continue

        name = egress_graph._space_names.get(sguid, sguid)
        storey = egress_graph._space_storeys.get(sguid, "—")

        # Find shortest path to any exit
        best_dist: float | None = None
        best_exit_name: str | None = None

        if sguid in egress_graph._exit_spaces:
            # Already an exit space (contains exterior door)
            best_dist = 0.0
            best_exit_name = name
        else:
            for exit_guid in egress_graph._exit_spaces:
                if exit_guid not in G:
                    continue
                try:
                    dist = nx.shortest_path_length(G, sguid, exit_guid, weight="weight")
                    if best_dist is None or dist < best_dist:
                        best_dist = dist
                        best_exit_name = egress_graph._space_names.get(exit_guid, exit_guid)
                except nx.NetworkXNoPath:
                    continue

        if best_dist is None:
            results.append({
                "check": "egress_travel_distance",
                "obc_ref": "OBC 9.9.10.1",
                "space_guid": sguid,
                "space_name": name,
                "storey_name": storey,
                "travel_distance_m": None,
                "nearest_exit": None,
                "required_max_m": OBC_MAX_TRAVEL_DISTANCE_M,
                "passes": False,
                "no_path": True,
                "severity": "mandatory",
            })
        else:
            passes = best_dist <= OBC_MAX_TRAVEL_DISTANCE_M
            results.append({
                "check": "egress_travel_distance",
                "obc_ref": "OBC 9.9.10.1",
                "space_guid": sguid,
                "space_name": name,
                "storey_name": storey,
                "travel_distance_m": round(best_dist, 1),
                "nearest_exit": best_exit_name,
                "required_max_m": OBC_MAX_TRAVEL_DISTANCE_M,
                "passes": passes,
                "no_path": False,
                "severity": "mandatory",
            })

    return results
