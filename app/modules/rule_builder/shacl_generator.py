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
#: `app.modules.comparator._SCOPE_LIST_FIELDS`) mapped onto the SPARQL pattern
#: that binds the property value to `?v`.
_SCOPE_SPARQL_PATTERNS = {
    "material_any_of": "?this bimguard:materials ?v .",
    "element_type_any_of": "?this a ?type_iri .\n                            BIND(REPLACE(STR(?type_iri), \"^.*#\", \"\") AS ?v)",
    "storey_any_of": "?storey bot:containsElement|bot:hasElement ?this .\n                            ?storey rdfs:label ?v .",
    "space_any_of": "?space bot:containsElement|bot:hasElement|bot:hasSpace|bot:adjacentElement ?this .\n                            ?space rdfs:label ?v .",
}

#: Operators that require a SHACL-SPARQL constraint rather than a Core constraint.
_OPERATOR_TO_SPARQL = {
    "field_consistency": True,
    "unique_within_scope": True,
    "exists": True,
    "not_exists": True,
}

def rule_is_shacl_eligible(rule: dict[str, Any]) -> bool:
    """Return True when a rule's requirement can be expressed as a SHACL shape."""
    if not rule.get("target_ifc_class") or not rule.get("property_name"):
        return False
    operator = str(rule.get("operator") or "")
    if operator == "between":
        return rule.get("value_min") is not None or rule.get("value_max") is not None
    return operator in _OPERATOR_TO_SHACL or operator in _OPERATOR_TO_SPARQL


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

    message = str(rule.get("description") or f"{rule_id} violated").strip()
    severity = SH.Violation if str(rule.get("severity") or "mandatory") == "mandatory" else SH.Warning

    operator = str(rule.get("operator") or "")
    unit = rule.get("unit")
    datatype = XSD.string if unit == "" and operator == "matches" else XSD.decimal

    if operator in _OPERATOR_TO_SPARQL:
        sparql_constraint = BNode()
        shapes.add((node_shape, SH.sparql, sparql_constraint))
        shapes.add((sparql_constraint, RDF.type, SH.SPARQLConstraint))
        shapes.add((sparql_constraint, SH.message, Literal(message)))
        shapes.add((sparql_constraint, SH.severity, severity))
        shapes.add((sparql_constraint, BIMGUARD.ruleId, Literal(rule_id)))
        
        # Build prefix declarations
        prefixes = BNode()
        shapes.add((sparql_constraint, SH.prefixes, prefixes))
        
        bimguard_prefix = BNode()
        shapes.add((prefixes, SH.declare, bimguard_prefix))
        shapes.add((bimguard_prefix, SH.prefix, Literal("bimguard")))
        shapes.add((bimguard_prefix, SH.namespace, Literal(str(BIMGUARD), datatype=XSD.anyURI)))
        
        bot_prefix = BNode()
        shapes.add((prefixes, SH.declare, bot_prefix))
        shapes.add((bot_prefix, SH.prefix, Literal("bot")))
        shapes.add((bot_prefix, SH.namespace, Literal("https://w3id.org/bot#", datatype=XSD.anyURI)))

        rdfs_prefix = BNode()
        shapes.add((prefixes, SH.declare, rdfs_prefix))
        shapes.add((rdfs_prefix, SH.prefix, Literal("rdfs")))
        shapes.add((rdfs_prefix, SH.namespace, Literal("http://www.w3.org/2000/01/rdf-schema#", datatype=XSD.anyURI)))

        property_local = str(property_path)[len(str(BIMGUARD)) :]
        
        if operator == "exists":
            query = f"""
            SELECT $this ?value
            WHERE {{
                FILTER NOT EXISTS {{ $this bimguard:{property_local} ?v }}
            }}
            """
        elif operator == "not_exists":
            query = f"""
            SELECT $this ?value
            WHERE {{
                $this bimguard:{property_local} ?value .
            }}
            """
        elif operator == "unique_within_scope":
            query = f"""
            SELECT $this ?value
            WHERE {{
                $this bimguard:{property_local} ?value .
                ?other bimguard:{property_local} ?value .
                FILTER($this != ?other)
            }}
            """
        elif operator == "field_consistency":
            query = f"""
            SELECT $this ?value
            WHERE {{
                $this bimguard:{property_local} ?value .
                ?other bimguard:{property_local} ?other_val .
                FILTER($this != ?other && ?value != ?other_val)
            }}
            """
        else:
            query = "SELECT $this WHERE { FILTER (1=0) }"

        # If there are exceptions, append them to the SPARQL WHERE clause to waive
        exception_filters = _build_exception_filters(rule.get("exceptions"))
        if exception_filters:
            query = query.replace("WHERE {", f"WHERE {{\n{exception_filters}\n")

        shapes.add((sparql_constraint, SH.select, Literal(query)))
        
        return

    prop_shape = BNode()
    shapes.add((node_shape, SH.property, prop_shape))
    shapes.add((prop_shape, SH.path, property_path))
    shapes.add((prop_shape, SH.message, Literal(message)))
    shapes.add((prop_shape, SH.severity, severity))
    shapes.add((prop_shape, BIMGUARD.ruleId, Literal(rule_id)))

    if operator == "between":
        if rule.get("value_min") is not None:
            shapes.add((prop_shape, SH.minInclusive, Literal(float(rule["value_min"]), datatype=XSD.decimal)))
        if rule.get("value_max") is not None:
            shapes.add((prop_shape, SH.maxInclusive, Literal(float(rule["value_max"]), datatype=XSD.decimal)))
    else:
        constraint_predicate = _OPERATOR_TO_SHACL[operator]
        check_value = rule.get("check_value")
        if constraint_predicate == SH.pattern:
            shapes.add((prop_shape, constraint_predicate, Literal(str(check_value))))
        else:
            shapes.add((prop_shape, constraint_predicate, Literal(float(check_value), datatype=datatype)))

    # If this is a property shape and we have exceptions, we need to add a sh:sparql 
    # exclusion directly onto the property shape, or change the target to exclude exceptions.
    # However, standard SHACL properties apply to ALL targeted nodes. To exclude via exceptions, 
    # we can modify the node shape's target if it's a SPARQL target, OR we can add an exclusion to 
    # the target.
    _apply_exceptions_to_target(shapes, node_shape, target_class, rule.get("exceptions"))


