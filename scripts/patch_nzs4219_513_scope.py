"""Narrow the scope of NZS-4219-5.13 in the rule catalog.

The clause requires a seismic clearance around independently supported
services in ceiling voids, above a mass threshold. It was imported from
``data/notebooklm_exports/real_seismic_rules.json`` as::

    target_ifc_class : IfcDistributionElement
    applies_when     : {"location": "ceiling_void", "mass_kg": {"min": 10.0}}

Both halves of that scope are inert against the current extractor, and the
result is a rule that governs every distribution element in the model:

* ``IfcDistributionElement`` is the abstract supertype of ducts, cables,
  fittings, terminals and pipe alike, so the target class narrows nothing.
* ``mass_kg`` and ``location`` are not keys
  ``comparator._predicate_key`` recognises. An unrecognised key is
  UNDETERMINED, and an undetermined *scope* deliberately keeps the element in
  scope (an unevaluable narrowing must never silently suppress a check). So
  the mass threshold does not exclude anything either.

This patch replaces the scope with one the extractor can actually evaluate.

The proxy
---------
``nominal_diameter_mm`` maps to ``NominalDiameter`` in
``_SCOPE_NUMERIC_PROPERTIES`` and is resolved per element by Module 2, so a
band on it is enforced today. Nominal bore stands in for mass: a run at NB50
and above, water-filled, is the size at which the clause's 10 kg threshold
starts to be met in practice. It is a proxy, not the clause's own test --
recorded as such in ``parameters.scope_patch`` so it is not mistaken for the
standard's wording during review.

AND, not OR
-----------
``_evaluate_predicate`` ANDs across a predicate's keys; there is no ``any_of``
construct, so "mass OR diameter" cannot be expressed. What makes the pairing
work today is the three-valued outcome, not a disjunction:

    diameter NO_MATCH  -> settles the predicate, element out of scope
    diameter MATCH + mass UNDETERMINED -> UNDETERMINED, element stays in scope

That is the behaviour wanted: the diameter band does the narrowing, and the
unevaluable mass key rides along without suppressing anything. ``mass_kg`` is
kept for exactly that reason -- it holds the clause's real threshold and
surfaces in ``undetermined_predicates`` so the gap stays visible.

**The pairing inverts the day ``mass_kg`` becomes extractable.** Both keys
would then be enforced, and a heavy small-bore run -- under NB50 but over
10 kg -- would fall out of scope, which the clause does not intend. When mass
lands in ``_SCOPE_NUMERIC_PROPERTIES``, drop ``nominal_diameter_mm`` from this
rule rather than leaving both in place. ``--revert`` restores the imported
scope; it does not do that migration.

Retiring the proxy
------------------
That day has arrived. ``app/modules/ifc_reader/ifc_seismic.py`` resolves
``mass_kg`` per element and ``comparator._SCOPE_NUMERIC_PROPERTIES``
now maps ``mass_kg`` -> ``MassKg``, which is the exact condition
``scope_patch.retire_proxy_when`` was written against. ``--retire-proxy``
drops ``nominal_diameter_mm`` and leaves the clause's own threshold to do the
narrowing on its own.

This is not ``--revert``. Revert restores the *imported* scope, abstract
target class and all; retiring keeps the IfcPipeSegment narrowing -- which was
always correct and is independent of the proxy -- and removes only the
stand-in.

Why the proxy is now a false negative, not merely redundant: the keys are
ANDed, so a 25 mm run carrying 40 kg reads NO_MATCH on the diameter band,
which SETTLES the predicate. The element drops out of scope and the clause
that governs it never runs. Under the old extractor that could not happen,
because the diameter band was the only enforceable key it had.

Usage::

    python scripts/patch_nzs4219_513_scope.py                    # dry run (default)
    python scripts/patch_nzs4219_513_scope.py --print-sql        # emit the SQL form
    python scripts/patch_nzs4219_513_scope.py --apply            # write to Supabase
    python scripts/patch_nzs4219_513_scope.py --revert --apply
    python scripts/patch_nzs4219_513_scope.py --retire-proxy --apply

Exit codes: ``0`` success (including a dry run), ``1`` the rule was not found
or the write failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

#: The catalog row this patch targets. `reference` is the stable identity;
#: the primary key is whatever the import happened to allocate.
REFERENCE = "NZS-4219-5.13"

#: Stamped into parameters so a reviewer can tell a patched row from an
#: imported one, and revert it deterministically.
PATCHER = "patch_nzs4219_513_scope/1"

#: Nominal bore at or above which the clause is taken to apply, standing in
#: for the mass threshold. Inclusive: `{"min": 50.0}` admits NB50 itself,
#: which is the smallest size the clause is understood to reach.
PROXY_DIAMETER_MIN_MM = 50.0

#: The clause's own threshold, carried through unchanged.
MASS_MIN_KG = 10.0

NEW_TARGET = "IfcPipeSegment"
OLD_TARGET = "IfcDistributionElement"

NEW_DESCRIPTION = (
    "Seismic clearance for independently supported pipework in ceiling "
    f"voids, nominal bore {PROXY_DIAMETER_MIN_MM:.0f} mm and above."
)
OLD_DESCRIPTION = (
    "Seismic clearance for independently supported equipment in ceiling voids."
)

#: Why the diameter band is here at all, kept inside the predicate so it
#: travels with the rule. `note` is an annotation key: neutral at evaluation,
#: never reported as an unsupported predicate.
SCOPE_NOTE = (
    f"mass_kg >= {MASS_MIN_KG:.0f} is the clause's own threshold and is not "
    "resolvable by the extractor today; nominal bore "
    f"{PROXY_DIAMETER_MIN_MM:.0f} mm and above is the enforceable proxy. "
    "Drop nominal_diameter_mm once mass_kg is extractable -- the keys are "
    "ANDed, so keeping both would then exclude heavy small-bore runs."
)

#: The patched scope. Key order is presentational only; `_evaluate_predicate`
#: short-circuits on the first NO_MATCH whatever the order.
NEW_APPLIES_WHEN = {
    "target_ifc_class": NEW_TARGET,
    "nominal_diameter_mm": {"min": PROXY_DIAMETER_MIN_MM},
    "location": "ceiling_void",
    "mass_kg": {"min": MASS_MIN_KG},
    "note": SCOPE_NOTE,
}

#: The scope as imported, for --revert.
OLD_APPLIES_WHEN = {
    "target_ifc_class": OLD_TARGET,
    "location": "ceiling_void",
    "mass_kg": {"min": MASS_MIN_KG},
}

#: Stamped by --retire-proxy, so a row that has had the stand-in removed is
#: distinguishable from one that never carried it.
RETIRE_PATCHER = "patch_nzs4219_513_scope/2"

RETIRED_DESCRIPTION = (
    "Seismic clearance for independently supported pipework in ceiling voids."
)

#: What the clause actually says, now that the extractor can evaluate it.
#: `mass_kg` does the narrowing on its own; `location` is still unrecognised by
#: the comparator and still rides along as UNDETERMINED, which keeps an element
#: in scope rather than dropping it -- the safe direction, and the reason it is
#: kept rather than deleted.
#:
#: `nominal_diameter_mm` is deliberately absent. See the module docstring: with
#: mass extractable the two keys AND together, and the band would drop a heavy
#: small-bore run out of scope entirely.
RETIRED_APPLIES_WHEN = {
    "target_ifc_class": NEW_TARGET,
    "location": "ceiling_void",
    "mass_kg": {"min": MASS_MIN_KG},
}

#: Provenance for the retirement. `previous_applies_when` points at the v1
#: patched scope rather than the imported one, so the row's history reads
#: import -> narrow -> retire in order.
RETIRE_PATCH_PARAM = {
    "patcher": RETIRE_PATCHER,
    "supersedes": PATCHER,
    "removed_key": "nominal_diameter_mm",
    "removed_min_mm": PROXY_DIAMETER_MIN_MM,
    "reason": (
        "mass_kg is resolvable by ifc_reader.ifc_seismic and mapped in "
        "comparator._SCOPE_NUMERIC_PROPERTIES, which is the condition "
        "scope_patch.retire_proxy_when named. Keeping the band would AND with "
        "the mass gate and drop a heavy small-bore run out of scope."
    ),
    "target_ifc_class_retained": NEW_TARGET,
    "previous_applies_when": NEW_APPLIES_WHEN,
}

#: Provenance merged into the row's `parameters` blob.
SCOPE_PATCH_PARAM = {
    "patcher": PATCHER,
    "narrowed_target_from": OLD_TARGET,
    "narrowed_target_to": NEW_TARGET,
    "proxy_key": "nominal_diameter_mm",
    "proxy_min_mm": PROXY_DIAMETER_MIN_MM,
    "proxy_for": "mass_kg",
    "proxy_for_min": MASS_MIN_KG,
    "proxy_is_not_clause_text": True,
    "previous_applies_when": OLD_APPLIES_WHEN,
    "retire_proxy_when": (
        "mass_kg is added to comparator._SCOPE_NUMERIC_PROPERTIES"
    ),
}


def _decode(blob, default):
    """Decode a JSON column, falling back when it is absent or malformed."""
    if isinstance(blob, (dict, list)):
        return blob
    try:
        value = json.loads(blob or "null")
    except (json.JSONDecodeError, TypeError):
        return default
    return value if isinstance(value, type(default)) else default


def _sql_literal(text: str) -> str:
    """Quote a value as a Postgres string literal."""
    return "'" + str(text).replace("'", "''") + "'"


#: The three states this row can be written to. A boolean `revert` flag
#: expressed only two, and retiring the proxy is neither of them: it keeps the
#: v1 target narrowing and drops only the stand-in key.
MODE_PATCH = "patch"
MODE_REVERT = "revert"
MODE_RETIRE = "retire"

#: mode -> (applies_when, target_ifc_class, description, scope_patch value).
#: A None provenance means "delete the key", which is what revert wants: the
#: row should end up as the importer produced it, unstamped.
_PLANS: dict[str, tuple[dict, str, str, dict | None]] = {
    MODE_PATCH: (NEW_APPLIES_WHEN, NEW_TARGET, NEW_DESCRIPTION, SCOPE_PATCH_PARAM),
    MODE_REVERT: (OLD_APPLIES_WHEN, OLD_TARGET, OLD_DESCRIPTION, None),
    MODE_RETIRE: (
        RETIRED_APPLIES_WHEN,
        NEW_TARGET,
        RETIRED_DESCRIPTION,
        RETIRE_PATCH_PARAM,
    ),
}

_HEADLINES = {
    MODE_PATCH: (
        "Narrows IfcDistributionElement -> IfcPipeSegment and adds the\n"
        "-- enforceable nominal-bore band that proxies for mass_kg."
    ),
    MODE_REVERT: "Restores the scope as imported from NotebookLM.",
    MODE_RETIRE: (
        "Drops the nominal_diameter_mm proxy now that mass_kg is extractable.\n"
        "-- The keys are ANDed, so leaving the band in place would drop a heavy\n"
        "-- small-bore run out of scope -- a false negative the clause does not\n"
        "-- intend. The IfcPipeSegment narrowing from the v1 patch is kept."
    ),
}

_VERBS = {MODE_PATCH: "Patch", MODE_REVERT: "Revert", MODE_RETIRE: "Retire proxy in"}


def build_sql(mode: str = MODE_PATCH) -> str:
    """Return the equivalent SQL patch, for running via the Supabase editor.

    Written against `reference` rather than the primary key so it is portable
    across environments, and idempotent: re-running matches the same row and
    rewrites it to the same values.
    """
    applies_when, target, description, provenance = _PLANS[mode]
    # With no provenance the key is removed rather than rewritten, so the row
    # is left as the importer produced it.
    parameters_expr = (
        "(coalesce(nullif(parameters, ''), '{}')::jsonb - 'scope_patch')::text"
        if provenance is None
        else (
            "(coalesce(nullif(parameters, ''), '{}')::jsonb || "
            f"jsonb_build_object('scope_patch', {_sql_literal(json.dumps(provenance))}::jsonb))::text"
        )
    )
    return f"""-- {_VERBS[mode]} {REFERENCE} scope.
