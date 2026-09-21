"""Room identity and element-to-room links.

Answers two questions the rest of the engine keeps needing:

* *What kind of room is this space?*  ``RoomIndex`` reads every ``IfcSpace`` once
  and types it through ``app.modules.room_types``.
* *Which rooms does this element connect to?*  ``ElementRoomLinker`` resolves any
  element -- door, window, wall, slab, covering -- to the rooms it bounds, and
  says HOW it knows.

That second answer is graded, because the evidence behind it varies enormously
between models. A link is one of:

    self         the element is itself an IfcSpace
    boundary     an authored IfcRelSpaceBoundary names the element
    containment  the element is contained in the IfcSpace directly
    host_wall    a door/window inherits the rooms of the wall it fills, narrowed
                 to the ones its own geometry actually touches
    geometric_bbox   bounding-box contact only -- NOT usable (see below)

The first four are *usable*: a rule may be scoped by them. ``geometric_bbox`` is
not. Measured on a real residential model that ships rooms but no space
boundaries, bounding-box contact linked one door to six rooms and one wall to
twenty-two, so scoping "bedroom doors" by it would put half the doors of the
building in a bedroom rule. An element that only has that evidence is reported
as unresolved (which the comparator turns into an UNDETERMINED predicate: kept
in scope, flagged) rather than quietly trusted.

Nothing here decides pass or fail. It hands the reader facts and provenance; the
comparator does the comparing.
"""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass

from app.modules.room_types import (
    ROOM_TYPES,
    UNKNOWN_ROOM_TYPE,
    NameSuggestion,
    classify_room,
    closest_room_types,
    name_mentions,
    suggest_name_correction,
)

from .ifc_spatial import (
    BOUNDARY_SOURCE_GEOMETRIC,
    BOUNDARY_SOURCE_MODEL,
    _get_storey_name,
    boxes_touch,
)

logger = logging.getLogger("bimguard.rooms")

try:
    import ifcopenshell.util.element

    _IFC_AVAILABLE = True
except ImportError:
    _IFC_AVAILABLE = False

try:
    from .ifc_penetrations import resolve_hosts
except ImportError:  # pragma: no cover - penetrations module is a sibling
    resolve_hosts = None

# ── Link provenance ───────────────────────────────────────────────────────────

SOURCE_SELF = "self"
SOURCE_BOUNDARY = "boundary"
SOURCE_CONTAINMENT = "containment"
SOURCE_HOST_WALL = "host_wall"
SOURCE_GEOMETRIC = "geometric_bbox"
SOURCE_NONE = "none"

#: Sources a rule may be scoped or counted by. ``geometric_bbox`` is excluded on
#: purpose -- see the module docstring.
USABLE_SOURCES = frozenset(
    {SOURCE_SELF, SOURCE_BOUNDARY, SOURCE_CONTAINMENT, SOURCE_HOST_WALL}
)

_NOTE_UNLINKED = (
    "no room could be linked to this element (no space boundary, containment "
    "or host-wall relationship names one)"
)
_NOTE_COARSE = (
    "room links were only inferred from bounding-box contact, which is too "
    "coarse to scope a rule by room; export the model with space boundaries"
)

#: How close (mm) a door/window must be to a candidate room's bounding box for
#: the room to count as one it opens onto. Looser than the 200 mm the model-wide
#: fallback uses, because the candidates are already restricted to the rooms the
#: host wall bounds, and a window may sit on the far face of a thick wall.
_HOST_PROXIMITY_MM = 500.0

#: Property name (separators stripped, lower-case) -> what it resolves to.
#: ``types`` / ``names`` describe the element's connected rooms (an IfcSpace's
#: own, for a space); the count keys apply to IfcSpace elements only.
_COUNT_CLASSES: dict[str, tuple[str, ...]] = {
    "DoorCount": ("IfcDoor",),
    "WindowCount": ("IfcWindow",),
    "WallCount": ("IfcWall",),
    "SlabCount": ("IfcSlab",),
}
_COUNT_LABELS = {
    "DoorCount": "doors",
    "WindowCount": "windows",
    "WallCount": "walls",
    "SlabCount": "slabs",
}

