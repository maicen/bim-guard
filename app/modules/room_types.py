"""Room-type vocabulary and classifier for ``IfcSpace`` names.

A rule that says "bedroom doors must be at least 800 mm" needs to know which
rooms are bedrooms. IFC has no room-type attribute -- ``IfcSpace.PredefinedType``
distinguishes an internal space from a parking space, not a kitchen from a
bathroom -- so the type has to be read from what authors actually type: the
space's category property, its object type, its long name, its name.

This module is deliberately pure Python with no IFC dependency, so the
comparator (which never touches a model) and the reader can share one
definition of the vocabulary and of the scope-predicate keys built on it.

Two design rules, both inherited from how the rest of the engine treats missing
data:

* A name that matches nothing is ``UNKNOWN_ROOM_TYPE``, never a guess. A caller
  that scopes a rule by room type then gets an UNDETERMINED predicate for that
  room instead of a silent in/out decision.
* There are no code-specific groups such as "habitable". Whether a kitchen is a
  habitable room is a question the governing code answers differently in
  different jurisdictions, so a rule lists the types it means explicitly.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

#: Type reported for a room whose text matched no keyword. It is a real value,
#: not an absence: it tells a predicate "this room exists but cannot be typed".
UNKNOWN_ROOM_TYPE = "unknown"

#: ``applies_when`` / ``exceptions`` predicate keys that scope a rule by the
#: rooms an element is connected to. Shared so the comparator (evaluates them),
#: the reader (decides whether to resolve room links) and the SHACL generator
#: (which cannot express them) all agree on what a room predicate is.
ROOM_SCOPE_KEYS = frozenset(
    {
        "room_type_any_of",
        "room_type_all_of",
        "room_type_none_of",
        "room_name_any_of",
    }
)

#: Canonical room type -> phrases that identify it. Matched as whole words (or
#: whole consecutive words), so "den" does not match "garden". Plurals are
#: handled by the matcher; keywords are written in the singular.
ROOM_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bedroom": (
        "bedroom", "bed room", "sleeping room", "nursery", "bunk room",
        "guest room",
        # A misspelling seen throughout the repo's own reference model
        # (BUILDING_R4 names 64 rooms "BADROOM 1/2"); it cannot mean anything else.
        "badroom",
    ),
    "living": (
        "living", "living room", "lounge", "family room", "great room",
        "sitting room", "den", "recreation room", "rec room", "media room",
    ),
    "kitchen": ("kitchen", "kitchenette"),
    "dining": ("dining", "dining room", "breakfast"),
    "bathroom": ("bathroom", "bath", "ensuite", "en suite", "shower room"),
    "toilet": (
        "toilet", "wc", "w c", "lavatory", "water closet", "powder room",
        "restroom", "washroom",
    ),
    "laundry": ("laundry", "laundry room"),
    "utility": ("utility", "utility room"),
    "storage": ("storage", "store", "store room", "storeroom", "pantry"),
    "closet": ("closet", "walk in closet", "wardrobe", "dressing room"),
    "corridor": ("corridor", "hallway", "hall", "passage", "passageway"),
    "lobby": ("lobby", "foyer", "entry", "entrance", "vestibule"),
    "stair": ("stair", "staircase", "stairwell"),
    "office": ("office", "study", "home office"),
    "garage": ("garage", "carport"),
    "balcony": ("balcony", "terrace", "porch", "deck", "veranda", "patio"),
    "mechanical": (
        "mechanical", "electrical", "boiler", "plant", "riser", "shaft",
    ),
}

#: Characters that separate two room types written as one name
#: ("Kitchen/Dining", "Living & Dining", "Kitchen and Dining").
_SEGMENT_SPLIT = re.compile(r"[/&+,;]|\band\b")
_TOKEN = re.compile(r"[a-z]+|\d+")


def _singular(token: str) -> str:
    """Strip a plural 's' so "bedrooms" and "stairs" match their keywords.

    Leaves short tokens ("wc", "bus") and "-ss" words ("glass") untouched.
    """
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(text: str) -> list[str]:
    """Lower-case word tokens, digits kept apart so "Bedroom1" reads as two."""
    return [_singular(t) for t in _TOKEN.findall(text.lower())]


def _compile(keywords: Mapping[str, Iterable[str]]) -> list[tuple[str, tuple[str, ...]]]:
    """Flatten ``{type: phrases}`` into ``[(type, phrase_tokens)]``."""
    compiled: list[tuple[str, tuple[str, ...]]] = []
    for room_type, phrases in keywords.items():
        for phrase in phrases:
            tokens = tuple(_tokens(phrase))
            if tokens:
                compiled.append((room_type, tokens))
    return compiled


_COMPILED_DEFAULT = _compile(ROOM_TYPE_KEYWORDS)


def _head_type(
    tokens: list[str], compiled: list[tuple[str, tuple[str, ...]]]
) -> str | None:
    """Return the type of the segment's head noun, or None.

    English puts the head noun last: a "Bedroom Closet" is a closet and a
    "Master Bedroom Bathroom" is a bathroom. So among every keyword found, the
    one that ends latest wins, and a longer phrase beats a shorter one ending in
    the same place ("water closet" is a toilet, not a closet).
    """
    best: tuple[int, int, str] | None = None
    for room_type, phrase in compiled:
        width = len(phrase)
        for start in range(len(tokens) - width + 1):
            if tuple(tokens[start : start + width]) != phrase:
                continue
            candidate = (start + width, width, room_type)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    return best[2] if best else None


def classify_room_text(
    text: str | None,
    keywords: Mapping[str, Iterable[str]] | None = None,
) -> list[str]:
    """Return the room types named by one piece of text, in order of appearance.

    A name that lists several rooms ("Kitchen/Dining") yields several types; a
    name with one head noun yields one. An empty list means nothing matched --
    callers decide whether that becomes ``UNKNOWN_ROOM_TYPE``.

    ``keywords`` overrides the default vocabulary, for tests and for a future
    per-project vocabulary.
    """
    if not text or not str(text).strip():
        return []
    compiled = _compile(keywords) if keywords is not None else _COMPILED_DEFAULT
    found: list[str] = []
    for segment in _SEGMENT_SPLIT.split(str(text).lower()):
        room_type = _head_type(_tokens(segment), compiled)
        if room_type and room_type not in found:
            found.append(room_type)
    return found


def classify_room(
    candidates: Iterable[tuple[str, str | None]],
    keywords: Mapping[str, Iterable[str]] | None = None,
) -> tuple[list[str], str | None]:
    """Classify a room from several labelled text sources, best source first.

    ``candidates`` is ``[(source_label, text), ...]`` in priority order -- an
    explicit category property before a free-text name. The first source that
    yields a type wins, so a Revit room whose ``Name`` is the number "104" but
    whose ``LongName`` is "Bedroom" is still typed.

    Returns ``(types, source_label)``. When nothing matches, returns
    ``([UNKNOWN_ROOM_TYPE], None)``.
    """
    for source, text in candidates:
        types = classify_room_text(text, keywords)
        if types:
            return types, source
    return [UNKNOWN_ROOM_TYPE], None
