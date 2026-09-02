"""Import NotebookLM rule exports (JSON) into the Supabase rule catalog.

The NotebookLM workflow ends with a model emitting an array of extracted rule
objects. Those objects are *close* to the shape ``RuleService.create_rule``
wants but never identical: the key names drift between notebooks (``ref`` vs
``reference`` vs ``clause``), the measurement is usually carried in a
unit-suffixed key such as ``clearance_mm`` rather than in a separate
``check_value`` / ``unit`` pair, and every notebook invents extra keys of its
own. This importer is the adapter: it maps whatever the export used onto the
catalog columns, derives the check from the dimension key when the export did
not spell one out, and preserves every key it did not consume in
``parameters`` so nothing extracted is silently dropped.

It is the file-driven counterpart to ``scripts/seed_nfpa13_clearances.py``,
which carries the same rule shape as hardcoded dictionaries.

Input format
------------
A file may hold either a bare JSON array of rule objects, or an object with the
rules under ``rules`` / ``data`` / ``items`` / ``records`` / ``results`` /
``entries`` / ``extracted_rules``. In the object form the remaining top-level
keys become defaults for every rule in the file (``ruleset_id``, ``mechanism``,
``category``, ``source_text``, ...) and are recorded as export provenance on
each row.

Key mapping
-----------
* Aliases — ``FIELD_ALIASES`` maps the spellings notebooks actually produce
  onto catalog columns. The first alias present wins.
* Dimensions — a key of the form ``<stem>_<unit>`` (``clearance_mm``,
  ``annular_clearance_mm``, ``gap_in``) is read as the rule's measurement when
  the export gave no explicit ``check_value``. The unit and, when absent, the
  property name are derived from it. The operator is only defaulted to ``>=``
  for stems where a minimum is unambiguous (``MIN_DEFAULT_STEMS``); any other
  stem must state its own operator rather than have one guessed.
* ``applies_when`` / ``exceptions`` — coerced to the shapes Module 2 resolves
  and Module 4 evaluates. Exception entries may be reference strings (resolved
  against sibling rules at analysis time) or inline
  ``{reference, label, predicate}`` objects. Predicate keys the extractor
  cannot supply are reported, because they leave elements UNDETERMINED rather
  than narrowing scope or waiving a finding.
* Everything else — carried verbatim into ``parameters`` under its original
  key, alongside an ``_import`` provenance block.

Provenance defaults
-------------------
Rows land as ``extraction_method="notebooklm"``, ``needs_review=True`` and
``confidence=0.5`` unless the export states otherwise. Text pulled out of a
standard by a language model is a draft until a human confirms it, so the
default is the review queue, not the catalog proper.

Usage::

    python scripts/import_notebooklm_json.py                    # whole export dir
    python scripts/import_notebooklm_json.py data/notebooklm_exports/x.json
    python scripts/import_notebooklm_json.py --dry-run          # map and report only
    python scripts/import_notebooklm_json.py --force            # replace existing refs
    python scripts/import_notebooklm_json.py --strict           # abort on any bad row

Exit codes: ``0`` every record imported, ``1`` a record was rejected or a write
failed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.services.rules_service import (  # noqa: E402 - needs REPO_ROOT on sys.path
    MECHANISMS,
    RULE_CATEGORIES,
    RuleService,
)

#: Where NotebookLM exports are dropped.
DEFAULT_EXPORT_DIR = REPO_ROOT / "data" / "notebooklm_exports"

#: Stamped into every row's parameters so an imported rule can be traced back.
IMPORTER = "import_notebooklm_json/1"

#: Top-level keys that may hold the rule array in an object-wrapped export.
CONTAINER_KEYS = (
    "rules",
    "extracted_rules",
    "data",
    "items",
    "records",
    "results",
    "entries",
)

#: Catalog column -> export spellings, in priority order (first present wins).
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "reference": ("reference", "ref", "rule_id", "clause_ref", "clause", "id"),
    "description": ("description", "desc", "requirement", "statement", "title", "summary"),
    "rule_type": ("rule_type", "type", "kind"),
    "rule_category": ("rule_category",),
    "category": ("category", "discipline"),
    "mechanism": ("mechanism",),
    "ruleset_id": ("ruleset_id", "ruleset", "rule_folder", "folder"),
    "target_ifc_class": (
        "target_ifc_class",
        "target",
        "target_class",
        "ifc_class",
        "ifc_entity",
        "entity",
        "element",
        "element_class",
    ),
    "property_set": ("property_set", "pset", "pset_name"),
    "property_name": ("property_name", "property", "parameter", "quantity", "attribute"),
    "fallback_property": ("fallback_property", "fallback"),
    "operator": ("operator", "op", "comparison", "comparator"),
    "check_value": ("check_value", "value", "threshold", "limit", "required_value"),
    "value_min": ("value_min", "min", "minimum", "min_value", "lower_bound"),
    "value_max": ("value_max", "max", "maximum", "max_value", "upper_bound"),
    "unit": ("unit", "units", "uom"),
    "severity": ("severity", "priority"),
    "keyword": ("keyword", "keywords", "tag", "tags"),
    "compliance_type": ("compliance_type", "compliance"),
    "applies_when": ("applies_when", "applies_to", "scope", "conditions", "when"),
    "exceptions": ("exceptions", "exemptions", "waivers", "exclusions"),
    "related_refs": ("related_refs", "related", "references", "see_also"),
    "overridden_by": ("overridden_by",),
    "source_text": ("source_text", "source", "citation", "quote", "clause_text", "excerpt"),
    "confidence": ("confidence", "confidence_score"),
    "needs_review": ("needs_review", "review_required", "unverified"),
    "extraction_method": ("extraction_method",),
    "parameters": ("parameters", "params"),
}

#: Unit suffix as written in a key -> the unit string stored on the rule.
UNIT_ALIASES: dict[str, str] = {
    "mm": "mm",
    "millimetre": "mm",
    "millimetres": "mm",
    "millimeter": "mm",
    "millimeters": "mm",
    "cm": "cm",
    "m": "m",
    "metre": "m",
    "metres": "m",
    "meter": "m",
    "meters": "m",
    "in": "in",
    "inch": "in",
    "inches": "in",
    "ft": "ft",
    "foot": "ft",
    "feet": "ft",
    "deg": "deg",
    "degree": "deg",
    "degrees": "deg",
    "pct": "%",
    "percent": "%",
    "pa": "Pa",
    "kpa": "kPa",
    "mpa": "MPa",
    "kg": "kg",
    "kn": "kN",
    "mm2": "mm2",
    "m2": "m2",
    "m3": "m3",
    "lux": "lux",
    "db": "dB",
}

_UNIT_PATTERN = "|".join(sorted(UNIT_ALIASES, key=len, reverse=True))
DIMENSION_RE = re.compile(rf"^(?P<stem>.+?)_(?P<unit>{_UNIT_PATTERN})$")

#: Dimension stems preferred as the rule's measurement when several are present.
DIMENSION_PRIORITY = (
    "annular_clearance",
    "clearance",
    "clear_width",
    "clear_height",
    "clear_opening",
    "gap",
    "air_gap",
    "separation",
    "headroom",
    "cover",
)

#: Stems for which ">=" is the only reading — a clearance is a floor, never a
#: ceiling. Any other stem must carry an explicit operator; guessing one would
#: silently invert the rule.
MIN_DEFAULT_STEMS = frozenset(DIMENSION_PRIORITY) | {
    "clear_distance",
    "clearance_distance",
    "minimum_clearance",
    "free_space",
}

#: Dimension stem -> IFC-style property name, used only when the export names
#: no property of its own.
PROPERTY_NAMES = {
    "annular_clearance": "AnnularClearance",
    "clearance": "Clearance",
    "clear_width": "ClearWidth",
    "clear_height": "ClearHeight",
    "clear_opening": "ClearOpeningWidth",
    "air_gap": "AirGap",
    "separation": "SeparationDistance",
}

#: Operators the comparator dispatches on (``module4_comparator._compare``
#: plus the operators it handles before reaching it).
SUPPORTED_OPERATORS = {
    ">=",
    "<=",
    ">",
    "<",
    "==",
    "!=",
    "between",
    "matches",
    "exists",
    "not_exists",
    "documented",
    "field_consistency",
    "unique_within_scope",
    "exempt",
}

#: Operators that carry no threshold of their own.
VALUELESS_OPERATORS = {
    "exists",
    "not_exists",
    "documented",
    "exempt",
    "unique_within_scope",
    "field_consistency",
}

#: Severity vocabulary already present in the rules table.
SEVERITIES = {"mandatory", "recommended", "advisory", "informational"}

#: Exception-object key aliases, mapped onto the shape Module 4 evaluates.
EXCEPTION_REF_KEYS = ("reference", "ref", "rule_id", "id", "key", "exemption_key")
EXCEPTION_LABEL_KEYS = ("label", "title", "name", "description", "desc")
EXCEPTION_PREDICATE_KEYS = ("predicate", "applies_when", "when", "condition", "conditions")


class RecordError(Exception):
    """A record could not be mapped onto a catalog row."""


def _key(name: Any) -> str:
    """Normalize an export key to snake_case for alias matching."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _build_alias_index() -> dict[str, str]:
    """Return alias -> column, rejecting an alias claimed by two columns."""
    index: dict[str, str] = {}
    for column, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            norm = _key(alias)
            if index.get(norm, column) != column:
                raise RuntimeError(
                    f"alias {alias!r} is claimed by both {index[norm]!r} and {column!r}"
                )
            index[norm] = column
    return index


