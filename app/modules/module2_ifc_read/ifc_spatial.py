"""
module2_ifc_read/ifc_spatial.py
---------------------------------
Tier 2 spatial adjacency engine.

Parses IfcRelSpaceBoundary to map every IfcSpace to the walls, doors and
windows that bound it, and identifies party walls shared between two spaces.

Two compliance checks are built on top of the adjacency map:
  - check_daylight_ratios()     OBC 9.7.2  window area / floor area >= 1/10
  - check_fire_separation()     OBC 9.10.9 party walls must have FireRating >= 45 min

Both return lists of result dicts compatible with the Module 4 report format.
"""

import logging

logger = logging.getLogger("bimguard.spatial")

try:
    import ifcopenshell
    import ifcopenshell.util.element

    _IFC_AVAILABLE = True
except ImportError:
    _IFC_AVAILABLE = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_area_from_psets(element) -> float | None:
    """Read any area quantity from an element's Psets / Qto sets."""
    try:
        psets = ifcopenshell.util.element.get_psets(element, psets_only=False)
        for ps in psets.values():
            if not isinstance(ps, dict):
                continue
            for key in (
                "NetFloorArea", "GrossFloorArea", "NetArea", "GrossArea",
                "GlazingArea", "OverallArea", "Area",
            ):
                v = ps.get(key)
                if v is not None:
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        pass
    except Exception:
        pass
    return None


def _get_fire_rating(element) -> tuple[str | None, float | None]:
    """
    Read FireRating from Pset_WallCommon (or any Pset).

    Returns (raw_string, numeric_minutes).
    """
    try:
        psets = ifcopenshell.util.element.get_psets(element, psets_only=False)
        for ps in psets.values():
            if not isinstance(ps, dict):
                continue
            for key in ("FireRating", "FireResistanceRating", "FireResistance", "REI", "FRR"):
                raw = ps.get(key)
                if raw is None:
                    continue
                raw_str = str(raw)
                # Attempt to extract a number (e.g. "45 min", "60", "REI 90")
                import re
                m = re.search(r"(\d+(?:\.\d+)?)", raw_str)
                numeric = float(m.group(1)) if m else None
                return raw_str, numeric
    except Exception:
        pass
    return None, None


# ── Core adjacency builder ────────────────────────────────────────────────────

class IFCSpatialAdjacency:
    """
    Builds a spatial adjacency map from IfcRelSpaceBoundary relationships.

    Attributes populated after build():
      _space_data  : {space_guid -> {space, boundaries: [{element, type, physical}]}}
      _wall_spaces : {wall_guid  -> [space_guid, ...]}   -- party wall detection
      has_boundaries : bool  -- False if the file has no IfcRelSpaceBoundary data
    """

    def __init__(self, ifc_file):
        self.ifc_file = ifc_file
        self._space_data: dict[str, dict] = {}
        self._wall_spaces: dict[str, list[str]] = {}
        self.has_boundaries = False
        self._built = False

    def build(self) -> "IFCSpatialAdjacency":
        """Parse IfcRelSpaceBoundary and populate adjacency structures."""
        if self._built:
            return self

        try:
            rels = self.ifc_file.by_type("IfcRelSpaceBoundary")
        except Exception:
            rels = []

        for rel in rels:
            try:
                space = rel.RelatingSpace
                element = getattr(rel, "RelatedBuildingElement", None)
                if space is None or element is None:
                    continue

                space_guid = space.GlobalId
                elem_guid = element.GlobalId
                elem_type = element.is_a()
                physical = (
                    getattr(rel, "PhysicalOrVirtualBoundary", "PHYSICAL") == "PHYSICAL"
                )

                if space_guid not in self._space_data:
                    self._space_data[space_guid] = {
                        "space": space,
                        "boundaries": [],
                    }

                self._space_data[space_guid]["boundaries"].append(
                    {
                        "element": element,
                        "element_guid": elem_guid,
                        "element_type": elem_type,
                        "physical": physical,
                    }
                )

                # Track party walls: walls shared between 2+ spaces
                if elem_type in ("IfcWall", "IfcWallStandardCase"):
                    if elem_guid not in self._wall_spaces:
                        self._wall_spaces[elem_guid] = []
                    if space_guid not in self._wall_spaces[elem_guid]:
                        self._wall_spaces[elem_guid].append(space_guid)

            except Exception as e:
                logger.debug(f"Skipping boundary rel: {e}")
                continue

        self.has_boundaries = len(self._space_data) > 0
        self._built = True

        if not self.has_boundaries:
            logger.warning(
                "No IfcRelSpaceBoundary data found. "
                "Daylight and fire separation checks will be skipped. "
                "Export your model with Space Boundaries enabled."
            )

        return self

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_space_elements(self, space_guid: str, ifc_type: str) -> list:
        """Return all elements of ifc_type bounding the given space."""
        data = self._space_data.get(space_guid, {})
        return [
            b["element"]
            for b in data.get("boundaries", [])
            if b["element_type"] == ifc_type and b["physical"]
        ]

    def get_party_walls(self) -> list[dict]:
        """Return walls shared between two or more spaces."""
        return [
            {"wall_guid": wguid, "space_guids": sguids}
            for wguid, sguids in self._wall_spaces.items()
            if len(sguids) >= 2
        ]

    def get_adjacent_spaces(self, space_guid: str) -> list[str]:
        """Return guids of spaces that share a wall with this space."""
        adjacent: set[str] = set()
        data = self._space_data.get(space_guid, {})
        for b in data.get("boundaries", []):
            if b["element_type"] not in ("IfcWall", "IfcWallStandardCase"):
                continue
            for other_guid, other_spaces in self._wall_spaces.items():
                if b["element_guid"] == other_guid:
                    for sg in other_spaces:
                        if sg != space_guid:
                            adjacent.add(sg)
        return list(adjacent)

    def space_count(self) -> int:
        return len(self._space_data)

    def party_wall_count(self) -> int:
        return len(self.get_party_walls())


