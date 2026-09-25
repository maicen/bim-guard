"""Seed built-in BIMGuard engine rulesets into the shared rules table.

The seeding operations are idempotent: each routine checks whether its
``ruleset_id`` already exists before inserting rows.
"""

import json
from pathlib import Path

from app.logging_config import get_logger
from app.services.rules_service import RuleService
from app.services.static_data_service import StaticDataService

logger = get_logger(__name__)

_RULESET_DIR = Path(__file__).resolve().parents[2] / "data" / "rulesets"

_DEFAULT_CODE_RULESET_FILES = (
    "building_code_part9_ruleset.json",
    "building_code_part9_ext_ruleset.json",
    "fire_safety_starter_ruleset.json",
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _load(filename: str) -> dict:
    asset_key_map = {
        "building_code_part9_ruleset.json": "ruleset:BUILDING-CODE-PART9",
        "building_code_part9_ext_ruleset.json": "ruleset:BUILDING-CODE-PART9-EXT",
    }

    asset_key = asset_key_map.get(filename)
    if asset_key:
        payload = StaticDataService().get_asset_json(asset_key)
        if isinstance(payload, dict):
            return payload

    # Database-primary, repository fallback.
    local_path = _RULESET_DIR / filename
    if local_path.is_file():
        payload = json.loads(local_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload

    raise RuntimeError(f"Missing static ruleset asset: {filename}")


def _create(svc: RuleService, **kwargs) -> None:
    """Thin wrapper that sets extraction_method='seed' by default."""
    kwargs.setdefault("extraction_method", "seed")
    kwargs.setdefault("severity", "mandatory")
    svc.create_rule(**kwargs)


def _existing_references(svc: RuleService, ruleset_id: str) -> set[str]:
    """Return the references already stored for a ruleset.

    Insertion is one network round trip per row, so a seeding run that is
    interrupted part-way leaves the ruleset present but incomplete. Callers use
    this to resume: skip the references already written, insert the rest.

    Reads the table rather than the cached ``list_by_ruleset`` -- see
    :meth:`RuleService.references_for_ruleset` for why a cached answer let a
    duplicate set of band rows through on 2026-09-06.
    """
    return svc.references_for_ruleset(ruleset_id)


# Part 9's seed content has, at different times, cited the same clause
# under two conventions -- "OBC 9.6.4" and "CODE 9.6.4" -- same clause
# number, different prefix. Comparing raw `reference` strings missed that
# these are the same rule, letting the rename accumulate a duplicate row
# every time the other convention's seed source ran (audit: 18 rows across
# 12 clauses found 2026-09-18, see
# supabase/migrations/20260918155453_dedupe_part9_rules_by_content.sql and
# its 2026-09-18 follow-up). Normalizing the prefix away here closes that
# gap at its source instead of relying on a one-time cleanup migration.
_LEGACY_REFERENCE_PREFIXES = ("OBC ", "CODE ")


def _normalize_reference(reference: str) -> str:
    """Strip a known reference-prefix rename so the same clause dedupes as one rule."""
    stripped = reference.strip()
    upper = stripped.upper()
    for prefix in _LEGACY_REFERENCE_PREFIXES:
        if upper.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped


def _rule_key(reference: str, target: str, prop: str) -> tuple[str, str, str]:
    """Identity of one code rule within its ruleset.

    Reference alone is not unique: Part 9 cites one clause against several
    element classes (9.8.2.2.(3) covers both IfcStairFlight and IfcSlab), and
    the QA rules share the reference "BIMGuard QA" entirely. Target class and
    property name are what separate them. The reference component is
    normalized (see _normalize_reference) so a bare renumbering of the same
    clause's citation prefix is not mistaken for a new rule.
    """
    return (_normalize_reference(reference), target.strip(), prop.strip())


def _seed_json_ruleset(svc: RuleService, filename: str) -> int:
    """Seed one ruleset JSON document via RuleService.import_ruleset().

    Resumes rather than skipping: this previously returned 0 as soon as the
    ruleset had any row at all, so a set that was interrupted part way through
    stayed permanently incomplete. Only the rules not already stored are
    imported.
    """
    payload = _load(filename)
    ruleset_id = str(payload.get("ruleset_id") or "").strip()
    if not ruleset_id:
        raise ValueError(f"Ruleset file '{filename}' is missing ruleset_id")

    stored = {
        _rule_key(
            str(row.get("reference") or ""),
            str(row.get("target_ifc_class") or ""),
            str(row.get("property_name") or ""),
        )
        for row in svc.rows_for_ruleset(ruleset_id)
    }

    pending = []
    for rule in payload.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        key = _rule_key(
            str(rule.get("ref") or rule.get("reference") or ""),
            str(rule.get("target") or rule.get("target_ifc_class") or ""),
            str(rule.get("property_name") or ""),
        )
        if key in stored:
            continue
        stored.add(key)
        pending.append(rule)

    if not pending:
        return 0
    return svc.import_ruleset({**payload, "rules": pending})


def seed_architectural_code_rules(svc: RuleService) -> int:
    """Ensure hardcoded architectural egress, exit, daylight, and fire separation rules exist in DB."""
    count = 0
    rules_to_seed = [
        {
            "reference": "CODE 9.9.10.1",
            "rule_type": "egress_path",
            "rule_category": "circulation",
            "description": "Maximum egress travel distance from habitable room to exit — 25.0 m",
            "target_ifc_class": "IfcSpace",
            "property_name": "TravelDistance",
            "operator": "<=",
            "check_value": 25.0,
            "unit": "m",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
        {
            "reference": "CODE 9.9.4.1",
            "rule_type": "numeric_comparison",
            "rule_category": "circulation",
            "description": "Minimum number of exterior exits per building storey — 1",
            "target_ifc_class": "IfcBuildingStorey",
            "property_name": "ExitCount",
            "operator": ">=",
            "check_value": 1.0,
            "unit": "count",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
        {
            "reference": "CODE 9.7.2.3",
            "rule_type": "spatial_adjacency",
            "rule_category": "daylight",
            "description": "Minimum window glazing area to floor area ratio for habitable spaces — 1/10 (0.10)",
            "target_ifc_class": "IfcSpace",
            "property_name": "DaylightRatio",
            "operator": ">=",
            "check_value": 0.10,
            "unit": "ratio",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
        {
            "reference": "CODE 9.10.9.14.PW",
            "rule_type": "spatial_adjacency",
            "rule_category": "fire_safety",
            "description": "Fire-rated wall between dwelling units (party wall) — minimum 45-minute fire resistance",
            "target_ifc_class": "IfcWall",
            "property_name": "FireRating",
            "operator": ">=",
            "check_value": 45.0,
            "unit": "min",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
    ]

    # Window data-completeness checks: presence-only, not code-mandated
    # thresholds. Life-safety window properties (fire/acoustic/security
    # rating, thermal transmittance, egress/fire-exit flags, ...) live in
    # Pset_WindowCommon but are almost never populated by default in
    # authoring tools — ComplianceComparator already treats a missing
    # property as MISSING_DATA (or PARTIAL if some elements have it), never
    # PASS, so these rules surface "this window has no documented X" rather
    # than asserting compliance against a threshold nobody has verified.
    # Kept in a separate ruleset_id / mechanism from the seeded "CODE"
    # building-code rows above so they're never mistaken for real regulatory citations.
    window_pset_common_fields = [
        "FireRating",
        "AcousticRating",
        "SecurityRating",
        "ThermalTransmittance",
        "Infiltration",
        "IsExternal",
        "HandicapAccessible",
        "FireExit",
        "SelfClosing",
        "SmokeStop",
    ]
    for field_name in window_pset_common_fields:
        rules_to_seed.append({
            "reference": f"BIMGUARD-WIN.{field_name}",
            "rule_type": "property_presence",
            "rule_category": "window_documentation",
            "description": (
                f"Pset_WindowCommon.{field_name} should be documented on every "
                f"window (BIM-Guard data-completeness check — flags undocumented "
                f"data as MISSING_DATA, not a jurisdiction-specific threshold)"
            ),
            "target_ifc_class": "IfcWindow",
            "property_name": field_name,
            "operator": "documented",
            "ruleset_id": "BIMGUARD-WINDOW-DATA",
            "mechanism": "DATA_QC",
            "category": "Arch",
            "severity": "recommended",
        })

    # Normalized the same way as _rule_key: these hardcoded "CODE ..."
    # references duplicate clauses the JSON-imported rulesets above already
    # seeded under an "OBC ..." prefix, and a raw-reference guard missed that.
    existing_refs = {_normalize_reference(ref) for ref in svc.all_references()}

    for item in rules_to_seed:
        if _normalize_reference(item["reference"]) not in existing_refs:
            _create(svc, **item)
            count += 1

    return count


def seed_default_code_rulesets(svc: RuleService) -> dict[str, int]:
    """Seed baseline/extended building-code rulesets from JSON files."""
    seeded: dict[str, int] = {}
    for filename in _DEFAULT_CODE_RULESET_FILES:
        payload = _load(filename)
        ruleset_id = str(payload.get("ruleset_id") or "").strip() or filename
        seeded[ruleset_id] = _seed_json_ruleset(svc, filename)
    seed_architectural_code_rules(svc)
    return seeded


# ── Public entry point ────────────────────────────────────────────────────────


def seed_engine_rulesets(svc: RuleService) -> dict[str, int]:
    """Seed every engine ruleset the application ships with.

    Covers the architectural code rules.

    Idempotent: skips any ruleset already present in the DB.
    Returns a dict of {ruleset_id: rows_inserted}.
    """
    seeders = (("BUILDING-CODE-PART9-ARCH", seed_architectural_code_rules),)

    # Isolated per ruleset. A shared try/except let one unreachable static
    # asset abort every seeder after it.
    seeded: dict[str, int] = {}
    for ruleset_id, seeder in seeders:
        try:
            seeded[ruleset_id] = seeder(svc)
        except Exception as exc:
            print(f"[RulesetSeeder] Warning: {ruleset_id} not seeded: {exc}")
    return seeded
