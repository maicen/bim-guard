"""How far a rule can be trusted to run against a real IFC model.

Reliability here means one thing: **if the value is present, is it true?**

* **High** -- the value is stored in the file, on a path with only one source: an
  IFC attribute the schema itself defines, the element's own entity type, or an
  explicit stored relationship (contained-in-storey, fills/voids an opening,
  defined-by-type) that BIMGuard reads without any interpretation. A person (or
  the authoring tool) put it there; BIMGuard cannot get it wrong.
* **Medium** -- the value lives in a standard property set. It is still real,
  authored data -- true if found -- but whether the model has it at all depends
  on the authoring tool exporting it, and BIMGuard has to search for it by name.
* **Low** -- either nothing in the model actually holds this value, so BIMGuard's
  own geometry engine estimates it (an estimate can be wrong even when it looks
  plausible), or the value is genuinely not standard data at all (a project's
  own custom field, a manufacturer field, a user-defined type).

Every grade below cites a concrete source for that reason, not a guess at what
the name suggests:

1. The live IFC schema (IFC2X3 / IFC4 / IFC4X3, via ifcopenshell) -- is this a
   defined attribute of a real building-element class?
2. The local buildingSMART Data Dictionary (bSDD) -- is this a defined property
   of a real, named property set?
3. ``app.modules.ifc_reader.ifc_geometry._GEOMETRY_PROPERTY_MAP`` -- the exact
   list of property names BIMGuard's own geometry engine can compute when
   nothing stored resolves them (``get_geometry_value``, invoked by the property
   resolver in ``app.modules.ifc_reader`` only as its last-resort pass, after
   every stored-attribute and property-set lookup has failed).
4. A short, explicit list of categories named in the project's own reliability
   reference image (clear-opening/clearance dimensions, escape/smoke compliance,
   manufacturer data, user-defined types) -- not inferred, just recorded here.

Anything not covered by 1-4 has no known source and grades low rather than
being assumed safe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, Optional

Level = Literal["high", "medium", "low"]

_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class Assessment:
    """The grade for one property (or, from :func:`assess_rule`, one rule)."""

    level: Level
    category: str
    reason: str
    #: Whether the buildingSMART Data Dictionary defines this property; None when it can't be checked.
    bsdd_defined: Optional[bool] = None


def _key(text: Optional[str]) -> str:
    """Lower-case and strip everything but letters and digits, so ``Fire Rating`` == ``FireRating``."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


# -- Source 1: the live IFC schema --------------------------------------------------------------------

#: Building-element classes checked for attribute membership. Not exhaustive of the IFC schema --
#: a name true here is definitely a real attribute; a name false here may still be an attribute of a
#: class not listed (grading then falls through to the other sources rather than claiming "no").
_SCHEMA_CLASSES = (
    "IfcDoor", "IfcDoorType", "IfcWindow", "IfcWindowType", "IfcWall", "IfcWallType", "IfcSlab",
    "IfcStair", "IfcStairFlight", "IfcRailing", "IfcRoof", "IfcColumn", "IfcBeam", "IfcCovering",
    "IfcSpace", "IfcBuildingStorey", "IfcBuildingElement", "IfcElement", "IfcProduct", "IfcRoot",
)  # fmt: skip
_SCHEMA_NAMES = ("IFC2X3", "IFC4", "IFC4X3_ADD2")


@lru_cache(maxsize=1)
def _ifc_schema_attributes() -> frozenset[str]:
    """Normalised names of every attribute the live IFC schemas declare on ``_SCHEMA_CLASSES``.

    Source: ``ifcopenshell.ifcopenshell_wrapper``'s own compiled EXPRESS schema -- the same
    definition ifcopenshell itself parses files against. Empty if ifcopenshell isn't importable.
    """
    try:
        import ifcopenshell.ifcopenshell_wrapper as wrapper
    except Exception:  # noqa: BLE001 - grading must never fail just because ifcopenshell isn't installed
        return frozenset()

    names: set[str] = set()
    for schema_name in _SCHEMA_NAMES:
        try:
            schema = wrapper.schema_by_name(schema_name)
        except Exception:  # noqa: BLE001 - a schema variant not built into this ifcopenshell
            continue
        for class_name in _SCHEMA_CLASSES:
            try:
                declaration = schema.declaration_by_name(class_name)
            except Exception:  # noqa: BLE001 - class not defined in this schema version
                continue
            names.update(_key(attribute.name()) for attribute in declaration.all_attributes())
    return frozenset(names)