def _build_exception_filters(exceptions: dict | None) -> str:
    if not exceptions:
        return ""
    
    filters = []
    for key, values in exceptions.items():
        pattern = _SCOPE_SPARQL_PATTERNS.get(key)
        if pattern is None or not values:
            continue
        values_list = ", ".join(f'"{v}"' for v in values)
        filters.append(f"""
            FILTER NOT EXISTS {{
                {pattern}
                FILTER (?v IN ({values_list}))
            }}
        """)
    return "\n".join(filters)


def _apply_exceptions_to_target(shapes: Graph, node_shape: Any, target_class: Any, exceptions: dict | None) -> None:
    if not exceptions:
        return
    
    # We must convert the target to a SPARQLTarget if it isn't one already,
    # or if it is, we need to inject the exceptions filter.
    # For simplicity, if a targetClass exists, we'll remove it and replace it with a SPARQLTarget.
    existing_targets = list(shapes.objects(node_shape, SH.targetClass))
    if existing_targets:
        shapes.remove((node_shape, SH.targetClass, target_class))
        
        sparql_target = BNode()
        shapes.add((node_shape, SH.target, sparql_target))
        shapes.add((sparql_target, RDF.type, SH.SPARQLTarget))
        
        exception_filters = _build_exception_filters(exceptions)
        
        shapes.add(
            (
                sparql_target,
                SH.select,
                Literal(
                    f"""
                    PREFIX bimguard: <{BIMGUARD}>
                    PREFIX bot: <https://w3id.org/bot#>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    SELECT ?this
                    WHERE {{
                        ?this a <{target_class}> .
                        {exception_filters}
                    }}
                    """
                ),
            )
        )
    else:
        # It's already a SPARQL target (due to applies_when). We must modify the existing query.
        sparql_target = next(shapes.objects(node_shape, SH.target), None)
        if sparql_target:
            query = str(next(shapes.objects(sparql_target, SH.select)))
            exception_filters = _build_exception_filters(exceptions)
            # Inject exception_filters before the last closing brace
            query = query.rsplit("}", 1)[0] + exception_filters + "\n}"
            shapes.set((sparql_target, SH.select, Literal(query)))


def _apply_scope_target(shapes: Graph, node_shape: Any, target_class: Any, applies_when: dict | None) -> bool:
    """Narrow a shape's targets using `applies_when`, when it maps to a known graph predicate.

    Returns True when a SPARQL-based target was emitted (the caller must then
    skip the plain `sh:targetClass`, since pyshacl unions every target
    mechanism on a shape rather than intersecting them -- emitting both would
    select the class's full membership regardless of scope). Returns False
    when no `applies_when` key resolves to a graph predicate (see
    `_SCOPE_SPARQL_PATTERNS`); the caller then falls back to a plain
    `sh:targetClass` covering every element of the class, which is the
    correct MATCH/UNDETERMINED behaviour -- an unresolvable scope predicate
    must never silently narrow.

    Only the first resolvable `applies_when` key is compiled; a rule with
    more than one resolvable key is rare today and combining several as a
    single SPARQL query is left for when that need is concrete.
    """
    for key, values in (applies_when or {}).items():
        pattern = _SCOPE_SPARQL_PATTERNS.get(key)
        if pattern is None or not values:
            continue
        # Keep every element the class selects PLUS require it (only when
        # the predicate is present at all) to match one of the listed
        # values -- an element with no triple for `predicate` stays in scope
        # (UNDETERMINED), matching `app.modules.comparator`'s semantics for
        # this predicate family.
        values_list = ", ".join(f'"{v}"' for v in values)
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
                    PREFIX bot: <https://w3id.org/bot#>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    SELECT ?this
                    WHERE {{
                        ?this a <{target_class}> .
                        FILTER NOT EXISTS {{
                            {pattern}
                            FILTER (?v NOT IN ({values_list}))
                        }}
                    }}
                    """
                ),
            )
        )
        return True

    return False
