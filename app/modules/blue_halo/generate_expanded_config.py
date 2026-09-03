"""
app/modules/blue_halo/generate_expanded_config.py

Blue Halo — Phase 2 prep: generate a clean, jurisdiction-pair-agnostic
ClearanceConfig JSON from Hermes' raw standards research, with an
EU -> US fallback.

Reuses hermes_config_expanded.py's parsing/merging/validation (the same
free-text extraction, governing-value merge rule, and structural
validation already exercised — and bug-fixed — against the EN 1998-1 +
DIN 4149 pair) rather than duplicating it, and generalises it over which
pair of standards to combine:

  1. Try Blue Halo's Priority 1 pair (EN 1998-1 + DIN 4149).
  2. If either is missing from hermes_standards_research_summary.json,
     fall back to the Priority 2/3 US pair (ASCE 7-22 + NFPA 13).
  3. Whichever pair is used, write the full CONFIG TEMPLATE OUTPUT FORMAT
     JSON to data/rulesets/config_<pair>.json and validate it three ways:
     structural completeness, numeric-not-string field types, and a real
     load through halo_volume_generator.load_clearance_config().

Usage:
    uv run python app/modules/blue_halo/generate_expanded_config.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from app.modules.blue_halo.hermes_config_expanded import (  # noqa: E402
    SOURCE_PATH,
    extract_target_standards,
    load_research_summary,
    merge_standards,
    validate_config,
    validate_phase2_integration,
)

# (standard names, output filename) in fallback order — EU pair first
# (Blue Halo's Priority 1 per HERMES_CONTEXT.md), US pair as fallback.
CANDIDATE_PAIRS: tuple[tuple[tuple[str, str], str], ...] = (
    (("EN 1998-1", "DIN 4149"), "config_en_1998_1_din_4149.json"),
    (("ASCE 7-22", "NFPA 13"), "config_asce_7_22_nfpa_13.json"),
)

OUTPUT_DIR = REPO_ROOT / "data" / "rulesets"


def select_pair(entries: list[dict]) -> tuple[dict, tuple[str, str], str]:
    """Try each candidate pair in order; return the first one fully present.

    Returns:
        (standards, names, output_filename) for the first pair where both
        named standards exist in `entries`.

    Raises:
        ValueError: If no candidate pair is fully present in `entries`.
    """
    attempts: list[str] = []
    for names, filename in CANDIDATE_PAIRS:
        try:
            return extract_target_standards(entries, names=names), names, filename
        except ValueError as exc:
            attempts.append(str(exc))
    raise ValueError(
        "no candidate standard pair is fully present in the research summary:\n  "
        + "\n  ".join(attempts)
    )


if __name__ == "__main__":
    print("=" * 70)
    print("  generate_expanded_config.py — Blue Halo Phase 2 config generator")
    print("=" * 70)

    print(f"\nReading {SOURCE_PATH} ...")
    entries = load_research_summary()
    available = [e["standard"] for e in entries]
    print(f"  {len(entries)} standard(s) in the raw research summary: {available}")

    print(f"\nSelecting a standards pair (fallback order: "
          f"{[names for names, _ in CANDIDATE_PAIRS]})...")
    standards, names, filename = select_pair(entries)
    print(f"  using: {names}")
    for name, parsed in standards.items():
        print(f"    {name}: spacing={parsed.spacing_transverse_m}/{parsed.spacing_longitudinal_m}m, "
              f"clearance={parsed.base_clearance_mm}mm, "
              f"angle=[{parsed.angle_min_degrees}-{parsed.angle_max_degrees}]deg, "
              f"pipe_threshold={parsed.pipe_diameter_mm}mm, "
              f"duct_area={parsed.duct_area_sqm}sqm, "
              f"importance_factors={parsed.importance_factors}")

    print("\nMerging into one combined config (governing-value rule per field)...")
    config = merge_standards(standards, names=names)
    print(f"  jurisdiction: {config['metadata']['jurisdiction']}")
    print(f"  brace_types: {sorted(config['brace_types'].keys())}")
    print(f"  data_gaps flagged: {len(config['metadata']['data_gaps'])}")

    print("\nValidating structure (required fields + numeric field types)...")
    structural_problems = validate_config(config)
    if structural_problems:
        for p in structural_problems:
            print(f"  [FAIL] {p}")
    else:
        print("  [PASS] all required fields present, numeric fields are numbers, JSON round-trip clean")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename
    print(f"\nWriting {output_path} ...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    print(f"  wrote {output_path.stat().st_size:,} bytes")

    print("\nValidating Phase 2 integration (real load_clearance_config() call)...")
    integration_problems = validate_phase2_integration(output_path)
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
        print(f"  OVERALL: PASSED — {output_path.relative_to(REPO_ROOT)} is ready for Phase 2 integration")
    print("=" * 70)

    sys.exit(1 if all_problems else 0)
