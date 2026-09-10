"""Compile DB-stored compliance rules into W3C SHACL shapes.

Mirrors `ids_exporter.py`'s role -- both read `RuleCreateRequest`-shaped rows
(typically via `RuleService.list_by_ruleset()`) and translate them into a
declarative, standards-based validation artifact. Where `ids_exporter.py`
emits buildingSMART IDS XML for authoring-tool round-tripping, this module
emits SHACL shapes for `app.engines.bimguard_shacl_engine` to run with
pyshacl against a BOT graph (`app.modules.ifc_reader.bot_graph`).

Per this repo's "Zero Hardcoded Logic" rule, shapes are compiled from `rules`
rows at run time -- there is no static .ttl shape file checked in.

Scope of this first pass: `applies_when` (Applicability/Selection) is
compiled into scope-narrowing SPARQL-based targets, preserving the
MATCH/NO_MATCH/UNDETERMINED semantics `app.modules.comparator` already uses
(an element the graph says nothing about stays in scope). `exceptions`
(waivers) are NOT yet compiled here -- they still only apply along the
existing dict-based comparator path. Extending pyshacl-based validation to
also honour `exceptions` is a follow-up once there is a concrete need to
waive a SHACL-flagged violation.
"""

from __future__ import annotations

from typing import Any

from rdflib import BNode, Graph, Literal
from rdflib.namespace import RDF, SH, XSD

from app.modules.ifc_reader.bot_graph import BIMGUARD

#: `RuleCreateRequest.operator` -> SHACL constraint predicate for a single
#: bound. Only operators expressible as a per-element property constraint
#: are handled here; anything else (e.g. `unique_within_scope`,
#: `field_consistency`) stays on the existing dict-based comparator path.
_OPERATOR_TO_SHACL = {
    ">=": SH.minInclusive,
    "<=": SH.maxInclusive,
    ">": SH.minExclusive,
    "<": SH.maxExclusive,
    "==": SH.hasValue,
    "matches": SH.pattern,
}

#: `applies_when`/`exceptions` list-predicate keys (from
#: `app.modules.comparator._SCOPE_LIST_FIELDS`) mapped onto the BOT-graph
#: literal predicate a value would be enriched under, when one exists yet.
#: A key with no entry here is skipped during compilation (documented as
#: UNDETERMINED, matching the comparator's own behaviour for untestable keys).
_SCOPE_LIST_PREDICATE = {
    "material_any_of": BIMGUARD.materials,
}

#: Rules this engine can compile without pyshacl's SPARQL-target advanced
#: feature -- everything else (a rule carrying `applies_when` keys we can
#: resolve to a graph predicate) needs `advanced=True` at validation time.
def rule_is_shacl_eligible(rule: dict[str, Any]) -> bool:
    """Return True when a rule's requirement can be expressed as a SHACL shape."""
    if not rule.get("target_ifc_class") or not rule.get("property_name"):
        return False
    operator = str(rule.get("operator") or "")
    if operator == "between":
        return rule.get("value_min") is not None or rule.get("value_max") is not None
    return operator in _OPERATOR_TO_SHACL


def compile_shapes(rules: list[dict[str, Any]]) -> Graph:
    """Compile a list of `RuleCreateRequest`-shaped rule dicts into a SHACL shapes graph."""
    shapes = Graph()
    shapes.bind("sh", SH)
    shapes.bind("bimguard", BIMGUARD)

    for rule in rules:
        if rule_is_shacl_eligible(rule):
            _add_shape(shapes, rule)

    return shapes