# ── Tier 2 checks ─────────────────────────────────────────────────────────────

def check_daylight_ratios(adjacency: IFCSpatialAdjacency) -> list[dict]:
    """
    OBC 9.7.2 — every habitable room must have window area >= 1/10 of floor area.

    Returns one result dict per IfcSpace that has floor area data.
    Spaces with no floor area are skipped (cannot evaluate).
    """
    if not adjacency.has_boundaries:
        return []

    results = []

    for space_guid, data in adjacency._space_data.items():
        space = data["space"]
        space_name = (
            getattr(space, "LongName", None)
            or getattr(space, "Name", None)
            or space_guid
        )

        floor_area = _get_area_from_psets(space)
        if not floor_area:
            continue  # can't evaluate without floor area

        # Sum glazed area of all windows bounding this space
        windows = [
            b["element"]
            for b in data["boundaries"]
            if b["element_type"] == "IfcWindow" and b["physical"]
        ]

        total_window_area = 0.0
        window_details = []
        for win in windows:
            area = _get_area_from_psets(win)
            win_name = getattr(win, "Name", None) or win.GlobalId
            if area:
                total_window_area += area
                window_details.append({"name": win_name, "area_m2": round(area, 4)})

        ratio = total_window_area / floor_area if floor_area else 0.0
        passes = ratio >= 0.10

        results.append(
            {
                "check": "daylight_ratio",
                "obc_ref": "OBC 9.7.2",
                "space_guid": space_guid,
                "space_name": space_name,
                "floor_area_m2": round(floor_area, 3),
                "total_window_area_m2": round(total_window_area, 3),
                "daylight_ratio": round(ratio, 4),
                "required_ratio": 0.10,
                "passes": passes,
                "window_count": len(windows),
                "windows": window_details,
                "severity": "mandatory",
            }
        )

    return results


def check_fire_separation(adjacency: IFCSpatialAdjacency) -> list[dict]:
    """
    OBC 9.10.9 — party walls between dwelling units must have FireRating >= 45 min.

    Returns one result dict per party wall found.
    Walls with no FireRating declared are flagged as missing data.
    """
    if not adjacency.has_boundaries:
        return []

    results = []

    for pw in adjacency.get_party_walls():
        wall_guid = pw["wall_guid"]
        space_guids = pw["space_guids"]

        # Resolve wall element from guid
        wall = None
        try:
            for candidate in adjacency.ifc_file.by_type("IfcWall"):
                if candidate.GlobalId == wall_guid:
                    wall = candidate
                    break
        except Exception:
            pass

        if wall is None:
            continue

        wall_name = getattr(wall, "Name", None) or wall_guid
        raw_rating, numeric_rating = _get_fire_rating(wall)

        # Resolve space names for context
        space_names = []
        for sg in space_guids:
            sp_data = adjacency._space_data.get(sg, {})
            sp = sp_data.get("space")
            if sp:
                name = (
                    getattr(sp, "LongName", None)
                    or getattr(sp, "Name", None)
                    or sg
                )
                space_names.append(name)

        missing_rating = raw_rating is None
        passes = not missing_rating and numeric_rating is not None and numeric_rating >= 45

        results.append(
            {
                "check": "fire_separation",
                "obc_ref": "OBC 9.10.9",
                "wall_guid": wall_guid,
                "wall_name": wall_name,
                "adjacent_spaces": space_names,
                "fire_rating_raw": raw_rating,
                "fire_rating_min": numeric_rating,
                "required_min": 45,
                "passes": passes,
                "missing_rating": missing_rating,
                "severity": "mandatory",
            }
        )

    return results
