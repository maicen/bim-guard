"""Map MIL-STD-889B Table II alloy designations onto GC-001 catalog materials.

Table II names 93 specific alloys and tempers; the GC-001 catalog carries 20
generic material families. This script records the mapping between them as
``material_alias`` rule rows so that ``resolve_material()`` recognises the
specific designations an IFC model is likely to carry (``Al alloy 6061-T6``,
``Stainless steel 316L (passive)``) instead of falling through to its default.

The mapping is engineering judgement and is graded:

``exact``
    The designation is the family, or an unambiguous member of it
    (``Steel 1010`` -> ``carbon_steel``, ``Al alloy 6061-T6`` -> ``aluminium``).
``approximate``
    A member of a family the catalog does not carry separately, mapped to its
    nearest catalog neighbour (ferritic ``430`` -> the austenitic ``ss304_*``
    entries). Recorded so it can be audited rather than silently trusted.

Designations with no defensible catalog counterpart -- tantalum, tungsten,
Monel, lead, tin, nickel -- are deliberately **left unmapped** rather than
forced onto an approximate neighbour. See the caveat printed by this script.

The write is strictly additive: aliases are appended after the engine's
built-in ``MATERIAL_ALIASES``, so every string that resolves today resolves
identically afterwards. Only previously unrecognised strings change outcome.

Usage::

    python scripts/map_mil_std_synonyms.py [--dry-run]

Exit codes: ``0`` success, ``1`` write failure, ``2`` source data unavailable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

TABLE_II_JSON = REPO_ROOT / "data" / "reference" / "mil_std_889b_table_ii.json"
RULESET_ID = "BIMGUARD-GC-001"
ALIAS_RULE_TYPE = "material_alias"

#: Ordered (regex, catalog key, confidence) rules. First match wins, so the
#: specific patterns must precede the generic stainless catch-all.
MAPPING_RULES: list[tuple[str, str, str]] = [
    (r"^Magnesium|^M[gG] Alloy", "magnesium", "exact"),
    (r"^Zinc \(hot-dip", "zinc", "exact"),
    (r"^Cadmium", "cadmium", "exact"),
    (r"^Al(uminum)? ?(alloy|\(Al\))", "aluminium", "exact"),
    (r"^Steel 1010", "carbon_steel", "exact"),
    (r"^Iron, cast", "cast_iron", "exact"),
    (r"^Copper 110|^Copper \(plated", "copper", "exact"),
    (r"^Copper-Nickel", "copper", "approximate"),
    (r"^Titan(ium|um)", "titanium", "exact"),
    (r"^Gold$", "gold", "exact"),
    (r"^Graphite$", "graphite", "exact"),
    (r"[Bb]ronze", "bronze", "exact"),
    (r"[Bb]rass|Muntz metal", "brass", "exact"),
    (r"^Nickel-silver", "brass", "approximate"),
    # Stainless: 316/316L keep their own catalog entries; every other grade is
    # mapped by state onto the nearest austenitic neighbour the catalog holds.
    (r"^Stainless steel 316L? \(active\)", "ss316_active", "exact"),
    (r"^Stainless steel 316L? \(passive\)", "ss316_passive", "exact"),
    (r"^Stainless steel .*\(active\)", "ss304_active", "approximate"),
    (r"^Stainless steel .*\(passive\)", "ss304_passive", "approximate"),
    (r"^(AM3[05][05]|A286|Carpenter 20) \(active\)", "ss304_active", "approximate"),
    (r"^(AM3[05][05]|A286|Carpenter 20) \(passive\)", "ss304_passive", "approximate"),
]

#: Designations intentionally not mapped, with the reason.
UNMAPPED_REASONS = {
    "Beryllium": "no catalog counterpart",
    "Uranium": "not a building material",
    "Indium": "no catalog counterpart",
    "Tin": "no catalog counterpart",
    "Lead": "no catalog counterpart",
    "Nickel (": "no catalog counterpart",
    "Chromium": "no catalog counterpart",
    "Tantalum": "no catalog counterpart",
    "Tungsten": "no catalog counterpart",
    "Niobium": "no catalog counterpart",
    "Molybdenum": "no catalog counterpart",
    "Monel": "Ni-Cu alloy, no catalog counterpart",
    "Silver": "pure silver differs from the catalog's silver_solder braze alloy",
}


def lexical_variants(name: str) -> list[str]:
    """Return lower-cased lookup strings an IFC material name might carry."""
    base = name.lower().strip()
    variants = {base}
    # Drop the trailing state qualifier: "stainless steel 304 (active)".
    variants.add(re.sub(r"\s*\([^)]*\)\s*$", "", base).strip())
    # Bare designation: "al alloy 6061-t6" -> "6061-t6".
    bare = re.sub(
        r"^(al alloy|aluminum|stainless steel|brass,?|bronze,?|copper)\s*", "", base
    )
    if bare and bare != base:
        variants.add(bare.strip())
    # Bare grade numbers ("220", "464") are deliberately NOT emitted:
    # resolve_material() falls back to substring matching, so a digit-only
    # alias would match dimensions and tags -- "Insulation 220mm" would
    # resolve to bronze. The few well-known grade numbers that are safe
    # enough to carry (304, 316, 6061, 2205) are already built into the
    # engine's own MATERIAL_ALIASES.
    # A variant must begin with an alphanumeric. Stripping the family prefix
    # from "Brass (plated)" leaves the bare qualifier "(plated)", and because
    # resolve_material() substring-matches, such an alias would hijack every
    # other plated metal -- "Nickel (plated)" would resolve to brass.
    return sorted(
        v
        for v in variants
        if len(v) >= 3 and v[0].isalnum() and not v.replace("-", "").isdigit()
    )


def build_aliases(entries: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    """Return the alias mapping and the list of unmapped Table II entries."""
    compiled = [(re.compile(p), key, conf) for p, key, conf in MAPPING_RULES]
    aliases: dict[str, dict] = {}
    unmapped: list[dict] = []

    for entry in entries:
        name = entry["name"]
        target = next(
            ((key, conf) for regex, key, conf in compiled if regex.search(name)), None
        )
        if target is None:
            reason = next(
                (r for prefix, r in UNMAPPED_REASONS.items() if name.startswith(prefix)),
                "no mapping rule matched",
            )
            unmapped.append({"name": name, "rank": entry["rank"], "reason": reason})
            continue

        key, confidence = target
        for variant in lexical_variants(name):
            # First writer wins: an earlier, more specific entry keeps the alias.
            aliases.setdefault(
                variant,
                {
                    "material_key": key,
                    "confidence": confidence,
                    "source_name": name,
                    "source_rank": entry["rank"],
                },
            )
    return aliases, unmapped


def existing_engine_aliases() -> set[str]:
    """Return alias strings the engine already hardcodes, to avoid clashes."""
    from app.engines.bimguard_corrosion_engine import MATERIAL_ALIASES

    return set(MATERIAL_ALIASES)


def main() -> int:
    """Build the alias set and persist it as material_alias rule rows."""
    parser = argparse.ArgumentParser(description="Map Table II designations to GC-001.")
    parser.add_argument("--dry-run", action="store_true", help="build but do not write")
    args = parser.parse_args()

    if not TABLE_II_JSON.exists():
        print(f"error: {TABLE_II_JSON} missing", file=sys.stderr)
        return 2
    entries = json.loads(TABLE_II_JSON.read_text(encoding="utf-8"))["entries"]

    from app.environment import load_env_file

    load_env_file()

    aliases, unmapped = build_aliases(entries)
    builtin = existing_engine_aliases()
    collisions = sorted(set(aliases) & builtin)
    for alias in collisions:
        # The engine's own table stays authoritative.
        aliases.pop(alias, None)

    print(f"Table II entries:         {len(entries)}")
    print(f"mapped to catalog keys:   {len(entries) - len(unmapped)}")
    print(f"left unmapped:            {len(unmapped)}")
    print(f"alias strings generated:  {len(aliases)}")
    collision_note = f"  ({', '.join(collisions)})" if collisions else ""
    print(f"deferred to built-ins:    {len(collisions)}{collision_note}")

    by_key: dict[str, int] = {}
    for meta in aliases.values():
        by_key[meta["material_key"]] = by_key.get(meta["material_key"], 0) + 1
    print("\naliases per catalog material:")
    for key, count in sorted(by_key.items(), key=lambda kv: -kv[1]):
        print(f"  {key:<16} {count}")

    approx = sum(1 for m in aliases.values() if m["confidence"] == "approximate")
    print(f"\nconfidence: {len(aliases) - approx} exact, {approx} approximate")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    from app.services.rules_service import RuleService

    service = RuleService()
    existing = {
        row["reference"]
        for row in service.list_by_ruleset(RULESET_ID)
        if row.get("rule_type") == ALIAS_RULE_TYPE
    }

    written = skipped = 0
    for alias, meta in sorted(aliases.items()):
        slug = re.sub(r"[^a-z0-9]+", "_", alias).strip("_").upper()
        reference = f"GC-001.ALIAS.{slug}"
        if reference in existing:
            skipped += 1
            continue
        try:
            service.create_rule(
                reference=reference,
                rule_type=ALIAS_RULE_TYPE,
                description=f"{meta['source_name']} -> {meta['material_key']}",
                ruleset_id=RULESET_ID,
                keyword=alias,
                parameters=json.dumps({**meta, "alias": alias}),
                source_text=(
                    f"MIL-STD-889B Table II rank {meta['source_rank']}: "
                    f"{meta['source_name']}"
                ),
                mechanism="galvanic",
                extraction_method="derived",
            )
            written += 1
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            print(f"error writing {reference}: {exc}", file=sys.stderr)
            return 1

    print(f"\nwrote {written} material_alias rows, skipped {skipped} already present")

    print("\nCAVEAT - these resolve via the engine default, not an alias:")
    for item in unmapped:
        print(f"  rank {item['rank']:>3}  {item['name']:<38} ({item['reason']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
