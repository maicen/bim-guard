"""
ifc_reader/ifc_spatial.py
---------------------------------
Tier 2 spatial adjacency engine.

Parses IfcRelSpaceBoundary to map every IfcSpace to the walls, doors and
windows that bound it, and identifies party walls shared between two spaces.

Two compliance checks are built on top of the adjacency map:
    - check_daylight_ratios()     window area / floor area >= 1/10
    - check_fire_separation()     party walls should have FireRating >= 45 min

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


def _is_exterior_door(element) -> bool | None:
    """Classify an element (typically an IfcDoor) as exterior/interior from
    IsExternal. Checks Pset_DoorCommon first, then any other pset. Returns
    None (not False) when no reliable IsExternal data exists at all — callers
    must not silently treat "unknown" as "interior".
    """
    if not _IFC_AVAILABLE:
        return None
    try:
        psets = ifcopenshell.util.element.get_psets(element, psets_only=False)
    except Exception:
        return None

    def _as_bool(v):
        if isinstance(v, bool):
            return v
        if v is None:
            return None
        s = str(v).strip().upper()
        if s in ("TRUE", "1", "YES", "T"):
            return True
        if s in ("FALSE", "0", "NO", "F"):
            return False
        return None

    door_common = psets.get("Pset_DoorCommon")
    if isinstance(door_common, dict) and "IsExternal" in door_common:
        result = _as_bool(door_common.get("IsExternal"))
        if result is not None:
            return result

    for ps in psets.values():
        if isinstance(ps, dict) and "IsExternal" in ps:
            result = _as_bool(ps.get("IsExternal"))
            if result is not None:
                return result

    return None


def _element_matches_location(element, location: str) -> bool:
    """True if an element's IsExternal classification matches an
    applies_when.location condition ("interior" or "exterior"). An element
    with no verifiable IsExternal data (_is_exterior_door returns None) is
    excluded — never guessed into either bucket.
    """
    is_ext = _is_exterior_door(element)
    if is_ext is None:
        return False
    return is_ext if location == "exterior" else not is_ext


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
        self._door_to_spaces: dict[str, list[str]] | None = None
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

    def get_door_to_spaces(self) -> dict[str, list[str]]:
        """Return {door_guid -> sorted [space_guid, ...]}, lazily built and
        cached. Was previously duplicated independently in
        check_garage_separation() and IFCEgressGraph.build() — this is the
        one shared source of truth both now use. A set is used while
        accumulating so a door/space pair boundary emitted more than once by
        an exporter can't inflate the connected-space count.
        """
        if self._door_to_spaces is not None:
            return self._door_to_spaces

        mapping: dict[str, set[str]] = {}
        for sguid, data in self._space_data.items():
            for b in data["boundaries"]:
                if b["element_type"] != "IfcDoor" or not b["physical"]:
                    continue
                dguid = b["element_guid"]
                mapping.setdefault(dguid, set()).add(sguid)

        self._door_to_spaces = {
            dguid: sorted(sguids) for dguid, sguids in mapping.items()
        }
        return self._door_to_spaces


# ── Tier 2 checks ─────────────────────────────────────────────────────────────

def _get_storey_name(space) -> str | None:
    """Resolve the IfcBuildingStorey name for a space via ContainedInStructure."""
    try:
        for rel in getattr(space, "ContainedInStructure", []):
            container = rel.RelatingStructure
            if container.is_a("IfcBuildingStorey"):
                return getattr(container, "Name", None)
            # Space may be nested inside another space — walk one level up
            if container.is_a("IfcSpace"):
                for rel2 in getattr(container, "ContainedInStructure", []):
                    cont2 = rel2.RelatingStructure
                    if cont2.is_a("IfcBuildingStorey"):
                        return getattr(cont2, "Name", None)
    except Exception:
        pass
    return None


def check_daylight_ratios(
    adjacency: IFCSpatialAdjacency,
    min_ratio: float | None = None,
) -> list[dict]:
    """
    Evaluate daylight ratio: every habitable room should have window area >= min_ratio floor area.

    ``min_ratio`` comes from an explicit argument, else a BUILDING-CODE-PART9
    rule (9.7.2.3 / DaylightRatio / a ratio-unit 9.7.2.* rule). If neither
    supplies one, this returns an empty list -- no configured ratio means
    nothing to verify rooms against, matching how a missing boundary
    precondition is already handled above rather than silently checking
    against a residential-default ratio.

    Returns one result dict per IfcSpace that has floor area data.
    Spaces with no floor area are skipped (cannot evaluate).
    """
    if not adjacency.has_boundaries:
        return []

    if min_ratio is None:
        try:
            from app.services.rules_service import RuleService

            for r in RuleService().list_by_ruleset("BUILDING-CODE-PART9"):
                ref = str(r.get("reference") or "")
                prop = str(r.get("property_name") or "")
                unit = str(r.get("unit") or "").lower()
                if "9.7.2.3" in ref or prop == "DaylightRatio" or (unit == "ratio" and "9.7.2" in ref):
                    val = r.get("check_value")
                    if val is not None and 0.0 < float(val) <= 1.0:
                        min_ratio = float(val)
                        break
        except Exception:
            pass
    if min_ratio is None:
        return []
    required_ratio = min_ratio

    results = []

    for space_guid, data in adjacency._space_data.items():
        space = data["space"]
        space_name = (
            getattr(space, "LongName", None)
            or getattr(space, "Name", None)
            or space_guid
        )
        storey_name = _get_storey_name(space)

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
        passes = ratio >= required_ratio

        results.append(
            {
                "check": "daylight_ratio",
                "code_ref": "CODE 9.7.2",
                "space_guid": space_guid,
                "space_name": space_name,
                "storey_name": storey_name or "—",
                "floor_area_m2": round(floor_area, 3),
                "total_window_area_m2": round(total_window_area, 3),
                "daylight_ratio": round(ratio, 4),
                "required_ratio": required_ratio,
                "passes": passes,
                "window_count": len(windows),
                "windows": window_details,
                "severity": "mandatory",
            }
        )

    return results


#: Sleeping-room keywords -- the emergency-escape-and-rescue-opening
#: requirement (residential codes' "egress window" clause, e.g. IRC R310 /
#: NBC Part 9's window-egress provisions) applies specifically to bedrooms,
#: not every habitable room: a living room or kitchen with no operable
#: window of its own is not the same code violation a windowless bedroom is.
_SLEEPING_ROOM_KW = frozenset([
    "bedroom", "master bedroom", "guest room", "guest bedroom",
    "bunk room", "nursery",
])


def _is_sleeping_room(name: str) -> bool:
    """Pure name classifier -- no IFC access, unit-testable on its own."""
    n = (name or "").lower()
    return any(kw in n for kw in _SLEEPING_ROOM_KW)


#: (width_fraction, height_fraction) of a window's own full glazed envelope
#: that becomes the CLEAR OPENING once the sash is operated, keyed by
#: ``IfcWindowPanelOperationEnum``. A side/top/bottom-hung or pivoting sash
#: swings its whole leaf clear of the frame (minus hardware), so both
#: dimensions shrink only slightly; a sliding sash only ever has ONE of its
#: two dimensions open at a time -- the other sash permanently occupies the
#: rest of that dimension -- so that dimension is cut roughly in half while
#: the other stays near-full. FIXEDCASEMENT never opens at all.
#:
#: This is a documented v1 approximation (see compute_egress_clear_opening's
#: docstring), not a true net-clear-opening measurement of the sash's own
#: frame profile -- an operation type absent from this table, or absent
#: from the model entirely, is left Undetermined rather than guessed.
_OPERABLE_FRACTIONS: dict[str, tuple[float, float]] = {
    "SIDEHUNGLEFTHAND": (0.90, 0.90),
    "SIDEHUNGRIGHTHAND": (0.90, 0.90),
    "TILTANDTURNLEFTHAND": (0.90, 0.90),
    "TILTANDTURNRIGHTHAND": (0.90, 0.90),
    "TOPHUNG": (0.90, 0.90),
    "BOTTOMHUNG": (0.90, 0.90),
    "PIVOTHORIZONTAL": (0.85, 0.85),
    "PIVOTVERTICAL": (0.85, 0.85),
    "REMOVABLECASEMENT": (0.95, 0.95),
    "SLIDINGHORIZONTAL": (0.48, 0.90),
    "SLIDINGVERTICAL": (0.90, 0.46),
    "FIXEDCASEMENT": (0.0, 0.0),
}


def compute_egress_clear_opening(
    operation_type: str | None, width_mm: float | None, height_mm: float | None
) -> dict:
    """Pure arithmetic layer: no IFC access, unit-testable with plain
    values -- mirrors the split ``ifc_stair.py`` uses for the same reason
    (the arithmetic that could produce a wrong verdict should be provable
    without a model).

    Returns ``{"assessed": bool, "clear_width_mm", "clear_height_mm",
    "clear_area_m2", "reason"}``. ``assessed`` is False -- with a ``reason``
    naming why, never a guessed number -- whenever the operation type is
    missing, unrecognised, or the window's own geometry didn't resolve.
    """
    if width_mm is None or height_mm is None:
        return {"assessed": False, "reason": "window geometry not resolvable"}
    op = (operation_type or "").strip().upper().replace(" ", "").replace("_", "")
    fractions = _OPERABLE_FRACTIONS.get(op)
    if fractions is None:
        return {
            "assessed": False,
            "reason": (
                "window operation type not declared"
                if not op
                else f"unrecognised operation type '{operation_type}'"
            ),
        }
    width_fraction, height_fraction = fractions
    clear_width_mm = round(width_mm * width_fraction, 1)
    clear_height_mm = round(height_mm * height_fraction, 1)
    clear_area_m2 = round((clear_width_mm * clear_height_mm) / 1e6, 3)
    return {
        "assessed": True,
        "operation_type": op,
        "clear_width_mm": clear_width_mm,
        "clear_height_mm": clear_height_mm,
        "clear_area_m2": clear_area_m2,
    }


def _resolve_window_operation_type(window) -> str | None:
    """Best-effort read of a window's sash operation, from any Pset key
    literally named OperationType/PanelOperation -- on the instance or its
    type, since ``get_psets(should_inherit=True)`` (the default) walks both.
    Returns None (not a guess) when no such key is found anywhere."""
    if not _IFC_AVAILABLE:
        return None
    try:
        psets = ifcopenshell.util.element.get_psets(window, psets_only=False)
    except Exception:
        return None
    for ps in psets.values():
        if not isinstance(ps, dict):
            continue
        for key in ("OperationType", "PanelOperation"):
            v = ps.get(key)
            if v:
                return str(v).strip()
    return None


def _get_floor_z_mm(element, geometry_extractor) -> float | None:
    """Storey floor elevation in mm, for measuring a window's sill height
    above its OWN floor rather than an arbitrary world Z=0 -- same
    ContainedInStructure walk and unit-scale convention already used
    elsewhere in this codebase (see ifc_reader.__init__'s SillHeight path)."""
    try:
        for rel in getattr(element, "ContainedInStructure", []):
            container = rel.RelatingStructure
            if container.is_a("IfcBuildingStorey"):
                elev = getattr(container, "Elevation", None)
                if elev is None:
                    return None
                scale = getattr(geometry_extractor, "_unit_scale", 1.0) or 1.0
                return float(elev) * scale
    except Exception:
        pass
    return None


def check_egress_window_openings(
    adjacency: "IFCSpatialAdjacency",
    geometry_extractor=None,
    *,
    min_clear_area_m2: float | None = None,
    min_clear_width_mm: float | None = None,
    min_clear_height_mm: float | None = None,
    max_sill_height_mm: float | None = None,
) -> list[dict]:
    """
    Evaluate the emergency-escape-and-rescue-opening requirement: every
    sleeping room needs at least one OPERABLE window with a minimum clear
    opening (area/width/height) and a maximum sill height above its own
    floor.

    Every threshold comes from an explicit argument, else a
    BUILDING-CODE-PART9 rule keyed by property_name (EgressWindowClearArea,
    EgressWindowClearWidth, EgressWindowClearHeight,
    EgressWindowMaxSillHeight). With none configured and none supplied, this
    returns an empty list -- consistent with every other check in this
    module, never a hardcoded residential-default number.

    Returns one result dict per sleeping-room IfcSpace with boundary data,
    describing the BEST (largest clear-area) window found -- a room needs
    only ONE compliant opening, so it should be judged by its best window,
    not penalised for also having smaller or fixed ones. A room with no
    assessable window still gets a result (``best_window`` is None, and
    ``passes`` is False), so a missing rescue opening is a reported
    failure, not a silently-skipped one.
    """
    if not adjacency.has_boundaries:
        return []

    if (
        min_clear_area_m2 is None
        and min_clear_width_mm is None
        and min_clear_height_mm is None
        and max_sill_height_mm is None
    ):
        try:
            from app.services.rules_service import RuleService

            for r in RuleService().list_by_ruleset("BUILDING-CODE-PART9"):
                prop = str(r.get("property_name") or "")
                val = r.get("check_value")
                if val is None:
                    continue
                if prop == "EgressWindowClearArea":
                    min_clear_area_m2 = float(val)
                elif prop == "EgressWindowClearWidth":
                    min_clear_width_mm = float(val)
                elif prop == "EgressWindowClearHeight":
                    min_clear_height_mm = float(val)
                elif prop == "EgressWindowMaxSillHeight":
                    max_sill_height_mm = float(val)
        except Exception:
            pass

    if (
        min_clear_area_m2 is None
        and min_clear_width_mm is None
        and min_clear_height_mm is None
        and max_sill_height_mm is None
    ):
        return []

    results = []
    for space_guid, data in adjacency._space_data.items():
        space = data["space"]
        space_name = (
            getattr(space, "LongName", None)
            or getattr(space, "Name", None)
            or space_guid
        )
        if not _is_sleeping_room(space_name):
            continue
        storey_name = _get_storey_name(space)

        windows = [
            b["element"]
            for b in data["boundaries"]
            if b["element_type"] == "IfcWindow" and b["physical"]
        ]

        candidates = []
        for win in windows:
            win_name = getattr(win, "Name", None) or win.GlobalId
            width_mm = geometry_extractor.get_width_mm(win) if geometry_extractor else None
            height_mm = geometry_extractor.get_height_mm(win) if geometry_extractor else None
            bottom_mm = geometry_extractor.get_bottom_z_mm(win) if geometry_extractor else None
            floor_mm = _get_floor_z_mm(win, geometry_extractor) if geometry_extractor else None
            sill_mm = (
                round(bottom_mm - floor_mm, 1)
                if bottom_mm is not None and floor_mm is not None
                else None
            )
            operation_type = _resolve_window_operation_type(win)
            opening = compute_egress_clear_opening(operation_type, width_mm, height_mm)

            candidates.append({
                "name": win_name,
                "guid": win.GlobalId,
                "sill_height_mm": sill_mm,
                **opening,
            })

        assessed = [c for c in candidates if c["assessed"] and c["sill_height_mm"] is not None]
        best = max(assessed, key=lambda c: c["clear_area_m2"], default=None)

        checks: dict[str, bool] = {}
        if best is not None:
            if min_clear_area_m2 is not None:
                checks["clear_area"] = best["clear_area_m2"] >= min_clear_area_m2
            if min_clear_width_mm is not None:
                checks["clear_width"] = best["clear_width_mm"] >= min_clear_width_mm
            if min_clear_height_mm is not None:
                checks["clear_height"] = best["clear_height_mm"] >= min_clear_height_mm
            if max_sill_height_mm is not None:
                checks["sill_height"] = best["sill_height_mm"] <= max_sill_height_mm

        passes = bool(checks) and all(checks.values())
        if best is None:
            reason = (
                "no window found bounding this sleeping room"
                if not windows
                else "no window's operable clear opening could be determined "
                "(missing operation-type or sill-elevation data)"
            )
        else:
            reason = None if passes else f"fails: {', '.join(k for k, ok in checks.items() if not ok)}"

        results.append({
            "check": "egress_window_opening",
            "code_ref": "CODE 9.9 (emergency escape and rescue opening)",
            "space_guid": space_guid,
            "space_name": space_name,
            "storey_name": storey_name or "—",
            "window_count": len(windows),
            "windows": candidates,
            "best_window": best,
            "required_clear_area_m2": min_clear_area_m2,
            "required_clear_width_mm": min_clear_width_mm,
            "required_clear_height_mm": min_clear_height_mm,
            "required_max_sill_height_mm": max_sill_height_mm,
            "checks": checks,
            "passes": passes,
            "reason": reason,
            "severity": "mandatory",
        })

    return results


_GARAGE_KW = frozenset(["garage", "carport", "car port", "parking", "vehicle"])


def _is_garage_space(space) -> bool:
    """Check whether an IfcSpace represents a garage/carport by name."""
    name = (
        getattr(space, "LongName", None)
        or getattr(space, "Name", None)
        or ""
    ).lower()
    return any(kw in name for kw in _GARAGE_KW)


def check_fire_separation(
    adjacency: IFCSpatialAdjacency,
    min_rating_min: float | None = None,
) -> list[dict]:
    """
    Evaluate party-wall fire separation against FireRating >= min_rating_min.

    ``min_rating_min`` comes from an explicit argument, else a
    BUILDING-CODE-PART9 rule for reference 9.10.9 on IfcWall. If neither
    supplies one, this returns an empty list -- no configured minimum means
    nothing to verify walls against, matching how a missing boundary
    precondition is already handled above rather than silently checking
    against a residential-default rating.

    Returns one result dict per party wall found.
    Walls with no FireRating declared are flagged as missing data.
    """
    if not adjacency.has_boundaries:
        return []

    if min_rating_min is None:
        try:
            from app.services.rules_service import RuleService

            for r in RuleService().list_by_ruleset("BUILDING-CODE-PART9"):
                if "9.10.9" in str(r.get("reference") or "") and str(r.get("target_ifc_class") or "") == "IfcWall":
                    val = r.get("check_value")
                    if val is not None and float(val) > 1.0:
                        min_rating_min = float(val)
                        break
        except Exception:
            pass
    if min_rating_min is None:
        return []
    required_min = min_rating_min

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
        passes = not missing_rating and numeric_rating is not None and numeric_rating >= required_min

        results.append(
            {
                "check": "fire_separation",
                "code_ref": "CODE 9.10.9",
                "wall_guid": wall_guid,
                "wall_name": wall_name,
                "adjacent_spaces": space_names,
                "fire_rating_raw": raw_rating,
                "fire_rating_min": numeric_rating,
                "required_min": required_min,
                "passes": passes,
                "missing_rating": missing_rating,
                "severity": "mandatory",
            }
        )

    return results


def check_garage_separation(adjacency: IFCSpatialAdjacency) -> dict:
    """
    Evaluate fire separation between attached garage and dwelling.

    Walls between garage and living space: FireRating ≥ 30 min.
    Doors between garage and living space: FireRating ≥ 20 min.

    Returns:
        {
          "garage_spaces_found": int,
          "results": [per-element check dicts],
          "warnings": [str],
        }
    """
    if not adjacency.has_boundaries:
        return {
            "garage_spaces_found": 0,
            "results": [],
            "warnings": ["No IfcRelSpaceBoundary data — garage separation check skipped."],
        }

    # ── Identify garage spaces ────────────────────────────────────────────────
    garage_guids: set[str] = set()
    garage_names: dict[str, str] = {}
    for sguid, data in adjacency._space_data.items():
        space = data["space"]
        if _is_garage_space(space):
            garage_guids.add(sguid)
            garage_names[sguid] = (
                getattr(space, "LongName", None)
                or getattr(space, "Name", None)
                or sguid
            )

    if not garage_guids:
        return {
            "garage_spaces_found": 0,
            "results": [],
            "warnings": [
                "No garage or carport spaces detected. "
                "Name the garage space 'Garage' or 'Carport' in the authoring tool."
            ],
        }

    # ── Door → spaces map (walls already exist in _wall_spaces) ───────────────
    door_to_spaces = adjacency.get_door_to_spaces()

    results: list[dict] = []
    warnings: list[str] = []

    def _space_label(sguid: str) -> str:
        d = adjacency._space_data.get(sguid, {})
        sp = d.get("space")
        if sp is None:
            return sguid
        return (
            getattr(sp, "LongName", None)
            or getattr(sp, "Name", None)
            or sguid
        )

    # ── Check walls ───────────────────────────────────────────────────────────
    for wall_guid, space_guids in adjacency._wall_spaces.items():
        garage_side = [g for g in space_guids if g in garage_guids]
        living_side = [g for g in space_guids if g not in garage_guids]
        if not garage_side or not living_side:
            continue

        # Resolve wall element
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
        missing = raw_rating is None
        passes = not missing and numeric_rating is not None and numeric_rating >= 30

        results.append({
            "check": "garage_separation",
            "code_ref": "CODE 9.10.14.2",
            "element_type": "Wall",
            "element_name": wall_name,
            "garage_space": garage_names.get(garage_side[0], garage_side[0]),
            "adjacent_space": _space_label(living_side[0]),
            "fire_rating_raw": raw_rating,
            "fire_rating_min": numeric_rating,
            "required_min": 30,
            "passes": passes,
            "missing_rating": missing,
            "severity": "mandatory",
        })

    # ── Check doors ───────────────────────────────────────────────────────────
    for door_guid, space_guids in door_to_spaces.items():
        garage_side = [g for g in space_guids if g in garage_guids]
        living_side = [g for g in space_guids if g not in garage_guids]
        if not garage_side or not living_side:
            continue

        try:
            door_el = adjacency.ifc_file.by_guid(door_guid)
        except Exception:
            door_el = None
        if door_el is None:
            continue

        door_name = getattr(door_el, "Name", None) or door_guid
        raw_rating, numeric_rating = _get_fire_rating(door_el)
        missing = raw_rating is None
        passes = not missing and numeric_rating is not None and numeric_rating >= 20

        results.append({
            "check": "garage_separation",
            "code_ref": "CODE 9.10.14.2",
            "element_type": "Door",
            "element_name": door_name,
            "garage_space": garage_names.get(garage_side[0], garage_side[0]),
            "adjacent_space": _space_label(living_side[0]),
            "fire_rating_raw": raw_rating,
            "fire_rating_min": numeric_rating,
            "required_min": 20,
            "passes": passes,
            "missing_rating": missing,
            "severity": "mandatory",
        })

    # ── Summary warnings ──────────────────────────────────────────────────────
    missing_count = sum(1 for r in results if r["missing_rating"])
    fail_count    = sum(1 for r in results if not r["passes"] and not r["missing_rating"])

    if not results:
        warnings.append(
            "Garage space(s) found but no shared walls or doors with adjacent spaces detected. "
            "Check that IfcRelSpaceBoundary data includes garage boundaries."
        )
    if missing_count:
        warnings.append(
            f"{missing_count} garage-separation element(s) have no FireRating declared "
            "(reference 9.10.14.2: walls >= 30 min, doors >= 20 min)."
        )
    if fail_count:
        warnings.append(
            f"{fail_count} garage-separation element(s) have insufficient fire rating."
        )

    return {
        "garage_spaces_found": len(garage_guids),
        "results": results,
        "warnings": warnings,
    }


def check_door_space_connection(adjacency: IFCSpatialAdjacency, ifc_file) -> list[dict]:
    """
    BIMGuard QA — a door should bound the number of modeled spaces consistent
    with its IsExternal classification: an interior door bounds exactly two
    spaces; an exterior door bounds exactly one (the other side is "outside",
    which is never modeled as an IfcSpace).

    Returns one record per IfcDoor in the file. Empty list if the file has no
    usable IfcRelSpaceBoundary data at all (mirrors how daylight/fire-separation
    already degrade for such files).
    """
    if not adjacency.has_boundaries:
        return []

    door_to_spaces = adjacency.get_door_to_spaces()

    space_names: dict[str, str] = {}
    try:
        for space in ifc_file.by_type("IfcSpace"):
            space_names[space.GlobalId] = (
                getattr(space, "LongName", None)
                or getattr(space, "Name", None)
                or space.GlobalId
            )
    except Exception:
        pass

    results: list[dict] = []
    try:
        doors = sorted(ifc_file.by_type("IfcDoor"), key=lambda d: d.GlobalId)
    except Exception:
        doors = []

    for door in doors:
        guid = door.GlobalId
        space_guids = door_to_spaces.get(guid, [])
        connected_names = [space_names.get(sg, sg) for sg in space_guids]
        has_data = len(space_guids) > 0

        is_external = _is_exterior_door(door)
        if is_external is None:
            expected_count = None
            status = "indeterminate"
            passes = None
            reason = "The door could not be classified reliably as interior or exterior (no IsExternal data)."
        else:
            expected_count = 1 if is_external else 2
            if not has_data:
                status = "missing_boundary_data"
                passes = False
                reason = "No IfcRelSpaceBoundary relationship was found for this door."
            else:
                passes = len(space_guids) == expected_count
                status = "pass" if passes else "fail"
                reason = None if passes else (
                    f"Connects {len(space_guids)} space(s); expected {expected_count}."
                )

        # Declared-vs-observed mismatch: a door explicitly labeled interior
        # (IsExternal=False) should bound two spaces; if it only bounds one,
        # that's worth flagging — either the door is mislabeled (as happened
        # in this exact test model) or boundary data is missing on one side.
        # Deliberately one-directional per the request that introduced this:
        # doesn't flag the opposite case (labeled exterior, bounds two spaces).
        interior_single_space_mismatch = (is_external is False) and len(space_guids) == 1

        results.append({
            "door_guid": guid,
            "door_name": getattr(door, "Name", None) or getattr(door, "Tag", None) or guid,
            "is_external": is_external,
            "connected_space_guids": space_guids,
            "connected_space_names": connected_names,
            "connected_space_count": len(space_guids),
            "expected_count": expected_count,
            "passes": passes,
            "has_data": has_data,
            "status": status,
            "reason": reason,
            "interior_single_space_mismatch": interior_single_space_mismatch,
        })

    return results
