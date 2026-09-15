"""Export rules to AEC3PO/ELI/ODRL RDF format for regulatory provenance."""

from __future__ import annotations

import json
from typing import Any

from rdflib import BNode, Graph, Literal
from rdflib.namespace import RDF
from rdflib.term import Identifier

from app.modules.ifc_reader.bot_graph import BIMGUARD
from app.modules.ifc_reader.ontology_namespaces import AEC3PO, ELI, ODRL

# Each RASE component becomes its own typed AEC3PO sub-statement, linked from
# the CheckStatement via the ontology's own object property (see
# https://github.com/Accord-Project/aec3po/blob/main/src/rase_statement.ttl).
_RASE_COMPONENTS = (
    ("rase_requirement", AEC3PO.requires, AEC3PO.RequirementStatement, "requirement"),
    ("rase_applicability", AEC3PO.appliesTo, AEC3PO.ApplicationStatement, "applicability"),
    ("rase_selection", AEC3PO.selects, AEC3PO.SelectionStatement, "selection"),
    ("rase_exception", AEC3PO["except"], AEC3PO.ExceptionStatement, "exception"),
)


def export_aec3po(rules: list[dict[str, Any]]) -> Graph:
    """Compile rules with RASE metadata into an AEC3PO RDF graph.

    Follows the real AEC3PO vocabulary (namespace https://w3id.org/lbd/aec3po/):
    a rule becomes an aec3po:CheckStatement (statement.ttl), and each RASE
    component becomes its own typed sub-statement -- RequirementStatement/
    ApplicationStatement/SelectionStatement/ExceptionStatement -- linked via
    the ontology's own requires/appliesTo/selects/except properties
    (rase_statement.ttl), with content attached via
    aec3po:DocumentSubdivision_asLiteral, the ontology's generic text/value
    property for any DocumentSubdivision (aliased "text" in JSON-LD/YAML-LD;
    document.ttl).
    """
    graph = Graph()
    graph.bind("aec3po", AEC3PO)
    graph.bind("eli", ELI)
    graph.bind("odrl", ODRL)
    graph.bind("bimguard", BIMGUARD)

    document = BIMGUARD["document/regulatory_act"]
    graph.add((document, RDF.type, AEC3PO.Document))
    graph.add((document, RDF.type, ELI.LegalResource))

    for rule in rules:
        rule_id = str(rule.get("rule_id") or "rule")
        statement = BIMGUARD[f"statement/{rule_id}"]

        graph.add((statement, RDF.type, AEC3PO.CheckStatement))
        graph.add((document, AEC3PO.hasSubdivision, statement))

        for field, link_predicate, node_type, slug in _RASE_COMPONENTS:
            _add_rase_component(
                graph, statement, link_predicate, node_type, BIMGUARD[f"statement/{rule_id}/{slug}"], rule.get(field)
            )

        duty = BNode()
        graph.add((statement, ODRL.hasPolicy, duty))
        graph.add((duty, RDF.type, ODRL.Duty))
        graph.add((duty, ODRL.target, BIMGUARD[f"shape/{rule_id}"]))

    return graph


def _add_rase_component(
    graph: Graph, statement: Identifier, link_predicate: Identifier, node_type: Identifier, node: Identifier, value: Any
) -> None:
    """Attach one RASE component (requirement/applicability/selection/exception).

    `value` is either the requirement's plain text or one of BIM-Guard's
    applies_when/selection/exception dicts -- dicts are serialized as JSON
    text, since DocumentSubdivision_asLiteral's range is `rdfs:Literal` of
    "xsd:string, rdf:HTMLLiteral, xsd:base64Binary, or any other relevant
    datatype" and BIM-Guard's scope predicates have no AEC3PO-native
    structured representation (yet).
    """
    if not value:
        return
    text = value if isinstance(value, str) else json.dumps(value)
    graph.add((statement, link_predicate, node))
    graph.add((node, RDF.type, node_type))
    graph.add((node, AEC3PO.DocumentSubdivision_asLiteral, Literal(text)))
