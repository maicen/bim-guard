"""
app/modules/module2_producer/hermes_config_expanded.py

Blue Halo — Phase 2 config generator: expands Hermes' raw standards
research into a jurisdiction ClearanceConfig JSON file.

hermes_standards_research_summary.json (project root) is Hermes' raw,
shallow per-standard research output: one combined transverse/longitudinal
spacing string, one min_clearance string, one importance_factor string per
standard — not yet in the CONFIG TEMPLATE OUTPUT FORMAT that
halo_volume_generator.load_clearance_config() expects (see
HERMES_CONTEXT.md's "CONFIG TEMPLATE OUTPUT FORMAT" section).

This script:
  1. Reads that raw research summary.
  2. Extracts the EN 1998-1 and DIN 4149 entries — Blue Halo's Priority 1
     standards per HERMES_CONTEXT.md.
  3. Parses each entry's free-text fields into structured numeric values,
     converting imperial units to metric where present.
  4. Merges the two standards into ONE combined jurisdiction config using a
     governing-value (most conservative) rule per field — the same
     resolution strategy HERMES_CONTEXT.md's own "Conflict Resolution
     Needed" / "Consensus Rules" sections describe.
  5. Writes the result as valid JSON matching the full CONFIG TEMPLATE
     OUTPUT FORMAT: metadata, seismic_parameters, thresholds, brace_types
     (all four variants), clearance_rules, angle_constraints,
     standards_full_citations.
  6. Validates the output: a JSON round-trip, every required field present,
     and a real load through load_clearance_config() (Phase 1/2
     integration), not just structural inspection.

DATA QUALITY — every number in the output traces back to a source field
parsed from hermes_standards_research_summary.json, or is explicitly
documented below as computed (angle_ideal/tolerance are the sourced
range's midpoint/half-range) or as a data gap (a value the raw research
never provided, left at 0/null/empty rather than invented). See
GOVERNING_RULE_NOTES and the generated metadata.data_gaps for exactly
which fields fall into each category. Per HERMES_CONTEXT.md's "No
Hallucination" rule, nothing here is guessed and passed off as sourced.

Usage:
    uv run python app/modules/module2_producer/hermes_config_expanded.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = REPO_ROOT / "hermes_standards_research_summary.json"
OUTPUT_PATH = REPO_ROOT / "hermes_case_study_and_config.json"

TARGET_STANDARDS = ("EN 1998-1", "DIN 4149")

# Blue Halo's generic bracing-hardware taxonomy (halo_volume_generator.BraceType
# has no NFPA-style "fire" vs "mechanical" split, but jurisdiction configs may
# carry both angle-iron sub-variants — see _classify_brace_type's prefix match).
BRACE_VARIANTS = ("angle_fire", "angle_mechanical", "cable", "rod")

# Generic bracing-hardware footprints (angle bracket / cable clamp / rod
# clamp footprint) — physical hardware dimensions, NOT sourced from any
# seismic standard's clauses. Flagged in every generated config's
# metadata.data_gaps rather than presented as sourced.
_GENERIC_FOOTPRINT_MM: dict[str, list[int]] = {
    "angle_fire": [120, 120],
    "angle_mechanical": [120, 120],
    "cable": [50, 50],
    "rod": [100, 100],
}

_UNIT_TO_METRES = {"m": 1.0, "in": 0.0254, "ft": 0.3048}
_UNIT_TO_MM = {"mm": 1.0, "in": 25.4, "ft": 304.8}


# ═══════════════════════════════════════════════════════════════════════════
# Free-text parsing — hermes_standards_research_summary.json's fields are
# human-readable strings, not structured numbers.
# ═══════════════════════════════════════════════════════════════════════════


def _parse_importance_factors(raw: str) -> dict[str, float]:
    """'1.0 (standard, 1.5 for critical facilities)' -> {"standard": 1.0, "hospital": 1.5}."""
    numbers = re.findall(r"[-+]?\d*\.?\d+", raw)
    if not numbers:
        raise ValueError(f"cannot parse importance factors from {raw!r}")
    factors = {"standard": float(numbers[0])}
    if len(numbers) > 1:
        factors["hospital"] = float(numbers[1])
    return factors


def _parse_spacing_m(raw: str) -> tuple[float, float]:
    """'1.0 m (transverse), 1.5 m (longitudinal)' -> (1.0, 1.5), converted to metres."""
    matches = re.findall(r"([-+]?\d*\.?\d+)\s*(m|in|ft)\b", raw)
    if len(matches) < 2:
        raise ValueError(f"cannot parse transverse+longitudinal spacing from {raw!r}")
    (transverse, t_unit), (longitudinal, l_unit) = matches[0], matches[1]
    return (
        float(transverse) * _UNIT_TO_METRES[t_unit],
        float(longitudinal) * _UNIT_TO_METRES[l_unit],
    )


def _parse_clearance_mm(raw: str) -> float:
    """'150 mm from structure' / '12 in from structure' -> millimetres."""
    match = re.search(r"([-+]?\d*\.?\d+)\s*(mm|in|ft)\b", raw)
    if not match:
        raise ValueError(f"cannot parse clearance from {raw!r}")
    return float(match.group(1)) * _UNIT_TO_MM[match.group(2)]


def _parse_pipe_threshold_mm(raw: str | None) -> float | None:
    """'63 mm diameter' / '2.5 in diameter' -> millimetres, or None if absent."""
    if not raw:
        return None
    match = re.search(r"([-+]?\d*\.?\d+)\s*(mm|in)\b", raw)
    return float(match.group(1)) * _UNIT_TO_MM[match.group(2)] if match else None


def _parse_duct_threshold_area_m2(raw: str | None) -> float | None:
    """'8 in diameter' -> circular cross-section area in m^2, or None if absent.

    Some standards (e.g. ASCE 7-22) express the duct bracing threshold as a
    round-duct diameter rather than a rectangular cross-section area. The
    area = pi*(d/2)^2 conversion is a geometry computation, not a sourced
    area value — callers must flag this distinction (see merge_standards'
    data_gaps entry for thresholds.duct_area_sqm).
    """
    if not raw:
        return None
    match = re.search(r"([-+]?\d*\.?\d+)\s*(mm|in|ft|m)\b", raw)
    if not match:
        return None
    unit_to_m = {"m": 1.0, "mm": 0.001, "in": 0.0254, "ft": 0.3048}
    diameter_m = float(match.group(1)) * unit_to_m[match.group(2)]
    return round(math.pi * (diameter_m / 2) ** 2, 4)


def _parse_angle_range_degrees(raw: str) -> tuple[float, float]:
    """'35-70 degrees from horizontal' -> (35.0, 70.0).

    Deliberately not a generic signed-number findall: the range's own
    separator is an unspaced dash ("35-70"), which a `[-+]?\\d+` pattern
    would misread as a sign on the second number ("35", "-70") rather than
    a range delimiter.
    """
    match = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*degrees", raw)
    if not match:
        raise ValueError(f"cannot parse an angle range from {raw!r}")
    return float(match.group(1)), float(match.group(2))


# ═══════════════════════════════════════════════════════════════════════════
# Per-standard extraction
# ═══════════════════════════════════════════════════════════════════════════


class ParsedStandard:
    """Structured numeric values extracted from one raw research entry."""

    def __init__(self, entry: dict):
        self.name: str = entry["standard"]
        self.jurisdiction: str = entry["metadata"]["jurisdiction"]
        self.year = entry["metadata"]["year"]
        self.importance_factors = _parse_importance_factors(
            entry["seismic_parameters"]["importance_factor"]
        )
        self.spacing_transverse_m, self.spacing_longitudinal_m = _parse_spacing_m(
            entry["thresholds"]["restraint_spacing"]
        )
        self.pipe_diameter_mm = _parse_pipe_threshold_mm(entry["thresholds"].get("pipe_threshold"))
        self.duct_threshold_raw: str | None = entry["thresholds"].get("duct_threshold")
        self.duct_area_sqm = _parse_duct_threshold_area_m2(self.duct_threshold_raw)
        self.base_clearance_mm = _parse_clearance_mm(entry["clearance_rules"]["min_clearance"])
        self.angle_min_degrees, self.angle_max_degrees = _parse_angle_range_degrees(
            entry["angle_constraints"]
        )
        self.citations: list[str] = list(entry.get("citations", []))
        self.label = f"{self.name}:{self.year}"


def load_research_summary(path: Path = SOURCE_PATH) -> list[dict]:
    """Load and validate hermes_standards_research_summary.json.

    Raises:
        FileNotFoundError: If path does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: If it is not a JSON array of standard entries.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array of standard entries")
    return data