ALIAS_INDEX = _build_alias_index()


def _supported_predicate_keys() -> set[str] | None:
    """Return predicate keys the extractor can resolve, or None if unknown.

    Read off the comparator so this script cannot drift from it. Returns None
    when the comparator's shape has moved, in which case the predicate advisory
    is skipped rather than reported wrongly.
    """
    try:
        from app.modules import module4_comparator as m4
    except Exception:  # noqa: BLE001 - advisory only, never fatal to an import
        return None
    groups = [
        getattr(m4, "_SCOPE_NUMERIC_PROPERTIES", None),
        getattr(m4, "_SCOPE_LIST_FIELDS", None),
        getattr(m4, "_SCOPE_TRIVIAL_KEYS", None),
    ]
    if any(group is None for group in groups):
        return None
    keys: set[str] = set()
    for group in groups:
        keys.update(group)
    return keys


def _as_number(value: Any) -> float | None:
    """Return value as a float, accepting 50, '50' or '50 mm'. None if not numeric."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.match(r"^\s*(-?\d+(?:\.\d+)?)", value)
        if match:
            return float(match.group(1))
    return None


def _as_bool(value: Any, default: bool) -> bool:
    """Coerce an export value to a bool, tolerating 'true'/'yes'/1."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"true", "yes", "y", "1"}


