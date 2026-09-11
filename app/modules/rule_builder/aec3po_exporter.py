"""Export rules to AEC3PO/ELI/ODRL RDF format for regulatory provenance."""

from __future__ import annotations

import json
from typing import Any

from rdflib import BNode, Graph, Literal
from rdflib.namespace import RDF

from app.modules.ifc_reader.bot_graph import BIMGUARD
from app.modules.ifc_reader.ontology_namespaces import AEC3PO, ELI, ODRL


def export_aec3po(rules: list[dict[str, Any]]) -> Graph:
    """Compile rules with RASE metadata into an AEC3PO RDF graph."""
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
        
        graph.add((statement, RDF.type, AEC3PO.Statement))
        graph.add((document, AEC3PO.hasPart, statement))

        requirement = rule.get("rase_requirement")
        if requirement:
            graph.add((statement, AEC3PO.hasRequirement, Literal(requirement)))

        applicability = rule.get("rase_applicability")
        if applicability:
            graph.add((statement, AEC3PO.hasApplicability, Literal(json.dumps(applicability))))

        selection = rule.get("rase_selection")
        if selection:
            graph.add((statement, AEC3PO.hasSelection, Literal(json.dumps(selection))))

        exception = rule.get("rase_exception")
        if exception:
            graph.add((statement, AEC3PO.hasException, Literal(json.dumps(exception))))

        duty = BNode()
        graph.add((statement, ODRL.hasPolicy, duty))
        graph.add((duty, RDF.type, ODRL.Duty))
        graph.add((duty, ODRL.target, BIMGUARD[f"shape/{rule_id}"]))

    return graph
