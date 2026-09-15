"""Confidence classification for a resolved IFC property's provenance.

`ifc_reader._resolve_element_property`'s multi-pass resolution cascade
(relationship shortcut -> instance Pset -> direct attribute -> type-level
Pset -> alias -> rule fallback -> geometry bounding-box) already tags every
resolved value with a `found_pset` provenance string (e.g. `"Pset_WindowCommon"`,
`"type:Pset_WindowCommon"`, `"alias:direct_attribute"`, `"geometry"`) but that
string never reached the comparator or any report/UI — see the cascade's own
docstring in ifc_reader for the pass numbering this maps onto.

This module is the single source of truth mapping those provenance strings to
a small set of human-facing confidence categories, ordered from most to least
authoritative (`rank` 1 = most accurate), shared by the comparator (per-element
results) and the reporter (CSV/BCF exports).
"""

from __future__ import annotations

# Ordered most-to-least authoritative — `rank` 1 sorts first when a caller
# wants "most accurate first". Kept as an explicit list (not just a dict) so
# a legend can be rendered in this exact order.
CONFIDENCE_CATEGORIES: list[dict] = [
    {
        "id": "authored",
        "label": "Authored Property",
        "description": "Read directly from the element's own Pset, quantity set, or IFC attribute.",
        "rank": 1,
        "meter_level": 3,
    },
    {
        "id": "derived",
        "label": "Derived (Geometry & Relationships)",
        "description": (
            "Computed from the model's real geometry or IFC relationships "
            "(e.g. supports, seismic inputs, per-step stair geometry, door clear opening)."
        ),
        "rank": 2,
        "meter_level": 3,
    },
    {
        "id": "type_inherited",
        "label": "Type-Inherited",
        "description": "Not on the instance itself — inherited from its IfcTypeObject (e.g. IfcWindowType).",
        "rank": 3,
        "meter_level": 2,
    },
    {
        "id": "alias",
        "label": "Alias Match",
        "description": "Found under an alternate/synonym property name, not the one the rule asked for.",
        "rank": 4,
        "meter_level": 2,
    },
    {
        "id": "fallback",
        "label": "Rule Fallback",
        "description": "Found only via the rule's own declared backup property name.",
        "rank": 5,
        "meter_level": 1,
    },
    {
        "id": "geometry_estimate",
        "label": "Geometry Estimate",
        "description": (
            "Estimated from the model's bounding-box geometry — used only when no "
            "Pset or attribute value exists anywhere for this element."
        ),
        "rank": 6,
        "meter_level": 1,
    },
    {
        "id": "unresolved",
        "label": "Unresolved",
        "description": "No value could be found for this property through any resolution pass.",
        "rank": 7,
        "meter_level": 0,
    },
]

_BY_ID: dict[str, dict] = {c["id"]: c for c in CONFIDENCE_CATEGORIES}


def classify_property_confidence(found_pset: str | None) -> dict:
    """Classify a `found_pset` provenance string into a confidence category.

    Returns one of the dicts in CONFIDENCE_CATEGORIES verbatim — callers must
    not mutate the result.
    """
    if not found_pset:
        return _BY_ID["unresolved"]

    if found_pset == "geometry":
        return _BY_ID["geometry_estimate"]
    if found_pset.startswith(("geometry:", "derived:")):
        return _BY_ID["derived"]
    if found_pset.startswith(("spatial:", "material:")):
        return _BY_ID["authored"]
    # Checked before the plain "type:" prefix below: "alias:type:Pset_X" is an
    # alias match that happened to resolve on the type object, still an alias.
    if found_pset.startswith("alias:"):
        return _BY_ID["alias"]
    if found_pset.startswith("fallback:"):
        return _BY_ID["fallback"]
    if found_pset.startswith("type:"):
        return _BY_ID["type_inherited"]
    # A plain Pset name (Pass 1) or "direct_attribute" (Pass 3): the
    # instance's own authored data.
    return _BY_ID["authored"]