ROOM_DERIVED_PROPERTIES: dict[str, str] = {
    "roomtype": "types",
    "roomtypes": "types",
    "connectedroomtype": "types",
    "connectedroomtypes": "types",
    "roomname": "names",
    "roomnames": "names",
    "connectedroomname": "names",
    "connectedroomnames": "names",
    "doorcount": "DoorCount",
    "windowcount": "WindowCount",
    "wallcount": "WallCount",
    "slabcount": "SlabCount",
}

#: Existing door-connection property names (``ifc_reader.__init__`` resolves
#: them for doors through ``check_door_space_connection``). Listed here so a
#: rule that asks for them on ANY other element class also gets room context.
ROOM_LINK_PROPERTIES = frozenset(
    {
        "connectedspaces",
        "spaceconnection",
        "connectedspacenames",
        "doorconnectedspaces",
        "connectedspacecount",
        "spaceconnectioncount",
        "numberofconnectedspaces",
        "connectedspacescount",
    }
)


# ── Rooms ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RoomInfo:
    """One ``IfcSpace``, identified and typed."""

    guid: str
    name: str
    types: tuple[str, ...]
    type_source: str | None
    storey: str | None
    #: Set when the name looks like a misspelling of a known room word. The name
    #: itself is never changed; this is a proposal for the user.
    suggestion: NameSuggestion | None = None

    @property
    def is_classified(self) -> bool:
        return UNKNOWN_ROOM_TYPE not in self.types


def _space_text_candidates(space) -> list[tuple[str, str | None]]:
    """Text sources for typing a space, best first.

    An explicit category or occupancy property beats a free-text name, which is
    why the names come last. Any of them can be absent.
    """
    candidates: list[tuple[str, str | None]] = []
    psets: dict = {}
    if _IFC_AVAILABLE:
        try:
            psets = ifcopenshell.util.element.get_psets(space, psets_only=False)
        except Exception:
            psets = {}
    for pset_name, prop in (
        ("Pset_SpaceCommon", "Category"),
        ("Pset_SpaceOccupancyRequirements", "OccupancyType"),
    ):
        props = psets.get(pset_name)
        value = props.get(prop) if isinstance(props, dict) else None
        candidates.append((f"{pset_name}.{prop}", None if value is None else str(value)))
    candidates.append(("ObjectType", getattr(space, "ObjectType", None)))
    candidates.append(("LongName", getattr(space, "LongName", None)))
    candidates.append(("Name", getattr(space, "Name", None)))
    return candidates


def _storey_of(space) -> str | None:
    """Return the name of the storey a space is on.

    Exporters put a space under its storey in one of two ways -- contained in it
    (IfcRelContainedInSpatialStructure) or aggregated by it (IfcRelAggregates) --
    and ``_get_storey_name`` only follows the first.
    """
    name = _get_storey_name(space)
    if name:
        return name
    try:
        for rel in getattr(space, "Decomposes", None) or []:
            parent = getattr(rel, "RelatingObject", None)
            if parent is not None and parent.is_a("IfcBuildingStorey"):
                return getattr(parent, "Name", None)
    except Exception:
        pass
    return None


def _display_name(space) -> str:
    return (
        getattr(space, "LongName", None)
        or getattr(space, "Name", None)
        or space.GlobalId
    )


def _rooms(count: int) -> str:
    return f"{count} room" if count == 1 else f"{count} rooms"


def _typo_message(group: dict) -> str:
    """Return the warning text for one group of identically-named rooms."""
    subject = (
        f"Room name '{group['room_name']}'"
        if group["count"] == 1
        else f"Room name '{group['room_name']}' ({_rooms(group['count'])})"
    )
    return (
        f"{subject} looks like a misspelling of '{group['suggestion']}'. "
        f"Suggested name: '{group['suggested_name']}'. "
        "The name has been left as written, so until it is changed the room is "
        "treated as a room of unknown type."
    )