-- {_HEADLINES[mode]}
-- `applies_when` and `parameters` are text columns holding JSON (see
-- supabase/migrations/20260721135500_init_core_public_tables.sql), hence the
-- ::jsonb round trip on the merge.
update public.rules
   set target_ifc_class = {_sql_literal(target)},
       description      = {_sql_literal(description)},
       applies_when     = {_sql_literal(json.dumps(applies_when))},
       parameters       = {parameters_expr},
       updated_at       = to_char(now() at time zone 'utc',
                                  'YYYY-MM-DD"T"HH24:MI:SS+00:00')
 where reference = {_sql_literal(REFERENCE)};
"""


_TITLES = {
    MODE_PATCH: "scope narrowing",
    MODE_REVERT: "revert",
    MODE_RETIRE: "retire nominal_diameter_mm proxy",
}


def summarise(rows: list[dict], mode: str) -> None:
    """Print the before/after for every matching row."""
    applies_when, target, description, _ = _PLANS[mode]

    print()
    print("=" * 78)
    print(f"{REFERENCE} — {_TITLES[mode]}")
    print("=" * 78)

    for row in rows:
        current_scope = _decode(row.get("applies_when"), {})
        print(f"\n  rule id {row.get('id')}   ruleset {row.get('ruleset_id') or '—'}")
        print(f"    target      : {row.get('target_ifc_class')}  ->  {target}")
        print(f"    description : {row.get('description')}")
        print(f"                  ->  {description}")
        print(f"    applies_when: {json.dumps(current_scope)}")
        print(f"                  ->  {json.dumps(applies_when)}")

    if mode == MODE_PATCH:
        print("\n  evaluation, per comparator._evaluate_predicate (AND):")
        print(f"    NominalDiameter <  {PROXY_DIAMETER_MIN_MM:.0f} mm"
              "  -> NO_MATCH   -> NOT_APPLICABLE, element dropped from the rule")
        print(f"    NominalDiameter >= {PROXY_DIAMETER_MIN_MM:.0f} mm"
              "  -> UNDETERMINED (mass_kg, location unresolved) -> stays in scope,"
              "\n                              reported under undetermined_predicates")
        print("    NominalDiameter absent      -> UNDETERMINED -> stays in scope")
    elif mode == MODE_RETIRE:
        print("\n  evaluation, per comparator._evaluate_predicate (AND):")
        print(f"    MassKg <  {MASS_MIN_KG:.0f} kg"
              "  -> NO_MATCH   -> NOT_APPLICABLE, element dropped from the rule")
        print(f"    MassKg >= {MASS_MIN_KG:.0f} kg"
              "  -> UNDETERMINED (location unresolved) -> stays in scope")
        print("    MassKg absent  -> UNDETERMINED -> stays in scope, gap reported")
        print("\n  what this fixes: a run under NB50 carrying more than "
              f"{MASS_MIN_KG:.0f} kg was\n  dropped from the rule by the diameter "
              "band. It is now governed.")


def main() -> int:
    """Apply, revert, or preview the scope patch."""
    parser = argparse.ArgumentParser(
        description=f"Narrow the {REFERENCE} applies_when predicate."
    )
    parser.add_argument(
        "--apply", action="store_true", help="write to the database (default: dry run)"
    )
    parser.add_argument(
        "--revert", action="store_true", help="restore the scope as imported"
    )
    parser.add_argument(
        "--retire-proxy",
        action="store_true",
        help="drop nominal_diameter_mm now that mass_kg is extractable",
    )
    parser.add_argument(
        "--print-sql", action="store_true", help="print the equivalent SQL and exit"
    )
    args = parser.parse_args()

    if args.revert and args.retire_proxy:
        parser.error(
            "--revert and --retire-proxy write different scopes; pick one. "
            "Revert restores the imported scope; retire keeps the "
            "IfcPipeSegment narrowing and drops only the proxy key."
        )

    mode = (
        MODE_REVERT if args.revert else MODE_RETIRE if args.retire_proxy else MODE_PATCH
    )

    if args.print_sql:
        print(build_sql(mode))
        return 0

    from app.environment import load_env_file

    load_env_file()
    from app.services.rules_service import RuleService

    service = RuleService()
    rows = [
        row
        for row in service.fetch_rules_by_ref(REFERENCE)
        if str(row.get("reference") or "").strip() == REFERENCE
    ]
    if not rows:
        print(f"error: no rule with reference {REFERENCE!r} in the catalog", file=sys.stderr)
        return 1

    summarise(rows, mode)

    if not args.apply:
        print("\n  dry run: nothing written. Re-run with --apply.")
        return 0

    applies_when, target, description, provenance = _PLANS[mode]

    for row in rows:
        rule_id = row["id"]
        try:
            service.set_rule_scope(
                rule_id,
                applies_when=applies_when,
                target_ifc_class=target,
                description=description,
            )
            if provenance is None:
                service.remove_rule_parameter(rule_id, "scope_patch")
            else:
                service.set_rule_parameter(rule_id, "scope_patch", provenance)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            print(f"error writing rule {rule_id}: {exc}", file=sys.stderr)
            return 1

    print(f"\n  wrote {len(rows)} rule(s).")
    print(
        "  Rerun the analysis to pick it up: rule rows are read fresh per run,\n"
        "  but any cached analysis result for a project still holds the old scope."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