#: BIMGuard's own names for reading an explicit stored IFC relationship -- never geometry.
#: Verified against ifcopenshell.util.element: get_container() reads IfcRelContainedInSpatialStructure
#: (walking IfcRelAggregates for an indirect container); FillsVoids/VoidsElements are the inverse
#: attributes of IfcRelFillsElement/IfcRelVoidsElement; get_type() reads IfcRelDefinesByType.
_RELATIONSHIP_LOOKUPS: dict[str, str] = {
    "storeyglobalid": "IfcRelContainedInSpatialStructure (the element's spatial container)",
    "storeyname": "IfcRelContainedInSpatialStructure (the element's spatial container)",
    "hostglobalid": "IfcRelVoidsElement (the wall/slab the opening this element fills belongs to)",
    "hostifcclass": "IfcRelVoidsElement (the wall/slab the opening this element fills belongs to)",
    "openingglobalid": "IfcRelFillsElement (the opening this element fills)",
    "openingifcclass": "IfcRelFillsElement (the opening this element fills)",
    "openingelement": "IfcRelFillsElement (the opening this element fills)",
    "ifcopeningelement": "IfcRelFillsElement (the opening this element fills)",
    "fillsvoids": "IfcRelFillsElement (the opening this element fills)",
    "fillsopening": "IfcRelFillsElement (the opening this element fills)",
    "hostelement": "IfcRelVoidsElement (the wall/slab the opening this element fills belongs to)",
    "typeglobalid": "IfcRelDefinesByType (the element's type object)",
    "typename": "IfcRelDefinesByType (the element's type object)",
    "typeobject": "IfcRelDefinesByType (the element's type object)",
    "elementtype": "IfcRelDefinesByType (the element's type object)",
    "istypedby": "IfcRelDefinesByType (the element's type object)",
    "relatingtype": "IfcRelDefinesByType (the element's type object)",
    "typeassignmentcount": "IfcRelDefinesByType (the type objects assigned to the element)",
    "typecount": "IfcRelDefinesByType (the type objects assigned to the element)",
    "numberoftypes": "IfcRelDefinesByType (the type objects assigned to the element)",
    "typeassignments": "IfcRelDefinesByType (the type objects assigned to the element)",
    # "WindowType", "IfcDoorStyle", ...: the reader answers these for any
    # element class; the door/window spellings are the ones rules use.
    **{
        f"{prefix}{cls}{suffix}": "IfcRelDefinesByType (the element's type object)"
        for cls in ("door", "window")
        for prefix in ("", "ifc")
        for suffix in ("type", "style")
    },
    "placementmatrix": "IfcLocalPlacement (the element's own placement)",
}

# -- Source 2: bSDD (property-set membership) ---------------------------------------------------------

#: Pseudo property sets the extractor and rule form use for things that are not property sets at all.
_ATTRIBUTE_PSETS = frozenset(
    {"", "attributes", "attribute", "ifcattributes", "geometry", "relationships", "relationship", "quantities"}
)


@lru_cache(maxsize=1)
def _property_set_members() -> dict[str, frozenset[str]]:
    """Every bSDD property-set name mapped to the properties it actually contains.

    A pset+property *pair* lookup, not two independent existence checks -- ``Pset_DoorCommon``
    being real, and some property being real, does not mean that property is IN that set. This
    is what catches an invented name like ``Qto_DoorBaseQuantities.QtoWidth``: the set is real,
    ``QtoWidth`` is not one of its members (the real name is ``Width``). Empty when bSDD isn't loadable.
    """
    try:
        from app.services.bsdd_ontology_repository import get_bsdd_ontology_repository

        return get_bsdd_ontology_repository().known_property_set_members()
    except Exception:  # noqa: BLE001 - grading must never fail just because bSDD isn't loadable
        return {}


