"""Causal compliance decision lineage and W3C PROV-O audit graph infrastructure.

Inspired by Semantica's Context Graph and Decision Intelligence architecture,
this module projects compliance verification decisions, building code rule axioms,
and IFC product evaluations into GraphService (Neo4j).

Provides:
- `ingest_compliance_verdicts(...)`: Persists compliance verdicts and causal links.
- `trace_decision_causal_chain(...)`: Traverses upstream causal ancestry from an issue finding.
- `analyze_rule_impact(...)`: Identifies all model elements impacted by a given building code rule.
- `export_w3c_prov_rdf(...)`: Exports the decision graph as standardized W3C PROV-O Turtle RDF.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services.graph_database import GraphService

logger = logging.getLogger("bimguard.services.compliance_decision_graph")


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest_compliance_verdicts(
    graph_service: GraphService,
    project_id: str,
    issues: list[dict[str, Any]],
) -> dict[str, int]:
    """Persist compliance verification decisions and causal relationships into Neo4j.

    Creates:
    - `:ComplianceVerdict` nodes for each compliance check outcome.
    - `:Rule` nodes for each evaluated rule/standard clause.
    - `:Issue` nodes for tracked findings.
    - Directed edges:
      - `(ComplianceVerdict)-[:EVALUATED_ELEMENT]->(IfcProduct)`
      - `(ComplianceVerdict)-[:TRIGGERED_BY]->(Rule)`
      - `(ComplianceVerdict)-[:GENERATED_FINDING]->(Issue)`
    """
    if not graph_service or not graph_service.provider or not issues:
        return {"verdicts": 0, "rules": 0, "edges": 0}

    verdict_nodes: list[dict[str, Any]] = []
    rule_nodes: list[dict[str, Any]] = []
    issue_nodes: list[dict[str, Any]] = []
    seen_rules: set[str] = set()

    for iss in issues:
        issue_id = str(iss.get("id") or "")
        rule_id = str(iss.get("rule_id") or "UNSPECIFIED")
        element_id = str(iss.get("element_id") or "")
        if not issue_id:
            continue

        verdict_id = f"verdict_{issue_id}"
        citations = iss.get("citations") or []
        first_citation = citations[0] if citations and isinstance(citations[0], dict) else {}

        verdict_nodes.append(
            {
                "id": verdict_id,
                "verdict_id": verdict_id,
                "issue_id": issue_id,
                "project_id": str(project_id),
                "element_id": element_id,
                "rule_id": rule_id,
                "outcome": "FAIL",
                "risk_band": str(iss.get("band") or "medium"),
                "score": float(iss.get("score") or 0.0),
                "mechanism": str(iss.get("mechanism") or ""),
                "title": str(iss.get("title") or "")[:120],
                "description": str(iss.get("description") or "")[:300],
                "mitigation": str(iss.get("mitigation") or "")[:200],
                "timestamp": str(iss.get("created_at") or _now_iso_utc()),
            }
        )

        issue_nodes.append(
            {
                "id": issue_id,
                "issue_id": issue_id,
                "project_id": str(project_id),
                "title": str(iss.get("title") or "")[:120],
                "status": str(iss.get("status") or "open"),
            }
        )

        rule_key = f"{project_id}_{rule_id}"
        if rule_key not in seen_rules:
            seen_rules.add(rule_key)
            rule_nodes.append(
                {
                    "id": f"rule_{rule_id}",
                    "rule_id": rule_id,
                    "project_id": str(project_id),
                    "standard": str(first_citation.get("standard") or "BuildingCode"),
                    "clause": str(first_citation.get("clause") or ""),
                }
            )

    try:
        # Ingest nodes in batch
        graph_service.add_nodes_batch("ComplianceVerdict", verdict_nodes)
        if rule_nodes:
            graph_service.add_nodes_batch("Rule", rule_nodes)
        graph_service.add_nodes_batch("Issue", issue_nodes)

        # Link verdicts to rules, elements, and issues via Cypher
        link_query = """
        UNWIND $items AS item
        MATCH (v:ComplianceVerdict {id: item.verdict_id, project_id: $project_id})
        MATCH (r:Rule {id: item.rule_node_id, project_id: $project_id})
        MATCH (i:Issue {id: item.issue_id, project_id: $project_id})
        MERGE (v)-[:TRIGGERED_BY]->(r)
        MERGE (v)-[:GENERATED_FINDING]->(i)
        WITH v, item
        MATCH (e {guid: item.element_id, project_id: $project_id})
        MERGE (v)-[:EVALUATED_ELEMENT]->(e)
        """
        link_items = [
            {
                "verdict_id": f"verdict_{iss['id']}",
                "rule_node_id": f"rule_{iss.get('rule_id', 'UNSPECIFIED')}",
                "issue_id": str(iss["id"]),
                "element_id": str(iss.get("element_id") or ""),
            }
            for iss in issues
            if iss.get("id")
        ]
        graph_service.execute(link_query, {"project_id": str(project_id), "items": link_items})

        logger.info(
            "Ingested compliance decision lineage project_id=%s verdicts=%d rules=%d",
            project_id,
            len(verdict_nodes),
            len(rule_nodes),
        )
        return {
            "verdicts": len(verdict_nodes),
            "rules": len(rule_nodes),
            "edges": len(link_items) * 3,
        }
    except Exception as exc:
        logger.warning(
            "Failed to ingest compliance decision lineage for project %s: %s",
            project_id,
            exc,
        )
        return {"verdicts": 0, "rules": 0, "edges": 0}


def trace_decision_causal_chain(
    graph_service: GraphService,
    project_id: str,
    issue_id: str,
) -> dict[str, Any]:
    """Trace the complete causal lineage of a compliance finding from Neo4j.

    Returns the verdict, triggering rule, evaluated element, spatial context,
    graph nodes and edges for visualization, and an audit summary.
    """
    query = """
    MATCH (v:ComplianceVerdict {project_id: $project_id, issue_id: $issue_id})
    OPTIONAL MATCH (v)-[:TRIGGERED_BY]->(r:Rule)
    OPTIONAL MATCH (v)-[:EVALUATED_ELEMENT]->(e)
    OPTIONAL MATCH (e)<-[:CONTAINS*1..2]-(parent)
    RETURN v, r, e, collect(DISTINCT parent) AS parents
    LIMIT 1
    """
    try:
        results = graph_service.execute(query, {"project_id": str(project_id), "issue_id": str(issue_id)})
    except Exception as exc:
        logger.warning("Cypher causal trace failed for issue %s: %s", issue_id, exc)
        results = []

    if not results:
        # Fallback empty structure
        return {
            "project_id": int(project_id) if str(project_id).isdigit() else 0,
            "issue_id": issue_id,
            "verdict": {},
            "rule": {},
            "element": {},
            "lineage_nodes": [],
            "lineage_edges": [],
            "prov_summary": f"No persisted causal lineage found for issue {issue_id}.",
        }

    row = results[0]
    verdict = row.get("v") or {}
    rule = row.get("r") or {}
    element = row.get("e") or {}
    parents = row.get("parents") or []

    lineage_nodes: list[dict[str, Any]] = []
    lineage_edges: list[dict[str, Any]] = []

    # 1. Verdict node
    v_id = verdict.get("id") or f"verdict_{issue_id}"
    lineage_nodes.append(
        {
            "id": v_id,
            "label": f"Verdict: {verdict.get('outcome', 'FAIL')} ({verdict.get('risk_band', 'MEDIUM').upper()})",
            "node_type": "compliance_verdict",
            "properties": verdict,
        }
    )

    # 2. Rule node
    r_id = rule.get("id") or f"rule_{verdict.get('rule_id', 'UNSPECIFIED')}"
    lineage_nodes.append(
        {
            "id": r_id,
            "label": f"Standard: {rule.get('standard', 'Code')} §{rule.get('clause', '')}".strip(),
            "node_type": "rule_axiom",
            "properties": rule,
        }
    )
    lineage_edges.append(
        {
            "source": v_id,
            "target": r_id,
            "label": "TRIGGERED_BY",
        }
    )

    # 3. Element node
    e_guid = element.get("guid") or verdict.get("element_id") or "UNKNOWN_ELEMENT"
    e_label = element.get("name") or element.get("ifc_type") or e_guid
    lineage_nodes.append(
        {
            "id": e_guid,
            "label": f"{element.get('ifc_type', 'Element')}: {e_label}",
            "node_type": "ifc_element",
            "properties": element,
        }
    )
    lineage_edges.append(
        {
            "source": v_id,
            "target": e_guid,
            "label": "EVALUATED_ELEMENT",
        }
    )

    # 4. Spatial parents (Storey, Building)
    last_spatial = e_guid
    for p in parents:
        p_guid = p.get("guid") or p.get("id")
        if p_guid:
            lineage_nodes.append(
                {
                    "id": p_guid,
                    "label": f"{p.get('ifc_type', 'Spatial')}: {p.get('name', p_guid)}",
                    "node_type": "spatial_zone",
                    "properties": p,
                }
            )
            lineage_edges.append(
                {
                    "source": p_guid,
                    "target": last_spatial,
                    "label": "CONTAINS",
                }
            )
            last_spatial = p_guid

    parent_names = [p.get("name") for p in parents if p.get("name")]
    location_str = f" located in {', '.join(parent_names)}" if parent_names else ""
    std_str = f"{rule.get('standard', 'applicable building code')} §{rule.get('clause', '')}".strip()

    prov_summary = (
        f"Element {e_label} ({element.get('ifc_type', 'IfcProduct')}){location_str} "
        f"was evaluated by {verdict.get('mechanism', 'BIM-Guard')} against {std_str} "
        f"(Rule {verdict.get('rule_id')}). Check resulted in {verdict.get('outcome', 'FAIL')} "
        f"with risk score {verdict.get('score', 0.0):.2f} ({verdict.get('risk_band', 'medium')})."
    )

    return {
        "project_id": int(project_id) if str(project_id).isdigit() else 0,
        "issue_id": issue_id,
        "verdict": verdict,
        "rule": rule,
        "element": element,
        "lineage_nodes": lineage_nodes,
        "lineage_edges": lineage_edges,
        "prov_summary": prov_summary,
    }


def analyze_rule_impact(
    graph_service: GraphService,
    project_id: str,
    rule_id: str,
) -> dict[str, Any]:
    """Find all elements and verdicts influenced by a specific building code rule."""
    query = """
    MATCH (v:ComplianceVerdict {project_id: $project_id, rule_id: $rule_id})
    OPTIONAL MATCH (v)-[:EVALUATED_ELEMENT]->(e)
    RETURN v, e
    LIMIT 200
    """
    try:
        results = graph_service.execute(query, {"project_id": str(project_id), "rule_id": str(rule_id)})
    except Exception as exc:
        logger.warning("Rule impact analysis failed for rule %s: %s", rule_id, exc)
        results = []

    impacted: list[dict[str, Any]] = []
    for r in results:
        v = r.get("v") or {}
        e = r.get("e") or {}
        impacted.append(
            {
                "verdict_id": v.get("id"),
                "issue_id": v.get("issue_id"),
                "element_id": e.get("guid") or v.get("element_id"),
                "element_name": e.get("name"),
                "ifc_type": e.get("ifc_type"),
                "outcome": v.get("outcome", "FAIL"),
                "risk_band": v.get("risk_band", "medium"),
                "score": v.get("score", 0.0),
                "title": v.get("title", ""),
            }
        )

    unique_elements = {item["element_id"] for item in impacted if item.get("element_id")}

    return {
        "project_id": int(project_id) if str(project_id).isdigit() else 0,
        "rule_id": rule_id,
        "total_elements_evaluated": len(unique_elements),
        "total_findings": len(impacted),
        "impacted_elements": impacted,
    }


def export_w3c_prov_rdf(
    project_id: str,
    issues: list[dict[str, Any]],
) -> str:
    """Serialize compliance evaluation decision lineage to standardized W3C PROV-O Turtle RDF."""
    from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace

    PROV = Namespace("http://www.w3.org/ns/prov#")
    BIMGUARD = Namespace("https://bim-guard.xyz/prov/")

    g = Graph()
    g.bind("prov", PROV)
    g.bind("bimguard", BIMGUARD)

    # Activity: Audit Pipeline Execution
    activity_uri = BIMGUARD[f"activity/pipeline_run_{project_id}"]
    g.add((activity_uri, RDF.type, PROV.Activity))
    g.add((activity_uri, RDFS.label, Literal(f"Compliance Audit Pipeline Run {project_id}")))
    g.add((activity_uri, PROV.startedAtTime, Literal(_now_iso_utc(), datatype=XSD.dateTime)))

    # Agent: BIM-Guard Orchestrator
    agent_uri = BIMGUARD["agent/bim_guard_orchestrator"]
    g.add((agent_uri, RDF.type, PROV.Agent))
    g.add((agent_uri, RDF.type, PROV.SoftwareAgent))
    g.add((agent_uri, RDFS.label, Literal("BIM-Guard Automated Architectural Compliance Engine")))
    g.add((activity_uri, PROV.wasAssociatedWith, agent_uri))

    for iss in issues:
        issue_id = str(iss.get("id") or "")
        rule_id = str(iss.get("rule_id") or "UNSPECIFIED")
        element_id = str(iss.get("element_id") or "")
        if not issue_id:
            continue

        # Verdict Entity
        verdict_uri = BIMGUARD[f"verdict/{issue_id}"]
        g.add((verdict_uri, RDF.type, PROV.Entity))
        g.add((verdict_uri, RDFS.label, Literal(f"Compliance Verdict {issue_id}: FAIL ({iss.get('band', 'medium')})")))
        g.add((verdict_uri, PROV.wasGeneratedBy, activity_uri))

        # Rule Entity
        rule_uri = BIMGUARD[f"rule/{rule_id}"]
        g.add((rule_uri, RDF.type, PROV.Entity))
        g.add((rule_uri, RDFS.label, Literal(f"Rule {rule_id}")))
        g.add((activity_uri, PROV.used, rule_uri))
        g.add((verdict_uri, PROV.wasDerivedFrom, rule_uri))

        # Element Entity
        if element_id:
            elem_uri = BIMGUARD[f"element/{element_id}"]
            g.add((elem_uri, RDF.type, PROV.Entity))
            g.add((elem_uri, RDFS.label, Literal(f"IFC Product {element_id}")))
            g.add((activity_uri, PROV.used, elem_uri))
            g.add((verdict_uri, PROV.wasDerivedFrom, elem_uri))

    return g.serialize(format="turtle")