def _as_obj(value: Any, field: str) -> dict:
    """Coerce a value that must be a JSON object into a dict."""
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise RecordError(f"{field} is a string that is not JSON: {value!r}") from exc
        if isinstance(decoded, dict):
            return decoded
    raise RecordError(f"{field} must be an object, got {type(value).__name__}")


def _as_list(value: Any) -> list:
    """Coerce a value that should be a JSON array into a list."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return [value]
        return decoded if isinstance(decoded, list) else [decoded]
    return [value]


def _display_path(path: Path) -> str:
    """Return a repo-relative POSIX path, falling back to the absolute one.

    An export handed in from outside the repository (a download directory, a
    temp file) has no relative form, and recording where it came from must not
    be the thing that fails the import.
    """
    try:
        relative = path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return path.resolve().as_posix()
    return relative.as_posix()


def _camel(stem: str) -> str:
    """Turn a snake_case dimension stem into an IFC-style property name."""
    return "".join(part.capitalize() for part in stem.split("_") if part)


def _normalize_exception(entry: Any, notes: list[str]) -> Any:
    """Return an exception entry in the shape Module 2 and Module 4 consume.

    A string stays a reference, resolved at analysis time against the rule it
    names. An object is rewritten to ``{reference, label, predicate}``; any
    other keys it carried are kept beside them.
    """
    if not isinstance(entry, dict):
        ref = str(entry).strip()
        return ref or None

    fields = {_key(k): (k, v) for k, v in entry.items()}
    out: dict[str, Any] = {}
    used: set[str] = set()

    for group, target in (
        (EXCEPTION_REF_KEYS, "reference"),
        (EXCEPTION_LABEL_KEYS, "label"),
    ):
        for alias in group:
            norm = _key(alias)
            if norm in fields:
                out[target] = str(fields[norm][1]).strip()
                used.add(norm)
                break

    predicate: dict = {}
    for alias in EXCEPTION_PREDICATE_KEYS:
        norm = _key(alias)
        if norm not in fields:
            continue
        raw = fields[norm][1]
        used.add(norm)
        if isinstance(raw, dict):
            predicate = raw
        else:
            notes.append(
                f"exception {out.get('reference', '?')}: {fields[norm][0]!r} is free text, "
                "not a predicate object — it can never waive a finding"
            )
        break

    out["predicate"] = predicate
    for norm, (orig, value) in fields.items():
        if norm not in used:
            out[orig] = value

    if not out.get("reference"):
        notes.append("an inline exception has no reference; it will report as 'exception'")
    if not predicate:
        notes.append(
            f"exception {out.get('reference', '?')} carries no predicate; "
            "the comparator declines to waive on an empty predicate"
        )
    return out


def read_export(path: Path) -> tuple[list[Any], dict[str, Any], dict[str, Any]]:
    """Return (records, column defaults, export metadata) for one export file.

    Top-level keys other than the rule array become defaults for every record
    in the file — recognised names map onto columns, the rest are kept as
    export metadata and stamped on each row's provenance.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RecordError(f"{path.name}: {exc}") from exc

    if isinstance(doc, list):
        return doc, {}, {}
    if not isinstance(doc, dict):
        raise RecordError(f"{path.name}: top level must be an array or object")

    records: list[Any] | None = None
    container_key = ""
    for candidate in CONTAINER_KEYS:
        value = doc.get(candidate)
        if isinstance(value, list):
            records, container_key = value, candidate
            break
    if records is None:
        records = [doc]

    defaults: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    for raw_key, value in doc.items():
        if raw_key == container_key:
            continue
        column = ALIAS_INDEX.get(_key(raw_key))
        # reference and description are per-rule by nature; a file-level one
        # would stamp every row with the same identity.
        if column and column not in ("reference", "description"):
            defaults[column] = value
        else:
            metadata[raw_key] = value
    return records, defaults, metadata