@lru_cache(maxsize=1)
def _bsdd_property_names() -> frozenset[str]:
    """Normalised names of every property the local bSDD dictionary defines (empty if unavailable)."""
    try:
        from app.services.bsdd_ontology_repository import get_bsdd_ontology_repository

        return get_bsdd_ontology_repository().known_property_names()
    except Exception:  # noqa: BLE001 - grading must never fail just because bSDD isn't loadable
        return frozenset()


# -- Source 3: BIMGuard's own geometry engine -----------------------------------------------------

@lru_cache(maxsize=1)
def _geometry_computed_names() -> frozenset[str]:
    """Normalised property names BIMGuard's geometry engine can compute (empty if the module can't be read).

    Reads the key set of ``_GEOMETRY_PROPERTY_MAP`` directly from
    ``app.modules.ifc_reader.ifc_geometry`` -- the actual last-resort fallback table the property
    resolver (``app.modules.ifc_reader``, Pass 7) consults, not a separate guess at the same list.
    Its keys are already normalised (lower-case, no separators).
    """
    try:
        from app.modules.ifc_reader.ifc_geometry import _GEOMETRY_PROPERTY_MAP

        return frozenset(_GEOMETRY_PROPERTY_MAP)
    except Exception:  # noqa: BLE001 - grading must never fail just because that module can't be read
        return frozenset()


# -- Source 4: named directly in the project's reliability reference image ---------------------------

#: (category, reason, pattern), checked only after nothing above resolved the name. Quotes the image's
#: own five Low examples plus the pattern for a user-defined enum value -- not an inferred keyword list.
_NAMED_LOW_CATEGORIES: tuple[tuple[str, str, "re.Pattern[str]"], ...] = (
    (
        "user_defined",
        'Named as the project\'s "user-defined" example: its meaning is set per project, not by IFC.',
        re.compile(r"userdefined"),
    ),
    (
        "manufacturer",
        'Named as the project\'s "manufacturer data" example: rarely filled in consistently.',
        re.compile(r"manufacturer|modellabel|modelreference|articlenumber"),
    ),
    (
        "derived",
        'Named as the project\'s "clear opening dimensions" example: this is what the geometry-engine '
        "clearance check computes, not a stored value.",
        re.compile(r"clear(opening|width|height|depth|ance)"),
    ),
    (
        "contextual",
        'Named as the project\'s "escape compliance / smoke protection" example: not IFC data.',
        re.compile(r"escapecompliance|smokeprotection|smokestop"),
    ),
)

_REASONS = {
    "ifc_class": "The element's own IFC entity type: this is what it is, not something that could be missing or wrong.",
    "schema_attribute": (
        "A direct IFC attribute -- defined by the IFC schema itself and read straight from the file, "
        "never calculated."
    ),
    "quantity": (
        "A standard IFC quantity (Qto_...): exported by the authoring tool as a stored value, not "
        "computed by BIMGuard."
    ),
    "property_set": (
        "A standard property set (buildingSMART Data Dictionary): true if found, because it was "
        "authored, not guessed -- but many models don't export it."
    ),
    "bsdd_defined": (
        "Defined in the buildingSMART Data Dictionary but not a core IFC attribute: true if found, "
        "but only as complete as the model's authoring."
    ),
    "custom_pset_name": (
        "Named like a standard property set but not in the buildingSMART dictionary, so it is treated "
        "as a project-specific one that may be missing or hold anything."
    ),
    "unrecognised": (
        "Not found in the IFC schema, the buildingSMART Dictionary, or BIMGuard's own geometry engine "
        "-- there is no known source for this value."
    ),
}


def _geometry_reason(name: str) -> str:
    try:
        from app.modules.ifc_reader.ifc_geometry import _GEOMETRY_PROPERTY_MAP

        method = _GEOMETRY_PROPERTY_MAP.get(name, "")
    except Exception:  # noqa: BLE001
        method = ""
    return (
        "Not stored anywhere in the model: BIMGuard's geometry engine computes this from the mesh "
        f"({method or 'a derived measurement'}) only when nothing authored is found -- a calculated "
        "estimate, not a value read from the file, and it can be wrong even when it looks plausible."
    )