class RoomIndex:
    """Every ``IfcSpace`` in a model, identified and typed once."""

    def __init__(self, ifc_file) -> None:
        self._rooms: dict[str, RoomInfo] = {}
        self._entities: dict[str, object] = {}
        try:
            spaces = ifc_file.by_type("IfcSpace") if ifc_file is not None else []
        except Exception:
            spaces = []
        for space in spaces:
            guid = getattr(space, "GlobalId", None)
            if not guid:
                continue
            types, source = classify_room(_space_text_candidates(space))
            name = str(_display_name(space))
            self._rooms[guid] = RoomInfo(
                guid=guid,
                name=name,
                types=tuple(types),
                type_source=source,
                storey=_storey_of(space),
                suggestion=(
                    suggest_name_correction(name) if UNKNOWN_ROOM_TYPE in types else None
                ),
            )
            self._entities[guid] = space

    def __contains__(self, guid: str) -> bool:
        return guid in self._rooms

    def __len__(self) -> int:
        return len(self._rooms)

    def get(self, guid: str) -> RoomInfo | None:
        return self._rooms.get(guid)

    def entity(self, guid: str):
        return self._entities.get(guid)

    def all(self) -> list[RoomInfo]:
        return list(self._rooms.values())

    # ── Naming warnings ───────────────────────────────────────────────────────
    #
    # Room names are whatever the model's author typed and are never altered.
    # When one looks like a misspelling of a known room word the engine cannot
    # type the room, and rather than guess it says so and proposes a fix.

    def typo_groups(self) -> list[dict]:
        """Group the suspected misspellings by name, most rooms first.

        A model with 32 identical flats has 32 rooms called "BADROOM 1"; one
        warning that says so is worth more than 32 copies of it.
        """
        groups: dict[tuple[str, str], dict] = {}
        for room in self._rooms.values():
            suggestion = room.suggestion
            if suggestion is None:
                continue
            group = groups.setdefault(
                (room.name, suggestion.keyword),
                {
                    "room_name": room.name,
                    "found": suggestion.found,
                    "suggestion": suggestion.keyword,
                    "room_type": suggestion.room_type,
                    "suggested_name": suggestion.suggested_name,
                    "count": 0,
                },
            )
            group["count"] += 1
        return sorted(groups.values(), key=lambda g: (-g["count"], g["room_name"]))

    def warning_messages(self) -> list[str]:
        """One human-readable warning per distinct suspected misspelling."""
        return [_typo_message(g) for g in self.typo_groups()]

    def scope_miss_warnings(self, predicate: dict | None) -> list[str]:
        """Explain each room a rule's scope names that no room in the model matches.

        Only the predicates that need a room to exist are checked
        (``room_type_any_of`` / ``room_type_all_of`` / ``room_name_any_of``);
        ``room_type_none_of`` is satisfied by an absent room. Each message says
        what was looked for, what the model has instead, and -- where the
        model's spelling or the rule's looks like a typo -- what to change.
        """
        messages: list[str] = []
        for key in ("room_type_any_of", "room_type_all_of", "room_name_any_of"):
            wanted = (predicate or {}).get(key)
            if wanted is None:
                continue
            for label in wanted if isinstance(wanted, list) else [wanted]:
                label = str(label).strip()
                if label and not self._matches_a_room(key, label):
                    messages.append(self._explain_miss(key, label))
        return messages

    def _matches_a_room(self, key: str, label: str) -> bool:
        cf = label.casefold()
        if key == "room_name_any_of":
            return any(cf in room.name.casefold() for room in self._rooms.values())
        if cf in ROOM_TYPES:
            return any(cf in room.types for room in self._rooms.values())
        return any(name_mentions(room.name, label) for room in self._rooms.values())

    def _explain_miss(self, key: str, label: str) -> str:
        cf = label.casefold()
        parts = [f"Rule scope {key} names '{label}', but no room in this model matches it."]

        # The model's rooms may be spelt wrongly ("BADROOM" for "bedroom").
        likely = [g for g in self.typo_groups() if cf in (g["room_type"], g["suggestion"])]
        if likely:
            shown = "; ".join(
                f"'{g['room_name']}' ({_rooms(g['count'])}) -> '{g['suggested_name']}'"
                for g in likely[:4]
            )
            parts.append(f"Room names that look like misspellings of '{label}': {shown}.")

        # ...or the rule's own label may be.
        if not likely and cf not in ROOM_TYPES:
            near = [f"'{t}'" for t in closest_room_types(label)]
            # Compared without regard to case, but reported as the model spells it.
            by_folded = {room.name.casefold(): room.name for room in self._rooms.values()}
            near += [
                f"'{by_folded[n]}'"
                for n in difflib.get_close_matches(cf, sorted(by_folded), n=3, cutoff=0.6)
            ]
            if near:
                parts.append(f"Did you mean: {', '.join(near)}?")

        if not likely:
            typed = sorted({t for r in self._rooms.values() for t in r.types} - {UNKNOWN_ROOM_TYPE})
            if typed:
                parts.append(f"Room types found in this model: {', '.join(typed)}.")
            unnamed = sorted({r.name for r in self._rooms.values() if not r.is_classified})
            if unnamed:
                sample = ", ".join(f"'{n}'" for n in unnamed[:6])
                more = f" and {len(unnamed) - 6} more" if len(unnamed) > 6 else ""
                parts.append(f"Rooms with names not matched to a type: {sample}{more}.")
        return " ".join(parts)


