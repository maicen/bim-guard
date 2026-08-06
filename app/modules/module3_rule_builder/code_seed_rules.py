"""Load and seed baseline building-code rules from canonical JSON rulesets."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from config import DB_PATH, SOURCE_DOC_SEED
    from module3_rule_builder.rule_generator import RuleGenerator
    from module3_rule_builder.rule_store import RuleStore
except ImportError:
    from app.modules.config import DB_PATH, SOURCE_DOC_SEED
    from app.modules.module3_rule_builder.rule_generator import RuleGenerator
    from app.modules.module3_rule_builder.rule_store import RuleStore


_RULESETS_DIR = Path(__file__).resolve().parents[3] / "data" / "rulesets"
_RULESET_CANDIDATES = (
    _RULESETS_DIR / "building_code_part9_ruleset.json",
)


def _resolve_ruleset_path() -> Path:
    """Return the first available baseline ruleset path."""
    for path in _RULESET_CANDIDATES:
        if path.exists():
            return path
    return _RULESET_CANDIDATES[0]


def _load_seed_rules() -> list[dict]:
    """Read baseline code rules from the JSON ruleset file."""
    payload = json.loads(_resolve_ruleset_path().read_text(encoding="utf-8"))
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ValueError("Invalid baseline ruleset: expected a 'rules' array")
    return rules


BASELINE_CODE_RULES = _load_seed_rules()


def seed_rules(store: RuleStore, generator: RuleGenerator) -> int:
    """Seed baseline code rules when the target store is empty."""
    existing_count = store.count()

    if existing_count > 0:
        print(f"[SeedRules] DB already has {existing_count} rules - skipping seed")
        print("  To re-seed, call store.clear_all_rules() first")
        return 0

    print(f"[SeedRules] Seeding {len(BASELINE_CODE_RULES)} baseline code rules...\n")
    saved_ids = generator.save_batch(BASELINE_CODE_RULES, source_doc=SOURCE_DOC_SEED)
    print(f"\n[SeedRules] Done - {len(saved_ids)} rules saved to DB")
    return len(saved_ids)


if __name__ == "__main__":
    store = RuleStore(DB_PATH)
    generator = RuleGenerator(store)
    seed_rules(store, generator)

    print("\nRules in DB by target:")
    summary = store.summary()
    for target, count in summary["by_entity"].items():
        print(f"  {target:<30} {count} rules")