def assess_property(property_set: Optional[str], property_name: Optional[str]) -> Optional[Assessment]:
    """Grade a single ``(property set, property)`` pair, or ``None`` when no property is named.

    Checks the live IFC schema and bSDD, then BIMGuard's own geometry-computation table, in that
    order -- the same order the property resolver itself tries a stored value before ever falling
    back to a geometry estimate (see the module docstring for each source).
    """
    name = _key(property_name)
    if not name:
        return None
    bsdd_defined = (name in _bsdd_property_names()) if _bsdd_property_names() else None

    if name in ("ifcclass", "ifcentity"):  # kept in step with ifc_reader's Pass 0
        return Assessment("high", "ifc_class", _REASONS["ifc_class"], bsdd_defined)
    if name in _RELATIONSHIP_LOOKUPS:
        reason = f"Read from an explicit stored IFC relationship: {_RELATIONSHIP_LOOKUPS[name]}."
        return Assessment("high", "relationship", reason, bsdd_defined)
    if name in _ifc_schema_attributes():
        return Assessment("high", "schema_attribute", _REASONS["schema_attribute"], bsdd_defined)

    raw_pset = (property_set or "").strip().lower()
    pset = _key(property_set)
    named_like_standard = raw_pset.startswith(("pset_", "qto_"))
    if pset and pset not in _ATTRIBUTE_PSETS:
        members_by_set = _property_set_members()
        if members_by_set:
            members = members_by_set.get(raw_pset)
            if members is None:
                reason = _REASONS["custom_pset_name"] if named_like_standard else "Not a standard or recognised property set."
                return Assessment("low", "custom", reason, bsdd_defined)
            if name not in members:
                reason = (
                    f"'{property_set}' is a real property set, but the buildingSMART Dictionary does "
                    f"not list '{property_name}' as one of its properties -- this looks like an "
                    "invented or mistyped name, not a value the model could ever carry."
                )
                return Assessment("low", "not_in_set", reason, False)
        elif not named_like_standard:
            return Assessment("low", "custom", "Not a standard or recognised property set.", bsdd_defined)
        if raw_pset.startswith("qto_"):
            return Assessment("high", "quantity", _REASONS["quantity"], bsdd_defined)
        return Assessment("medium", "property_set", _REASONS["property_set"], bsdd_defined)

    if bsdd_defined:
        return Assessment("medium", "bsdd_defined", _REASONS["bsdd_defined"], True)

    if name in _geometry_computed_names():
        return Assessment("low", "calculated", _geometry_reason(name), bsdd_defined)

    for category, reason, pattern in _NAMED_LOW_CATEGORIES:
        if pattern.search(name):
            return Assessment("low", category, reason, bsdd_defined)

    return Assessment("low", "unrecognised", _REASONS["unrecognised"], bsdd_defined)


def _get(rule: Any, *names: str) -> Optional[str]:
    """First non-empty attribute or key of *rule* among *names* (works for models and dicts)."""
    for name in names:
        value = rule.get(name) if isinstance(rule, dict) else getattr(rule, name, None)
        if value:
            return str(value)
    return None


def assess_rule(rule: Any) -> Optional[Assessment]:
    """Grade a rule by the *least* reliable property it depends on.

    Reads ``property_set``/``property_name`` (or the extractor's ``pset``/``property`` spellings)
    plus any other property the check compares against (``compare_property``, ``value_min_property``,
    ``value_max_property``). Returns ``None`` for a rule that names no property, so callers can show
    "not applicable" instead of a made-up grade.
    """
    pset = _get(rule, "property_set", "pset")
    primary_name = _get(rule, "property_name", "property")
    primary = assess_property(pset, primary_name)
    if primary is None:
        return None

    graded: list[tuple[str, Assessment]] = [(primary_name or "", primary)]
    for other_field in ("compare_property", "value_min_property", "value_max_property"):
        other = _get(rule, other_field)
        found = assess_property(pset, other) if other else None
        if found is not None:
            graded.append((other or "", found))

    name, weakest = min(graded, key=lambda item: _RANK[item[1].level])
    if name != primary_name:
        return Assessment(
            weakest.level, weakest.category, f"Compared against {name}: {weakest.reason}", weakest.bsdd_defined
        )
    return weakest