def normalize_record(
    raw: Any,
    defaults: dict[str, Any],
    metadata: dict[str, Any],
    source: Path,
    index: int,
    ruleset_override: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Map one export record onto ``RuleService.create_rule`` keyword arguments.

    Returns (row, notes). Notes are advisories worth printing; anything that
    would produce a wrong or unusable rule raises ``RecordError`` instead.
    """
    if not isinstance(raw, dict):
        raise RecordError(f"record #{index} is a {type(raw).__name__}, not an object")

    notes: list[str] = []
    fields: dict[str, tuple[str, Any]] = {}
    for key, value in raw.items():
        norm = _key(key)
        if not norm:
            continue
        if norm in fields:
            notes.append(f"key {key!r} duplicates {fields[norm][0]!r}; kept the first")
            continue
        fields[norm] = (key, value)

    consumed: set[str] = set()

    def take(column: str) -> Any:
        """Return the record's value for a column, marking its key consumed."""
        for alias in FIELD_ALIASES[column]:
            norm = _key(alias)
            if norm in fields:
                consumed.add(norm)
                return fields[norm][1]
        return defaults.get(column)

    # ── Identity ──────────────────────────────────────────────────────────────
    ruleset_id = str(ruleset_override or take("ruleset_id") or "").strip()
    if not ruleset_id:
        raise RecordError(f"record #{index}: no ruleset_id on the record or the envelope")

    reference = str(take("reference") or "").strip()
    if not reference:
        reference = f"{ruleset_id}-{index:03d}"
        notes.append(f"no reference in the export; generated {reference}")

    description = str(take("description") or "").strip()
    if not description:
        raise RecordError(f"{reference}: no description")

    mechanism = str(take("mechanism") or "").strip().upper()
    if mechanism and mechanism not in MECHANISMS:
        raise RecordError(
            f"{reference}: mechanism {mechanism!r} is not one of {sorted(MECHANISMS)}"
        )

    rule_category = str(take("rule_category") or "property_check").strip()
    if rule_category not in RULE_CATEGORIES:
        raise RecordError(
            f"{reference}: rule_category {rule_category!r} is not one of "
            f"{sorted(RULE_CATEGORIES)}"
        )

    raw_category = str(take("category") or "").strip()
    category = RuleService.normalize_category(raw_category, default="")
    if raw_category and not category:
        notes.append(f"category {raw_category!r} is unknown; leaving it to be inferred")

    target = str(take("target_ifc_class") or "").strip()
    if not target and rule_category == "property_check":
        raise RecordError(f"{reference}: a property_check needs a target_ifc_class")

    # ── The check ─────────────────────────────────────────────────────────────
    operator = str(take("operator") or "").strip()
    check_value = take("check_value")
    value_min = take("value_min")
    value_max = take("value_max")
    unit = str(take("unit") or "").strip()
    unit = UNIT_ALIASES.get(_key(unit), unit)
    property_name = str(take("property_name") or "").strip()
    property_set = str(take("property_set") or "").strip()
    fallback_property = str(take("fallback_property") or "").strip()

    # Unit-suffixed keys are deliberately left unconsumed: whether or not one
    # supplies the threshold, it is data the export stated and belongs in
    # parameters alongside the rest.
    dimensions: list[tuple[str, str, float, str]] = []
    for norm, (orig, value) in fields.items():
        if norm in consumed:
            continue
        match = DIMENSION_RE.match(norm)
        if not match:
            continue
        number = _as_number(value)
        if number is None:
            continue
        dimensions.append(
            (match.group("stem"), UNIT_ALIASES[match.group("unit")], number, orig)
        )

    chosen: tuple[str, str, float, str] | None = None
    if check_value is None:
        for stem in DIMENSION_PRIORITY:
            chosen = next((d for d in dimensions if d[0] == stem), None)
            if chosen:
                break
        if chosen is None and dimensions:
            chosen = dimensions[0]

    if chosen is not None:
        stem, dim_unit, number, orig_key = chosen
        check_value = number
        notes.append(f"threshold taken from {orig_key!r} ({number:g} {dim_unit})")
        if not unit:
            unit = dim_unit
        if not property_name:
            property_name = PROPERTY_NAMES.get(stem, _camel(stem))
            notes.append(f"property_name derived from {orig_key!r} as {property_name!r}")
        if not operator:
            if stem not in MIN_DEFAULT_STEMS:
                raise RecordError(
                    f"{reference}: {orig_key!r} gives a value but no operator, and "
                    f"{stem!r} is not unambiguously a minimum — state 'operator'"
                )
            operator = ">="
            notes.append(f"operator defaulted to '>=' ({stem!r} is a minimum)")

    if operator and operator not in SUPPORTED_OPERATORS:
        raise RecordError(
            f"{reference}: operator {operator!r} is not evaluated by the comparator "
            f"({sorted(SUPPORTED_OPERATORS)})"
        )
    if operator == "between" and (value_min is None or value_max is None):
        raise RecordError(f"{reference}: operator 'between' needs value_min and value_max")
    if (
        operator not in VALUELESS_OPERATORS
        and check_value is None
        and value_min is None
        and value_max is None
    ):
        raise RecordError(
            f"{reference}: no threshold — give 'check_value', a '<name>_<unit>' key, "
            "or a bounded range"
        )
    if operator and not property_name and rule_category == "property_check":
        notes.append("no property_name: the comparator cannot resolve a value to compare")

    numeric = _as_number(check_value)
    if numeric is not None:
        check_value = numeric

    # ── Scope and waivers ─────────────────────────────────────────────────────
    applies_when = _as_obj(take("applies_when"), f"{reference}: applies_when")
    if applies_when and target and "target_ifc_class" not in applies_when:
        applies_when = {"target_ifc_class": target, **applies_when}

    exceptions: list[Any] = []
    for entry in _as_list(take("exceptions")):
        normalized = _normalize_exception(entry, notes)
        if normalized is not None:
            exceptions.append(normalized)

    supported = _supported_predicate_keys()
    if supported is not None:
        predicates = [applies_when] + [
            e.get("predicate") or {} for e in exceptions if isinstance(e, dict)
        ]
        unsupported = sorted(
            {key for predicate in predicates for key in predicate if key not in supported}
        )
        if unsupported:
            notes.append(
                f"predicate keys {unsupported} are not resolved by the extractor; "
                "they leave elements UNDETERMINED (kept in scope, never waived)"
            )

    dangling = sorted({e for e in exceptions if isinstance(e, str)})
    related_refs = [str(r).strip() for r in _as_list(take("related_refs")) if str(r).strip()]

    # ── Provenance ────────────────────────────────────────────────────────────
    confidence_raw = take("confidence")
    if confidence_raw is None:
        confidence_raw = 0.5
        notes.append("no confidence in the export; defaulted to 0.5")
    confidence = _as_number(confidence_raw)
    if confidence is None or not 0.0 <= confidence <= 1.0:
        raise RecordError(f"{reference}: confidence must be a number in 0.0-1.0")

    needs_review = _as_bool(take("needs_review"), True)
    extraction_method = str(take("extraction_method") or "notebooklm").strip()

    severity = str(take("severity") or "mandatory").strip().lower()
    if severity not in SEVERITIES:
        raise RecordError(
            f"{reference}: severity {severity!r} is not one of {sorted(SEVERITIES)}"
        )

    keyword_raw = take("keyword")
    keyword = (
        ", ".join(str(k).strip() for k in keyword_raw if str(k).strip())
        if isinstance(keyword_raw, list)
        else str(keyword_raw or "").strip()
    )

    rule_type = str(take("rule_type") or "numeric_comparison").strip()
    compliance_type = str(take("compliance_type") or "").strip()
    overridden_by = str(take("overridden_by") or "").strip()
    source_text = str(take("source_text") or "").strip()

    # ── Parameters: everything the columns did not take ───────────────────────
    # Every take() must already have run, or the column it claimed is still
    # unconsumed and gets duplicated into parameters.
    explicit = _as_obj(take("parameters"), f"{reference}: parameters")
    carried = {orig: value for norm, (orig, value) in fields.items() if norm not in consumed}
    parameters: dict[str, Any] = {**carried, **explicit}
    parameters["_import"] = {
        "importer": IMPORTER,
        "source_file": _display_path(source),
        "record_index": index,
        "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **({"export": metadata} if metadata else {}),
        **({"unresolved_exception_refs": dangling} if dangling else {}),
    }

    if dangling:
        notes.append(
            f"exception references {dangling} resolve against sibling rules at analysis "
            "time; import those rows too or the waiver never fires"
        )

    row = {
        "reference": reference,
        "rule_type": rule_type,
        "rule_category": rule_category,
        "category": category,
        "description": description,
        "target_ifc_class": target,
        "property_set": property_set,
        "property_name": property_name,
        "fallback_property": fallback_property,
        "operator": operator,
        "check_value": check_value,
        "value_min": _as_number(value_min) if value_min is not None else None,
        "value_max": _as_number(value_max) if value_max is not None else None,
        "unit": unit,
        "severity": severity,
        "keyword": keyword,
        "compliance_type": compliance_type,
        "applies_when": applies_when,
        "exceptions": exceptions,
        "related_refs": related_refs,
        "overridden_by": overridden_by,
        "source_text": source_text,
        "confidence": confidence,
        "needs_review": needs_review,
        "extraction_method": extraction_method,
        "mechanism": mechanism,
        "ruleset_id": ruleset_id,
        "parameters": json.dumps(parameters),
    }
    return row, notes


def collect_files(paths: list[str]) -> list[Path]:
    """Expand CLI paths into a sorted list of JSON files."""
    targets = [Path(p) for p in paths] if paths else [DEFAULT_EXPORT_DIR]
    files: list[Path] = []
    for target in targets:
        resolved = target if target.is_absolute() else (REPO_ROOT / target)
        if resolved.is_dir():
            files.extend(sorted(resolved.glob("*.json")))
        elif resolved.is_file():
            files.append(resolved)
        else:
            raise RecordError(f"no such file or directory: {target}")
    return files


def describe(row: dict[str, Any], notes: list[str]) -> None:
    """Print one mapped row so the mapping can be reviewed before it is written."""
    print(f"\n  {row['reference']}  [{row['rule_type']}]")
    print(f"    description: {row['description'][:92]}")
    print(f"    target     : {row['target_ifc_class'] or '(none)'}")
    if row["operator"]:
        threshold = row["check_value"]
        if threshold is None and row["value_min"] is not None:
            threshold = f"{row['value_min']}..{row['value_max']}"
        rendered = "" if threshold is None else threshold
        print(
            f"    check      : {row['property_name'] or '(no property)'} "
            f"{row['operator']} {rendered} {row['unit']}".rstrip()
        )
    if row["applies_when"]:
        print(f"    scope      : {json.dumps(row['applies_when'])}")
    for exc in row["exceptions"]:
        if isinstance(exc, dict):
            print(
                f"    waived by  : {exc.get('reference', '?')} "
                f"{json.dumps(exc.get('predicate') or {})}"
            )
        else:
            print(f"    waived by  : {exc} (by reference)")
    flag = "   [NEEDS REVIEW]" if row["needs_review"] else ""
    print(
        f"    provenance : {row['mechanism'] or '(no mechanism)'} / {row['ruleset_id']}, "
        f"{row['extraction_method']}, confidence {row['confidence']}{flag}"
    )
    carried = [key for key in json.loads(row["parameters"]) if key != "_import"]
    if carried:
        print(f"    carried    : {', '.join(carried)} -> parameters")
    for note in notes:
        print(f"    note       : {note}")


def main() -> int:
    """Map every export file onto catalog rows and write them."""
    parser = argparse.ArgumentParser(
        description="Import NotebookLM JSON rule exports into the rule catalog."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help=f"files or directories (default: {_display_path(DEFAULT_EXPORT_DIR)})",
    )
    parser.add_argument("--dry-run", action="store_true", help="map and report, write nothing")
    parser.add_argument(
        "--force", action="store_true", help="replace rows whose reference already exists"
    )
    parser.add_argument(
        "--strict", action="store_true", help="write nothing if any record is rejected"
    )
    parser.add_argument("--ruleset", default="", help="override the ruleset_id for every record")
    args = parser.parse_args()

    try:
        files = collect_files(args.paths)
    except RecordError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not files:
        print(f"no .json exports found under {DEFAULT_EXPORT_DIR}")
        return 0

    rows: list[dict[str, Any]] = []
    rejected: list[str] = []

    print("=" * 78)
    print("NotebookLM rule import")
    print("=" * 78)

    for path in files:
        print(f"\n{_display_path(path)}")
        print("-" * 78)
        try:
            records, defaults, metadata = read_export(path)
        except RecordError as exc:
            print(f"  FILE REJECTED: {exc}")
            rejected.append(str(exc))
            continue
        if metadata:
            print(f"  export meta: {json.dumps(metadata)[:180]}")
        if defaults:
            print(f"  defaults   : {json.dumps(defaults)[:180]}")

        for index, record in enumerate(records, start=1):
            try:
                row, notes = normalize_record(
                    record, defaults, metadata, path, index, args.ruleset
                )
            except RecordError as exc:
                print(f"\n  record #{index} REJECTED: {exc}")
                rejected.append(str(exc))
                continue
            describe(row, notes)
            rows.append(row)

    print("\n" + "=" * 78)
    print(f"mapped {len(rows)} rules, rejected {len(rejected)}")

    if args.dry_run:
        print("--dry-run: nothing written")
        return 1 if rejected else 0
    if rejected and args.strict:
        print("--strict: nothing written because a record was rejected")
        return 1
    if not rows:
        return 1 if rejected else 0

    from app.environment import load_env_file

    load_env_file()
    service = RuleService()

    existing_by_ruleset: dict[str, dict[str, dict]] = {}

    def existing_for(ruleset_id: str) -> dict[str, dict]:
        """Return reference -> row for a ruleset, fetched once per run."""
        if ruleset_id not in existing_by_ruleset:
            existing_by_ruleset[ruleset_id] = {
                r["reference"]: r for r in service.list_by_ruleset(ruleset_id)
            }
        return existing_by_ruleset[ruleset_id]

    print()
    written = skipped = replaced = 0
    for row in rows:
        current = existing_for(row["ruleset_id"]).get(row["reference"])
        if current and not args.force:
            print(f"  skip    {row['reference']} — already in {row['ruleset_id']} (--force replaces)")
            skipped += 1
            continue
        if current:
            service.delete_rule(current["id"])
            replaced += 1
        try:
            service.create_rule(**row)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            print(f"error writing {row['reference']}: {exc}", file=sys.stderr)
            return 1
        print(f"  written {row['reference']} -> {row['ruleset_id']}")
        written += 1

    print(f"\nwrote {written} rules ({replaced} replaced), skipped {skipped}")
    for ruleset_id in sorted({row["ruleset_id"] for row in rows}):
        print(f"  {ruleset_id}: {len(service.list_by_ruleset(ruleset_id))} rules in catalog")
    print(
        "\nImported rows default to needs_review=True and confidence 0.5: a rule a\n"
        "language model read out of a standard is a draft until a human confirms it.\n"
        "Review them before the ruleset drives any verdict."
    )
    return 1 if rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
