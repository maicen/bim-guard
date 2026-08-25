"""Load and seed baseline building-code rules from database static assets."""

from __future__ import annotations

from app.modules.config import SOURCE_DOC_SEED
from app.modules.module3_rule_builder.rule_generator import RuleGenerator
from app.modules.module3_rule_builder.rule_store import RuleStore
from app.services.static_data_service import StaticDataService


def _load_seed_rules() -> list[dict]:
    """Read baseline code rules from database static assets."""
    payload = StaticDataService().get_asset_json("ruleset:BUILDING-CODE-PART9")
    if not isinstance(payload, dict):
        raise ValueError("Missing static asset ruleset:BUILDING-CODE-PART9")
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
    store = RuleStore()
    generator = RuleGenerator(store)
    seed_rules(store, generator)

    print("\nRules in DB by target:")
    summary = store.summary()
    for target, count in summary["by_entity"].items():
        print(f"  {target:<30} {count} rules")
