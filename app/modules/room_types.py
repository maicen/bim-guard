"""Room-type vocabulary and classifier for ``IfcSpace`` names.

A rule that says "bedroom doors must be at least 800 mm" needs to know which
rooms are bedrooms. IFC has no room-type attribute -- ``IfcSpace.PredefinedType``
distinguishes an internal space from a parking space, not a kitchen from a
bathroom -- so the type has to be read from what authors actually type: the
space's category property, its object type, its long name, its name.

This module is deliberately pure Python with no IFC dependency, so the
comparator (which never touches a model) and the reader can share one
definition of the vocabulary and of the scope-predicate keys built on it.

Design rules, inherited from how the rest of the engine treats missing data and
from the principle that the model's own wording is authoritative:

* A name that matches nothing is ``UNKNOWN_ROOM_TYPE``, never a guess. A caller
  that scopes a rule by room type then gets an UNDETERMINED predicate for that
  room instead of a silent in/out decision.
* A room's name is whatever its author typed and is never altered. A name that
  looks like a misspelling of a known room word is not quietly "corrected" into
  that type either: ``suggest_name_correction`` reports it so the user can fix
  the model, and until they do the room stays untyped.
* The vocabulary is a convenience, not a limit. Any room name a model carries is
  valid; a rule can name a label outside the vocabulary and it is matched against
  the room names literally (see ``name_mentions``).
* There are no code-specific groups such as "habitable". Whether a kitchen is a
  habitable room is a question the governing code answers differently in
  different jurisdictions, so a rule lists the types it means explicitly.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

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

#: The canonical room types, i.e. the labels a rule may use as a synonym-aware
#: shorthand. Any other label a rule names is matched against room names.
ROOM_TYPES = frozenset(ROOM_TYPE_KEYWORDS)

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


def name_mentions(name: str | None, phrase: str | None) -> bool:
    """Return True when ``name`` contains ``phrase`` as whole words.

    How a label outside the vocabulary is matched, so the engine is open to any
    room name: "waiting" finds "CENTRAL WAITING" and "Waiting / Activity Area",
    but "lab" does not find "Table Room". Case, punctuation and plurals are
    ignored, the same as the vocabulary matcher.
    """
    wanted = _tokens(str(phrase or ""))
    if not wanted:
        return False
    have = _tokens(str(name or ""))
    width = len(wanted)
    return any(have[i : i + width] == wanted for i in range(len(have) - width + 1))


# ── Misspelling detection ─────────────────────────────────────────────────────

#: Shortest word worth flagging as a misspelling. Typos in three- and four-letter
#: words are indistinguishable from other real words ("hail", "bath"), and the
#: rooms people actually mistype are the long ones ("bedroom", "kitchen").
_MIN_TYPO_LENGTH = 5
#: difflib similarity a word must reach to be reported as a likely misspelling.
_TYPO_CUTOFF = 0.8
_WORD = re.compile(r"[A-Za-z]+")


@dataclass(frozen=True)
class NameSuggestion:
    """A room name that looks like a misspelling of a known room word."""

    found: str  # the word exactly as the user wrote it
    keyword: str  # the vocabulary word it resembles
    room_type: str  # the room type that word belongs to
    suggested_name: str  # the user's name with only that word corrected


def _match_case(word: str, replacement: str) -> str:
    """Give ``replacement`` the capitalisation style of ``word``."""
    if word.isupper():
        return replacement.upper()
    if word[:1].isupper():
        return replacement.capitalize()
    return replacement.lower()


def suggest_name_correction(
    name: str | None,
    keywords: Mapping[str, Iterable[str]] | None = None,
) -> NameSuggestion | None:
    """Suggest a corrected spelling for a room name the vocabulary cannot read.

    Returns None when the name is already understood, has nothing that resembles
    a room word, or is too short to judge. The name itself is never modified: the
    suggestion is a proposal for the user to apply to the model, and only the
    misspelt word changes ("BADROOM 1" -> "BEDROOM 1").
    """
    if not name or classify_room_text(name, keywords):
        return None
    source = ROOM_TYPE_KEYWORDS if keywords is None else keywords
    single_words = {
        phrase: room_type
        for room_type, phrases in source.items()
        for phrase in phrases
        if len(_tokens(phrase)) == 1 and " " not in phrase
    }
    best: tuple[float, re.Match[str], str] | None = None
    for match in _WORD.finditer(str(name)):
        word = match.group()
        if len(word) < _MIN_TYPO_LENGTH:
            continue
        token = _singular(word.lower())
        for close in difflib.get_close_matches(token, single_words, n=1, cutoff=_TYPO_CUTOFF):
            score = difflib.SequenceMatcher(None, token, close).ratio()
            if best is None or score > best[0]:
                best = (score, match, close)
    if best is None:
        return None
    _, match, keyword = best
    word = match.group()
    replacement = _match_case(word, keyword)
    if _singular(word.lower()) != word.lower():  # keep a typed plural
        replacement += word[-1]
    return NameSuggestion(
        found=word,
        keyword=keyword,
        room_type=single_words[keyword],
        suggested_name=f"{name[: match.start()]}{replacement}{name[match.end() :]}",
    )


def closest_room_types(label: str, limit: int = 3) -> list[str]:
    """Return the vocabulary room types nearest to ``label`` (for "did you mean")."""
    return difflib.get_close_matches(str(label).casefold(), sorted(ROOM_TYPES), n=limit, cutoff=0.6)