# ── Element -> rooms ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ElementRoomLinks:
    """The rooms one element connects to, and the evidence for saying so."""

    rooms: tuple[RoomInfo, ...] = ()
    source: str = SOURCE_NONE
    note: str | None = None

    @property
    def usable(self) -> bool:
        """Whether a rule may be scoped by these links."""
        return bool(self.rooms) and self.source in USABLE_SOURCES


_UNLINKED = ElementRoomLinks(note=_NOTE_UNLINKED)


class ElementRoomLinker:
    """Resolve any element to the rooms it connects to.

    Built once per loaded model and shared by every rule, since the same door is
    asked about by every rule that targets doors. ``links_for`` is memoised.
    """

    def __init__(
        self,
        adjacency,
        ifc_file,
        geometry_extractor=None,
        room_index: RoomIndex | None = None,
    ) -> None:
        self._adjacency = adjacency
        self._ifc_file = ifc_file
        self._extractor = geometry_extractor
        self.rooms = room_index if room_index is not None else RoomIndex(ifc_file)
        self._cache: dict[str, ElementRoomLinks] = {}
        self._space_boxes: dict[str, dict | None] = {}
        self._space_elements: dict[str, dict[str, set[str]]] | None = None
        self._coverage: dict[str, tuple[int, int]] = {}

    # ── Public ────────────────────────────────────────────────────────────────

    def links_for(self, element) -> ElementRoomLinks:
        """Return the rooms ``element`` connects to (memoised by GlobalId)."""
        guid = getattr(element, "GlobalId", None)
        if not guid:
            return _UNLINKED
        cached = self._cache.get(guid)
        if cached is not None:
            return cached
        try:
            links = self._resolve(element, guid)
        except Exception as exc:
            logger.debug("Room link resolution failed for %s: %s", guid, exc)
            links = _UNLINKED
        self._cache[guid] = links
        return links

    def space_counts(self, space_guid: str) -> dict | None:
        """Count the doors/windows/walls/slabs that bound a room.

        Returns ``{"counts": {...}, "coverage": {key: (linked, total)}}``, or
        None when the room cannot be counted at all -- no usable evidence that
        anything was ever linked to it. None, never zeros: a room the export
        forgot about has an unknown number of windows, not none.
        """
        inverted = self._ensure_inversion()
        if space_guid not in inverted and not self._has_model_boundary(space_guid):
            return None
        per_class = inverted.get(space_guid, {})
        return {
            "counts": {key: len(per_class.get(key, ())) for key in _COUNT_CLASSES},
            "coverage": dict(self._coverage),
        }

    # ── Resolution tiers ──────────────────────────────────────────────────────

    def _resolve(self, element, guid: str) -> ElementRoomLinks:
        if element.is_a("IfcSpace"):
            room = self.rooms.get(guid)
            return ElementRoomLinks((room,), SOURCE_SELF) if room else _UNLINKED

        by_space = self._adjacency.get_element_spaces(guid) if self._adjacency else {}

        # 1. The model's own space boundaries: authored, authoritative.
        modelled = self._rooms_for(
            [g for g, src in by_space.items() if src == BOUNDARY_SOURCE_MODEL]
        )
        if modelled:
            return ElementRoomLinks(modelled, SOURCE_BOUNDARY)

        # 2. Direct containment in an IfcSpace.
        contained = self._contained_rooms(element)
        if contained:
            return ElementRoomLinks(contained, SOURCE_CONTAINMENT)

        # 3. A door/window inherits from the wall it fills.
        inherited = self._host_rooms(element)
        if inherited:
            return ElementRoomLinks(inherited, SOURCE_HOST_WALL)

        # 4. Bounding-box contact: recorded, but not usable.
        coarse = self._rooms_for(
            [g for g, src in by_space.items() if src == BOUNDARY_SOURCE_GEOMETRIC]
        )
        if coarse:
            return ElementRoomLinks(coarse, SOURCE_GEOMETRIC, _NOTE_COARSE)

        return _UNLINKED

    def _rooms_for(self, space_guids: list[str]) -> tuple[RoomInfo, ...]:
        """Return room records for these guids.

        Anything that is not an ``IfcSpace`` (an ``IfcExternalSpatialElement``
        bounding the outside) is not a room. Ordered by name, so the rooms read
        the same way in every finding ("Bedroom 1, Hallway"), with the guid as
        the tie-break for two rooms sharing a name.
        """
        rooms = [r for r in (self.rooms.get(g) for g in space_guids) if r is not None]
        return tuple(sorted(rooms, key=lambda r: (r.name.casefold(), r.guid)))

    def _contained_rooms(self, element) -> tuple[RoomInfo, ...]:
        found: list[str] = []
        for rel in getattr(element, "ContainedInStructure", None) or []:
            container = getattr(rel, "RelatingStructure", None)
            if container is not None and container.is_a("IfcSpace"):
                found.append(container.GlobalId)
        return self._rooms_for(found)

    def _host_rooms(self, element) -> tuple[RoomInfo, ...]:
        """Rooms a door/window opens onto, via the wall it sits in.

        A wall can bound many rooms -- a long corridor wall bounds every room
        along it -- so taking all of the host's rooms would credit a window to
        rooms it never touches. The candidates are therefore narrowed to those
        whose bounding box the element is actually near.
        """
        if resolve_hosts is None or self._adjacency is None:
            return ()
        try:
            hosts = resolve_hosts(element)
        except Exception:
            return ()
        for host in hosts:
            host_guid = getattr(host, "GlobalId", None)
            if not host_guid:
                continue
            candidates = [
                g
                for g, src in self._adjacency.get_element_spaces(host_guid).items()
                if src == BOUNDARY_SOURCE_MODEL and g in self.rooms
            ]
            if not candidates:
                continue
            narrowed = self._narrow_by_proximity(element, candidates)
            if narrowed:
                return self._rooms_for(narrowed)
        return ()

    def _narrow_by_proximity(self, element, candidates: list[str]) -> list[str]:
        if self._extractor is not None:
            element_box = self._box(element)
            if element_box is not None:
                boxes = {g: self._space_box(g) for g in candidates}
                if all(b is not None for b in boxes.values()):
                    return [
                        g
                        for g, b in boxes.items()
                        if boxes_touch(b, element_box, _HOST_PROXIMITY_MM)
                    ]
        # Geometry is unavailable, so proximity cannot arbitrate. A host that
        # bounds at most two rooms is unambiguous enough to inherit whole; a
        # host bounding more is not, and yields no link rather than a guess.
        return candidates if len(candidates) <= 2 else []

    def _box(self, element) -> dict | None:
        try:
            return self._extractor.get_bounding_box(element)
        except Exception:
            return None

    def _space_box(self, space_guid: str) -> dict | None:
        if space_guid not in self._space_boxes:
            entity = self.rooms.entity(space_guid)
            self._space_boxes[space_guid] = self._box(entity) if entity else None
        return self._space_boxes[space_guid]

    # ── Room -> elements (for counts) ─────────────────────────────────────────

    def _has_model_boundary(self, space_guid: str) -> bool:
        """Whether the model itself authored any boundary for this room."""
        if self._adjacency is None:
            return False
        data = self._adjacency._space_data.get(space_guid)
        return bool(data) and any(
            b.get("source") == BOUNDARY_SOURCE_MODEL for b in data["boundaries"]
        )

    def _ensure_inversion(self) -> dict[str, dict[str, set[str]]]:
        """Invert element->rooms into room->elements, once.

        Also measures how much of each class is linked at all, so a count can be
        qualified.
        """
        if self._space_elements is not None:
            return self._space_elements
        inverted: dict[str, dict[str, set[str]]] = {}
        coverage: dict[str, tuple[int, int]] = {}
        for count_key, ifc_types in _COUNT_CLASSES.items():
            seen: set[str] = set()
            linked = 0
            for ifc_type in ifc_types:
                try:
                    elements = self._ifc_file.by_type(ifc_type)
                except Exception:
                    continue
                for el in elements:
                    guid = getattr(el, "GlobalId", None)
                    if not guid or guid in seen:
                        continue
                    seen.add(guid)
                    links = self.links_for(el)
                    if not links.usable:
                        continue
                    linked += 1
                    for room in links.rooms:
                        inverted.setdefault(room.guid, {}).setdefault(
                            count_key, set()
                        ).add(guid)
            coverage[count_key] = (linked, len(seen))
        self._space_elements = inverted
        self._coverage = coverage
        return inverted


