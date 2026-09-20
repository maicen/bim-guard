"""How far a rule can be trusted to run against a real IFC model.

A rule is only as dependable as the data it reads. This module grades that from
the property a rule checks, independent of what the source PDF says, so an
extracted rule and a hand-written one get the same answer:

* **high** -- standard IFC attributes, geometry, quantities and relationships
  (GlobalId, width, height, area, host wall, storey): BIMGuard reads and
  verifies these straight from the model.
* **medium** -- standard property-set data (fire rating, U-value, glazing
  material, acoustic rating): reliable only when the property was authored and
  exported correctly from the authoring tool.
* **low** -- custom parameters, calculated or derived values, and anything that
  needs project context IFC does not reliably record (clear opening dimensions,
  escape compliance, smoke protection, manufacturer data, user-defined types).

The tiers follow the reliability guidance the project team supplied. They are
a heuristic on property *names* and property-set *naming*, kept here as data so
they can be tuned without touching the callers. A property this module cannot
place is graded ``low`` rather than assumed safe.

Whether a ``Pset_...`` name is a *real* buildingSMART property set is decided from the
local bSDD dictionary (a project can borrow the ``Pset_`` prefix for its own data). Only when
that dictionary cannot be loaded does grading fall back to the prefix alone.
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


# -- LOW: matched on the property name, checked before anything else ---------------------------------

#: (category, reason, pattern over the normalised property name), first match wins.
_LOW_BY_NAME: tuple[tuple[str, str, "re.Pattern[str]"], ...] = (
    (
        "user_defined",
        "A user-defined value: its meaning is set per project, so it can't be compared reliably.",
        re.compile(r"userdefined"),
    ),
    (
        "manufacturer",
        "Manufacturer or product data, which is rarely filled in consistently in IFC models.",
        re.compile(r"manufacturer|modellabel|modelreference|articlenumber|productionyear|assemblyplace"),
    ),
    (
        "derived",
        "A clear-opening or clearance dimension: it is calculated from geometry and hardware, "
        "not stored as standard IFC data.",
        re.compile(r"clear(opening|width|height|depth|ance)"),
    ),
    (
        "contextual",
        "Depends on project context (such as escape routes or smoke protection) that IFC does not "
        "reliably record.",
        re.compile(r"escape|egress|smoke|compliance|traveldistance"),
    ),
    (
        "derived",
        "A calculated or derived value rather than data stored in the model.",
        re.compile(r"calculated|derived|computed"),
    ),
)

# -- Property-set naming ------------------------------------------------------------------------------

#: Pseudo property sets the extractor and rule form use for things that are not property sets at all.
_ATTRIBUTE_PSETS = frozenset(
    {"", "attributes", "attribute", "ifcattributes", "geometry", "relationships", "relationship", "quantities"}
)

# -- HIGH: standard attributes, geometry/quantities, relationships ----------------------------------

_STANDARD_ATTRIBUTES = frozenset(
    """globalid name description objecttype tag predefinedtype ifcclass class type elementtype longname
    operationtype""".split()
)
_GEOMETRY_AND_QUANTITIES = frozenset(
    """width height depth length area volume thickness perimeter elevation overallwidth overallheight
    netarea grossarea netvolume grossvolume netwidth grosswidth netheight grossheight
    placementmatrix placement boundingbox""".split()
)
#: Relationship-derived lookups such as StoreyGlobalId, HostIfcClass, OpeningGlobalId.
_RELATIONSHIP = re.compile(
    r"^(storey|host|opening|type|container|space)(globalid|name|ifcclass|id)$"
    r"|^(storey|hostwall|hostelement)$"
)

# -- MEDIUM: standard property-set data, even when the property set itself isn't stated -------------

_STANDARD_PSET_PROPERTIES = frozenset(
    """firerating thermaltransmittance uvalue acousticrating glazingmaterial glazing isexternal
    loadbearing combustible surfacespreadofflame securityrating handicapaccessible selfclosing
    reference status material materialname""".split()
)

_REASONS = {
    "standard_attribute": "A standard IFC attribute: BIMGuard reads and verifies it directly from the model.",
    "geometry": "Geometry or a quantity: BIMGuard reads and verifies it directly from the model.",
    "relationship": "An IFC relationship (host, storey, opening): BIMGuard reads and verifies it directly.",
    "quantity": "A standard quantity set value: BIMGuard reads and verifies it directly from the model.",
    "property_set": (
        "Standard property-set data: reliable only if the property was authored and exported correctly "
        "from the authoring tool."
    ),
    "custom": (
        "A custom property set: authored per project rather than defined by IFC, so it may be missing "
        "or named differently."
    ),
    "custom_pset_name": (
        "Named like a standard property set but not in the buildingSMART dictionary, so it is treated "
        "as a custom set that may be missing or named differently."
    ),
    "bsdd_defined": (
        "Defined in the buildingSMART Data Dictionary but not a core IFC attribute, so it is only as "
        "reliable as the model's authoring."
    ),
    "unrecognised": (
        "Not recognised as a standard IFC attribute or property-set property, so BIMGuard can't rely "
        "on it being present."
    ),
}


@lru_cache(maxsize=1)
def _standard_property_sets() -> frozenset[str]:
    """Lower-cased names of the standard property sets in the local bSDD dictionary.

    Empty when the dictionary is unavailable; callers then fall back to the name prefix.
    Cached for the life of the process -- the reference data is static.
    """
    try:
        from app.services.bsdd_ontology_repository import get_bsdd_ontology_repository

        return get_bsdd_ontology_repository().known_property_set_names()
    except Exception:  # noqa: BLE001 - grading must never fail just because bSDD isn't loadable
        return frozenset()


@lru_cache(maxsize=1)
def _bsdd_property_names() -> frozenset[str]:
    """Normalised names of every property the local bSDD dictionary defines (empty if unavailable)."""
    try:
        from app.services.bsdd_ontology_repository import get_bsdd_ontology_repository

        return get_bsdd_ontology_repository().known_property_names()
    except Exception:  # noqa: BLE001 - grading must never fail just because bSDD isn't loadable
        return frozenset()


def assess_property(property_set: Optional[str], property_name: Optional[str]) -> Optional[Assessment]:
    """Grade a single ``(property set, property)`` pair, or ``None`` when no property is named.

    bSDD is a *reference*, not a verdict: being defined there shows a property is a standard one,
    not that real models fill it in reliably (``FireRating`` is defined in bSDD and still grades
    medium). It only ever lifts a property that would otherwise be "unrecognised".
    """
    name = _key(property_name)
    if not name:
        return None
    known_bsdd = _bsdd_property_names()
    bsdd_defined = (name in known_bsdd) if known_bsdd else None

    for category, reason, pattern in _LOW_BY_NAME:
        if pattern.search(name):
            return Assessment("low", category, reason, bsdd_defined)

    # Prefixes are read from the raw text: the normalised key has lost its underscores.
    raw_pset = (property_set or "").strip().lower()
    pset = _key(property_set)
    named_like_standard = raw_pset.startswith(("pset_", "qto_"))
    if pset and pset not in _ATTRIBUTE_PSETS:
        known = _standard_property_sets()
        # The dictionary is authoritative; the prefix alone is only a fallback for when it is missing.
        is_standard_set = raw_pset in known if known else named_like_standard
        if not is_standard_set:
            reason = _REASONS["custom_pset_name"] if named_like_standard else _REASONS["custom"]
            return Assessment("low", "custom", reason, bsdd_defined)
    else:
        is_standard_set = False
    is_quantity_set = is_standard_set and raw_pset.startswith("qto_")
    if is_quantity_set:
        return Assessment("high", "quantity", _REASONS["quantity"], bsdd_defined)

    if name in _STANDARD_ATTRIBUTES:
        return Assessment("high", "standard_attribute", _REASONS["standard_attribute"], bsdd_defined)
    if name in _GEOMETRY_AND_QUANTITIES:
        return Assessment("high", "geometry", _REASONS["geometry"], bsdd_defined)
    if _RELATIONSHIP.match(name):
        return Assessment("high", "relationship", _REASONS["relationship"], bsdd_defined)
    if is_standard_set or name in _STANDARD_PSET_PROPERTIES:
        return Assessment("medium", "property_set", _REASONS["property_set"], bsdd_defined)

    if bsdd_defined:
        return Assessment("medium", "bsdd_defined", _REASONS["bsdd_defined"], True)
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

    Reads ``property_set``/``property_name`` (or the extractor's ``pset``/
    ``property`` spellings) plus any other property the check compares against
    (``compare_property``, ``value_min_property``, ``value_max_property``).
    Returns ``None`` for a rule that names no property, e.g. an engine rule
    with no IFC property to grade, so callers can show "not applicable"
    instead of a made-up grade.
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