def extract_target_standards(
    entries: list[dict], names: tuple[str, str] = TARGET_STANDARDS
) -> dict[str, ParsedStandard]:
    """Parse a pair of named standard entries out of the raw research list.

    Args:
        entries: The raw research summary's top-level list.
        names: The two standard names to extract (must match `entries[i]["standard"]`
            exactly), defaulting to Blue Halo's Priority 1 pair (EN 1998-1, DIN 4149).

    Raises:
        ValueError: If either named standard is missing from `entries`.
    """
    by_name = {entry["standard"]: entry for entry in entries}
    missing = [name for name in names if name not in by_name]
    if missing:
        raise ValueError(f"hermes_standards_research_summary.json is missing standard(s): {missing}")
    return {name: ParsedStandard(by_name[name]) for name in names}


# ═══════════════════════════════════════════════════════════════════════════
# Conservative (governing-value) merge across standards
# ═══════════════════════════════════════════════════════════════════════════
# When two applicable standards disagree, Blue Halo applies whichever
# requirement is more conservative for clearance-envelope purposes — the
# same resolution strategy HERMES_CONTEXT.md's own "Conflict Resolution
# Needed" / "Consensus Rules (Acceptable Default)" sections describe for
# combining EN 1998-1 and DIN 4149 into one config.