# ── Reader-facing context ─────────────────────────────────────────────────────


def _group_of(room: RoomInfo) -> dict:
    suggestion = room.suggestion
    return {
        "room_name": room.name,
        "suggestion": suggestion.keyword,
        "suggested_name": suggestion.suggested_name,
    }


def room_context(element, linker: ElementRoomLinker, include_counts: bool = False) -> dict:
    """Room facts for one element, in the shape the reader threads through.

    ``rooms`` / ``room_guids`` / ``room_types`` are None (not empty) when the
    links are not usable, so the comparator reads them as unresolved -- "we
    found no rooms" and "this element touches no rooms" are different claims,
    and an exporter that omits the relationships makes the first.

    ``room_types`` is the de-duplicated union across the connected rooms and
    includes ``UNKNOWN_ROOM_TYPE`` when any room could not be typed.
    """
    links = linker.links_for(element)
    context: dict = {
        "link_source": links.source,
        "link_note": links.note,
        "rooms": None,
        "room_guids": None,
        "room_types": None,
        "space_counts": None,
        "name_warnings": [],
    }
    if links.usable:
        context["name_warnings"] = [
            _typo_message({**_group_of(room), "count": 1}) for room in links.rooms if room.suggestion
        ]
        types: list[str] = []
        for room in links.rooms:
            for room_type in room.types:
                if room_type not in types:
                    types.append(room_type)
        context["rooms"] = [r.name for r in links.rooms]
        context["room_guids"] = [r.guid for r in links.rooms]
        context["room_types"] = types
    if include_counts:
        try:
            if element.is_a("IfcSpace"):
                context["space_counts"] = linker.space_counts(element.GlobalId)
        except Exception as exc:
            logger.debug("Space counts failed for %s: %s", element, exc)
    return context


def room_derived_value(prop_key_name: str, room: dict | None) -> tuple[object, dict]:
    """Return ``(value, detail)`` for a room-derived property, or ``(None, {})``.

    None means the links could not answer -- never 0 and never "" -- so the
    property reads as missing data rather than as a compliant-looking blank.
    """
    kind = ROOM_DERIVED_PROPERTIES.get(prop_key_name)
    if kind is None or not room:
        return None, {}

    detail: dict = {
        "link_source": room.get("link_source"),
        "room_guids": room.get("room_guids"),
        "warnings": [],
    }

    if kind == "types":
        values = room.get("room_types")
        return (", ".join(values), detail) if values else (None, {})
    if kind == "names":
        values = room.get("rooms")
        return (", ".join(values), detail) if values else (None, {})

    counts = room.get("space_counts")
    if not counts:
        return None, {}
    linked, total = counts["coverage"].get(kind, (0, 0))
    if total and linked < total:
        detail["warnings"].append(
            f"only {linked} of {total} {_COUNT_LABELS[kind]} in this model are "
            f"linked to a room, so a {kind} of 0 may reflect missing room "
            "relationships rather than a room without any"
        )
    return counts["counts"][kind], detail