def _add_shape(shapes: Graph, rule: dict[str, Any]) -> None:
    rule_id = str(rule.get("rule_id") or "rule")
    node_shape = BIMGUARD[f"shape/{rule_id}"]
    target_class = BIMGUARD[str(rule["target_ifc_class"])]
    property_path = BIMGUARD[str(rule["property_name"])]

    shapes.add((node_shape, RDF.type, SH.NodeShape))
    if not _apply_scope_target(shapes, node_shape, target_class, rule.get("applies_when")):
        shapes.add((node_shape, SH.targetClass, target_class))

    prop_shape = BNode()
    shapes.add((node_shape, SH.property, prop_shape))
    shapes.add((prop_shape, SH.path, property_path))

    message = str(rule.get("description") or f"{rule_id} violated").strip()
    severity = SH.Violation if str(rule.get("severity") or "mandatory") == "mandatory" else SH.Warning
    shapes.add((prop_shape, SH.message, Literal(message)))
    shapes.add((prop_shape, SH.severity, severity))
    # pyshacl's validation report copies sh:sourceShape as a *property* shape
    # (this blank node), not the enclosing sh:NodeShape -- so the rule id is
    # stamped directly on it, rather than relied upon via a node-shape URI
    # that never appears in the report. issue_adapter.lift_shacl_report()
    # reads this back to attribute a violation to its rule.
    shapes.add((prop_shape, BIMGUARD.ruleId, Literal(rule_id)))

    operator = str(rule.get("operator") or "")
    unit = rule.get("unit")
    datatype = XSD.string if unit == "" and operator == "matches" else XSD.decimal

    if operator == "between":
        if rule.get("value_min") is not None:
            shapes.add((prop_shape, SH.minInclusive, Literal(float(rule["value_min"]), datatype=XSD.decimal)))
        if rule.get("value_max") is not None:
            shapes.add((prop_shape, SH.maxInclusive, Literal(float(rule["value_max"]), datatype=XSD.decimal)))
        return

    constraint_predicate = _OPERATOR_TO_SHACL[operator]
    check_value = rule.get("check_value")
    if constraint_predicate == SH.pattern:
        shapes.add((prop_shape, constraint_predicate, Literal(str(check_value))))
    else:
        shapes.add((prop_shape, constraint_predicate, Literal(float(check_value), datatype=datatype)))


def _apply_scope_target(shapes: Graph, node_shape: Any, target_class: Any, applies_when: dict | None) -> bool:
    """Narrow a shape's targets using `applies_when`, when it maps to a known graph predicate.

    Returns True when a SPARQL-based target was emitted (the caller must then
    skip the plain `sh:targetClass`, since pyshacl unions every target
    mechanism on a shape rather than intersecting them -- emitting both would
    select the class's full membership regardless of scope). Returns False
    when no `applies_when` key resolves to a graph predicate (see
    `_SCOPE_LIST_PREDICATE`); the caller then falls back to a plain
    `sh:targetClass` covering every element of the class, which is the
    correct MATCH/UNDETERMINED behaviour -- an unresolvable scope predicate
    must never silently narrow.

    Only the first resolvable `applies_when` key is compiled; a rule with
    more than one resolvable key is rare today and combining several as a
    single SPARQL query is left for when that need is concrete.
    """
    for key, values in (applies_when or {}).items():
        predicate = _SCOPE_LIST_PREDICATE.get(key)
        if predicate is None or not values:
            continue
        # Keep every element the class selects PLUS require it (only when
        # the predicate is present at all) to match one of the listed
        # values -- an element with no triple for `predicate` stays in scope
        # (UNDETERMINED), matching `app.modules.comparator`'s semantics for
        # this predicate family.
        values_list = ", ".join(f'"{v}"' for v in values)
        predicate_local = str(predicate)[len(str(BIMGUARD)) :]
        sparql_target = BNode()
        shapes.add((node_shape, SH.target, sparql_target))
        shapes.add((sparql_target, RDF.type, SH.SPARQLTarget))
        shapes.add(
            (
                sparql_target,
                SH.select,
                Literal(
                    f"""
                    PREFIX bimguard: <{BIMGUARD}>
                    SELECT ?this
                    WHERE {{
                        ?this a <{target_class}> .
                        FILTER NOT EXISTS {{
                            ?this bimguard:{predicate_local} ?v .
                            FILTER (?v NOT IN ({values_list}))
                        }}
                    }}
                    """
                ),
            )
        )
        return True

    return False