GOVERNING_RULE_NOTES = {
    "spacing": "tighter (smaller) spacing governs — it requires more restraints, the conservative reading",
    "clearance": "larger clearance governs — it produces a halo big enough to satisfy both standards",
    "pipe_threshold": "lower diameter threshold governs — it brings more pipes into scope for bracing",
    "duct_threshold": "smaller area threshold governs — it brings more ducts into scope for bracing",
    "importance_factor": "higher factor governs — it demands the greater restraint capacity",
    "angle_range": "intersection of both ranges governs — the band any brace satisfying both standards must fall in",
}


def merge_standards(standards: dict[str, ParsedStandard], names: tuple[str, str] = TARGET_STANDARDS) -> dict:
    """Combine two standards into one CONFIG TEMPLATE-shaped dict.

    Args:
        standards: Output of extract_target_standards, keyed by standard name.
        names: The same pair passed to extract_target_standards — determines
            merge order (names[0] first) in every data_gaps message below.
    """
    a = standards[names[0]]
    b = standards[names[1]]

    spacing_transverse_m = min(a.spacing_transverse_m, b.spacing_transverse_m)
    spacing_longitudinal_m = min(a.spacing_longitudinal_m, b.spacing_longitudinal_m)
    base_clearance_mm = max(a.base_clearance_mm, b.base_clearance_mm)

    pipe_candidates = [v for v in (a.pipe_diameter_mm, b.pipe_diameter_mm) if v is not None]
    pipe_diameter_mm = min(pipe_candidates) if pipe_candidates else None

    duct_candidates = [v for v in (a.duct_area_sqm, b.duct_area_sqm) if v is not None]
    duct_area_sqm = min(duct_candidates) if duct_candidates else None

    importance_factors: dict[str, float] = {}
    for key in set(a.importance_factors) | set(b.importance_factors):
        values = [d[key] for d in (a.importance_factors, b.importance_factors) if key in d]
        importance_factors[key] = max(values)

    angle_min = max(a.angle_min_degrees, b.angle_min_degrees)
    angle_max = min(a.angle_max_degrees, b.angle_max_degrees)
    angle_conflict = angle_min > angle_max
    if angle_conflict:
        # No overlap between the two standards' ranges — fall back to the
        # union so the config is still usable, but this must not be read
        # as sourced: flagged below in data_gaps.
        angle_min = min(a.angle_min_degrees, b.angle_min_degrees)
        angle_max = max(a.angle_max_degrees, b.angle_max_degrees)
    angle_ideal = round((angle_min + angle_max) / 2, 1)
    angle_tolerance = round((angle_max - angle_min) / 2, 1)

    if duct_area_sqm is not None:
        basis = "; ".join(
            f"{std.label} duct_threshold={std.duct_threshold_raw!r} -> {std.duct_area_sqm} sqm "
            "(circular cross-section area computed from the sourced diameter, not a directly sourced area value)"
            for std in (a, b)
            if std.duct_threshold_raw
        )
        duct_gap = (
            f"Combined config: duct_area_sqm = min of the available diameter-derived areas ({basis}) — "
            f"{GOVERNING_RULE_NOTES['duct_threshold']}."
        )
    else:
        duct_gap = (
            "thresholds.duct_area_sqm is not present in the source for either standard (no duct_threshold "
            "field found); left null pending standard-specific research."
        )

    data_gaps = [
        f"Combined config: spacing = min({a.label}={a.spacing_transverse_m}/{a.spacing_longitudinal_m}m, "
        f"{b.label}={b.spacing_transverse_m}/{b.spacing_longitudinal_m}m) per axis — {GOVERNING_RULE_NOTES['spacing']}.",
        f"Combined config: base_from_structure_mm = max({a.label}={a.base_clearance_mm}mm, "
        f"{b.label}={b.base_clearance_mm}mm) — {GOVERNING_RULE_NOTES['clearance']}.",
        f"Combined config: pipe_diameter_mm = min({a.label}={a.pipe_diameter_mm}mm, "
        f"{b.label}={b.pipe_diameter_mm}mm) — {GOVERNING_RULE_NOTES['pipe_threshold']}.",
        duct_gap,
        f"Combined config: importance_factors = per-key max across {a.label} and {b.label} — "
        f"{GOVERNING_RULE_NOTES['importance_factor']}.",
        (
            f"Combined config: angle range = intersection of {a.label} "
            f"({a.angle_min_degrees}-{a.angle_max_degrees} deg) and {b.label} "
            f"({b.angle_min_degrees}-{b.angle_max_degrees} deg) — {GOVERNING_RULE_NOTES['angle_range']}."
            if not angle_conflict
            else (
                f"CONFLICT: {a.label} ({a.angle_min_degrees}-{a.angle_max_degrees} deg) and {b.label} "
                f"({b.angle_min_degrees}-{b.angle_max_degrees} deg) angle ranges do not overlap; "
                "the union was used as a fallback and MUST be verified by an engineer of record before use."
            )
        ),
        "angle_constraints.ideal_degrees and tolerance_degrees are computed as the midpoint and "
        "half-range of the combined min/max above, not independently sourced values.",
        "Source research summary gives one combined restraint_spacing and min_clearance per standard, "
        "not broken out per brace-hardware variant; all four brace_types variants below share the same "
        "combined spacing/clearance figures pending brace-specific research.",
        "clearance_rules.seismic_zone_addition_mm and hospital_addition_mm are not present in the source "
        "for either standard; left at 0mm rather than guessed. Both standards scale required restraint "
        "capacity by Importance Factor, not clearance geometry directly, so 0mm additional clearance is "
        "the defensible reading absent clause text stating otherwise — verify against the full clause "
        "text before relying on this.",
        "clearance_rules.adjacent_system_mm is not present in the source for either standard; left at "
        "0mm pending standard-specific research.",
        "seismic_parameters.hazard_factor_default is not present in the source for either standard; "
        "left null pending standard-specific research.",
        "brace_types[*].base_footprint_mm values are generic bracing-hardware footprint placeholders "
        "(not sourced from either standard's clauses) and brace_types[*].standard_sizes are left empty "
        "pending a hardware catalog cross-reference.",
        f"standards_full_citations below are the section-reference citations from "
        f"hermes_standards_research_summary.json ({a.citations + b.citations}), not full bibliographic "
        "citations (author/title/publisher/location) — HERMES_CONTEXT.md's Priority 1/2 research pass "
        "should supply those.",
    ]

    brace_types = {
        variant: {
            "standard_sizes": [],
            "spacing_transverse_m": round(spacing_transverse_m, 3),
            "spacing_longitudinal_m": round(spacing_longitudinal_m, 3),
            "clearance_mm": round(base_clearance_mm, 1),
            "base_footprint_mm": _GENERIC_FOOTPRINT_MM[variant],
        }
        for variant in BRACE_VARIANTS
    }

    return {
        "metadata": {
            "jurisdiction": f"{a.label} + {b.label}",
            "region": f"{a.jurisdiction} / {b.jurisdiction}",
            "created_by": "hermes_config_expanded.py",
            "standards_cited": [a.name, b.name],
            "data_gaps": data_gaps,
            "paywalled_sections": [],
        },
        "seismic_parameters": {
            "hazard_factor_default": None,
            "importance_factors": importance_factors,
        },
        "thresholds": {
            "pipe_diameter_mm": pipe_diameter_mm,
            "duct_area_sqm": duct_area_sqm,
        },
        "brace_types": brace_types,
        "clearance_rules": {
            "base_from_structure_mm": round(base_clearance_mm, 1),
            "seismic_zone_addition_mm": 0,
            "hospital_addition_mm": 0,
            "adjacent_system_mm": 0,
        },
        "angle_constraints": {
            "min_degrees": angle_min,
            "ideal_degrees": angle_ideal,
            "max_degrees": angle_max,
            "tolerance_degrees": angle_tolerance,
        },
        "standards_full_citations": a.citations + b.citations,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════

_REQUIRED_TOP_LEVEL = (
    "metadata",
    "seismic_parameters",
    "thresholds",
    "brace_types",
    "clearance_rules",
    "angle_constraints",
    "standards_full_citations",
)
_REQUIRED_BRACE_FIELDS = (
    "standard_sizes",
    "spacing_transverse_m",
    "spacing_longitudinal_m",
    "clearance_mm",
    "base_footprint_mm",
)
_REQUIRED_CLEARANCE_RULE_FIELDS = (
    "base_from_structure_mm",
    "seismic_zone_addition_mm",
    "hospital_addition_mm",
    "adjacent_system_mm",
)
_REQUIRED_ANGLE_FIELDS = ("min_degrees", "ideal_degrees", "max_degrees", "tolerance_degrees")

# (section, field) pairs that must hold a number (or null for a genuine data
# gap) — never a string. Catches the exact failure mode the pre-existing
# hand-typed hermes_case_study_and_config.json had: clearance_rules values
# like "EN 1998-1: 2006-12 8.4.2.3(1)" where a millimetre figure belonged.
_NUMERIC_LEAF_FIELDS = (
    ("thresholds", "pipe_diameter_mm"),
    ("thresholds", "duct_area_sqm"),
    ("clearance_rules", "base_from_structure_mm"),
    ("clearance_rules", "seismic_zone_addition_mm"),
    ("clearance_rules", "hospital_addition_mm"),
    ("clearance_rules", "adjacent_system_mm"),
    ("angle_constraints", "min_degrees"),
    ("angle_constraints", "ideal_degrees"),
    ("angle_constraints", "max_degrees"),
    ("angle_constraints", "tolerance_degrees"),
)
_NUMERIC_BRACE_FIELDS = ("spacing_transverse_m", "spacing_longitudinal_m", "clearance_mm")


def _numeric_type_problem(path: str, value) -> str | None:
    """None if value is a number or null; otherwise a description of the mismatch.

    isinstance(True, int) is True in Python, so bool is explicitly excluded —
    a JSON `true`/`false` must not silently pass as a valid numeric field.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"{path} = {value!r} ({type(value).__name__}), expected a number or null"
    return None


def validate_config(config: dict) -> list[str]:
    """Structurally validate a generated config. Returns a list of problems
    (empty if none)."""
    problems: list[str] = []

    for key in _REQUIRED_TOP_LEVEL:
        if key not in config:
            problems.append(f"missing top-level key: {key}")

    if set(config.get("brace_types", {}).keys()) != set(BRACE_VARIANTS):
        problems.append(
            f"brace_types keys {sorted(config.get('brace_types', {}).keys())} != {sorted(BRACE_VARIANTS)}"
        )
    for variant, data in config.get("brace_types", {}).items():
        for field in _REQUIRED_BRACE_FIELDS:
            if field not in data:
                problems.append(f"brace_types.{variant} missing field: {field}")

    for field in _REQUIRED_CLEARANCE_RULE_FIELDS:
        if field not in config.get("clearance_rules", {}):
            problems.append(f"clearance_rules missing field: {field}")

    for field in _REQUIRED_ANGLE_FIELDS:
        if field not in config.get("angle_constraints", {}):
            problems.append(f"angle_constraints missing field: {field}")

    if not config.get("standards_full_citations"):
        problems.append("standards_full_citations is empty")

    for section, field in _NUMERIC_LEAF_FIELDS:
        problem = _numeric_type_problem(f"{section}.{field}", config.get(section, {}).get(field))
        if problem:
            problems.append(problem)

    for variant, data in config.get("brace_types", {}).items():
        for field in _NUMERIC_BRACE_FIELDS:
            problem = _numeric_type_problem(f"brace_types.{variant}.{field}", data.get(field))
            if problem:
                problems.append(problem)
        footprint = data.get("base_footprint_mm")
        footprint_ok = (
            isinstance(footprint, list)
            and len(footprint) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in footprint)
        )
        if footprint is not None and not footprint_ok:
            problems.append(
                f"brace_types.{variant}.base_footprint_mm = {footprint!r}, expected a 2-element numeric list"
            )

    try:
        round_tripped = json.loads(json.dumps(config))
    except (TypeError, ValueError) as exc:
        problems.append(f"json.dumps/json.loads round-trip failed: {exc}")
    else:
        if round_tripped != config:
            problems.append("json.dumps/json.loads round-trip changed the data")

    return problems


def validate_phase2_integration(output_path: Path) -> list[str]:
    """Load the written file through the real Phase 1/2 loader, proving
    it is ready for Phase 2 integration — not just structurally valid."""
    sys.path.insert(0, str(REPO_ROOT))
    from app.modules.module2_producer.halo_volume_generator import (  # noqa: PLC0415
        BraceType,
        load_clearance_config,
    )

    problems: list[str] = []
    try:
        loaded = load_clearance_config(output_path)
    except Exception as exc:  # noqa: BLE001 - report any loader failure as a validation problem
        return [f"load_clearance_config() raised {type(exc).__name__}: {exc}"]

    if len(loaded.rules) != len(BRACE_VARIANTS):
        problems.append(f"load_clearance_config() loaded {len(loaded.rules)} rules, expected {len(BRACE_VARIANTS)}")
    for variant in BRACE_VARIANTS:
        rule = loaded.rules.get(variant)
        if rule is None:
            problems.append(f"load_clearance_config() did not load a rule for variant {variant!r}")
            continue
        if rule.base_clearance_mm <= 0:
            problems.append(f"{variant}.base_clearance_mm loaded as {rule.base_clearance_mm} (expected > 0)")

    angle_rule = loaded.rules.get("angle_fire")
    if angle_rule is not None and not angle_rule.angle_min_degrees <= angle_rule.angle_ideal_degrees <= angle_rule.angle_max_degrees:
        problems.append("angle_fire's loaded min <= ideal <= max ordering does not hold")

    if not loaded.rules_for(BraceType.ANGLE_IRON):
        problems.append("rules_for(BraceType.ANGLE_IRON) returned no rules (expected angle_fire + angle_mechanical)")

    return problems


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  hermes_config_expanded.py — Blue Halo Phase 2 config generator")
    print("=" * 70)

    print(f"\nReading {SOURCE_PATH} ...")
    entries = load_research_summary()
    print(f"  {len(entries)} standard(s) in the raw research summary: "
          f"{[e['standard'] for e in entries]}")

    print(f"\nExtracting target standards: {TARGET_STANDARDS}")
    standards = extract_target_standards(entries)
    for name, parsed in standards.items():
        print(f"  {name}: spacing={parsed.spacing_transverse_m}/{parsed.spacing_longitudinal_m}m, "
              f"clearance={parsed.base_clearance_mm}mm, "
              f"angle=[{parsed.angle_min_degrees}-{parsed.angle_max_degrees}]deg, "
              f"pipe_threshold={parsed.pipe_diameter_mm}mm, "
              f"importance_factors={parsed.importance_factors}")

    print("\nMerging into one combined config (governing-value rule per field)...")
    config = merge_standards(standards)
    print(f"  jurisdiction: {config['metadata']['jurisdiction']}")
    print(f"  brace_types: {sorted(config['brace_types'].keys())}")
    print(f"  data_gaps flagged: {len(config['metadata']['data_gaps'])}")

    print("\nValidating structure...")
    structural_problems = validate_config(config)
    if structural_problems:
        for p in structural_problems:
            print(f"  [FAIL] {p}")
    else:
        print("  [PASS] all required fields present, JSON round-trip clean")

    print(f"\nWriting {OUTPUT_PATH} ...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    print(f"  wrote {OUTPUT_PATH.stat().st_size:,} bytes")

    print("\nValidating Phase 2 integration (real load_clearance_config() call)...")
    integration_problems = validate_phase2_integration(OUTPUT_PATH)
    if integration_problems:
        for p in integration_problems:
            print(f"  [FAIL] {p}")
    else:
        print("  [PASS] load_clearance_config() loaded all 4 brace-type rules successfully")

    all_problems = structural_problems + integration_problems
    print("\n" + "=" * 70)
    if all_problems:
        print(f"  OVERALL: FAILED ({len(all_problems)} problem(s))")
    else:
        print("  OVERALL: PASSED — ready for Phase 2 integration")
    print("=" * 70)

    sys.exit(1 if all_problems else 0)
