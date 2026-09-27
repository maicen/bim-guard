"""Regulatory Knowledge Graph Service (GraphRAG for Building Standards).

Inspired by kg-lite-builder:
Builds, links, and traverses a connected regulatory knowledge graph in Neo4j:
- (:Standard) -[:HAS_SECTION]-> (:Section) -[:CONTAINS_CLAUSE]-> (:Clause)
- (:Clause) -[:MANDATES]-> (:Requirement) -[:APPLIES_TO]-> (:IfcClass)
- (:Clause) -[:CROSS_REFERENCES]-> (:Clause)

Provides hybrid retrieval and contextual graph navigation for building codes
(IBC 2024, NFPA 101, ADA Standards, SBC).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.modules.contracts.graph import (
    GoverningRequirementsResponse,
    RegulatoryClauseNode,
    RegulatoryGraphContextResponse,
    RegulatoryRequirementItem,
)
from app.services.graph_database import GraphService
from app.services.rules_service import RuleService

logger = logging.getLogger("bimguard.services.regulatory_graph")

# Known architectural building standards and sections
_CURATED_STANDARDS_MAP: dict[str, dict[str, Any]] = {
    "IBC 2024": {
        "title": "International Building Code (2024 Edition)",
        "sections": {
            "1005": "Means of Egress Sizing",
            "1006": "Number of Exits and Exit Access Doorways",
            "1011": "Stairways and Ramps",
            "1017": "Exit Access Travel Distance",
            "1020": "Corridors and Egress Passageways",
            "716": "Opening Protectives and Fire Door Assemblies",
        },
    },
    "NFPA 101": {
        "title": "Life Safety Code (2024 Edition)",
        "sections": {
            "7.2": "Means of Egress Components - Doors and Stairs",
            "7.3": "Capacity of Means of Egress",
            "7.6": "Travel Distance to Exits",
            "8.2": "Construction and Compartmentation",
        },
    },
    "ADA 2010": {
        "title": "ADA Standards for Accessible Design",
        "sections": {
            "404": "Doors, Doorways, and Gates",
            "405": "Ramps and Walking Surfaces",
            "406": "Curb Ramps",
        },
    },
}

_CROSS_REF_RE = re.compile(r"\b(?:Section|Clause|Item)\s+([\w\.\-]+)", re.IGNORECASE)


def _resolve_standard_and_clause(rule: Any) -> tuple[str, str]:
    """Resolve standard name and clause string from rule fields."""
    std = getattr(rule, "standard", None) or getattr(rule, "ruleset_id", None)
    rule_id_str = str(getattr(rule, "rule_id", "") or "")
    if std and std.strip():
        standard = std.strip()
    elif rule_id_str.startswith("IBC"):
        standard = "IBC 2024"
    elif rule_id_str.startswith("NFPA"):
        standard = "NFPA 101"
    elif rule_id_str.startswith("ADA"):
        standard = "ADA 2010"
    elif rule_id_str.startswith("SBC"):
        standard = "SBC 2018"
    else:
        standard = "IBC 2024"

    clause = getattr(rule, "clause", None) or getattr(rule, "code", None) or rule_id_str or f"Rule_{getattr(rule, 'id', '')}"
    return standard, clause


class RegulatoryGraphService:
    """Manages the Regulatory Knowledge Graph and cross-clause GraphRAG queries."""

    def __init__(
        self,
        rules_service: RuleService | None = None,
        graph_service: GraphService | None = None,
    ) -> None:
        self.rules_service = rules_service or RuleService()
        self.graph_service = graph_service

    def get_governing_requirements(self, ifc_type: str) -> GoverningRequirementsResponse:
        """Find all regulatory requirements and rules governing a specific IFC entity type.

        Args:
            ifc_type: Target IFC entity class, e.g. 'IfcDoor', 'IfcWall', 'IfcSpace'.

        Returns:
            GoverningRequirementsResponse with rules grouped by standards.
        """
        all_rules = self.rules_service.list_rules()
        matching_items: list[RegulatoryRequirementItem] = []
        standards_set: set[str] = set()

        clean_type = ifc_type.strip()

        for rule in all_rules:
            target = getattr(rule, "target_ifc_class", "") or ""
            target_types = [t.strip() for t in target.split(",") if t.strip()]

            if clean_type in target_types or clean_type.lower() == target.lower():
                std, clause = _resolve_standard_and_clause(rule)
                standards_set.add(std)

                param = getattr(rule, "property_name", None) or getattr(rule, "parameter", None) or "ComplianceCriteria"
                val = getattr(rule, "check_value", None) or getattr(rule, "value", None) or getattr(rule, "value_min", "")
                desc = getattr(rule, "description", None) or getattr(rule, "name", "") or ""

                matching_items.append(
                    RegulatoryRequirementItem(
                        rule_id=getattr(rule, "id", None),
                        standard=std,
                        clause=clause,
                        target_ifc_type=clean_type,
                        parameter=param,
                        operator=getattr(rule, "operator", "==") or "==",
                        value=val,
                        unit=getattr(rule, "unit", None),
                        severity=getattr(rule, "severity", "critical") or "critical",
                        description=desc,
                    )
                )

        return GoverningRequirementsResponse(
            ifc_type=clean_type,
            total_requirements=len(matching_items),
            standards_covered=sorted(standards_set),
            requirements=matching_items,
        )

    def get_clause_context(self, clause_ref: str) -> RegulatoryGraphContextResponse:
        """Retrieve contextual knowledge graph neighborhood for a regulatory clause.

        Args:
            clause_ref: Clause identifier, code reference, or clause string (e.g. '1017.2', 'IBC-1017.2').

        Returns:
            RegulatoryGraphContextResponse including parent section, cross-references, and governed types.
        """
        all_rules = self.rules_service.list_rules()
        matched_rule = None
        clean_ref = clause_ref.strip()

        for rule in all_rules:
            ref = str(getattr(rule, "reference", "") or "").strip()
            clause = str(getattr(rule, "clause", "") or "").strip()
            code = str(getattr(rule, "code", "") or "").strip()
            rule_id_str = str(getattr(rule, "rule_id", "") or "").strip()
            desc = str(getattr(rule, "description", "") or "").strip()
            if (
                clean_ref in (ref, clause, code, rule_id_str)
                or (clean_ref.lower() in ref.lower())
                or (clean_ref.lower() in rule_id_str.lower())
                or (clean_ref.lower() in desc.lower())
            ):
                matched_rule = rule
                break

        standard = getattr(matched_rule, "standard", "IBC 2024") if matched_rule else "IBC 2024"
        clause_id = getattr(matched_rule, "clause", clean_ref) if matched_rule else clean_ref
        title = (
            getattr(matched_rule, "name", f"Regulatory Requirement {clean_ref}")
            if matched_rule
            else f"Requirement {clean_ref}"
        )
        text = getattr(matched_rule, "description", "") if matched_rule else ""
        target_ifc = getattr(matched_rule, "target_ifc_class", "IfcProduct") if matched_rule else "IfcProduct"
        target_types = [t.strip() for t in target_ifc.split(",") if t.strip()]

        # Extract cross-references mentioned in the rule description
        raw_refs = _CROSS_REF_RE.findall(text)
        cross_refs = [r.strip().rstrip(".,:;") for r in raw_refs if r.strip().rstrip(".,:;")]

        # Infer section number
        parts = clause_id.split(".")
        section_num = parts[0] if parts else "General"

        std_info = _CURATED_STANDARDS_MAP.get(standard, {})
        section_title = std_info.get("sections", {}).get(section_num, f"Section {section_num}")

        clause_node = RegulatoryClauseNode(
            clause_id=clause_id,
            standard=standard,
            section=f"{section_num} - {section_title}",
            title=title,
            text=text,
            target_ifc_types=target_types,
            cross_references=cross_refs,
        )

        extracted_reqs: list[RegulatoryRequirementItem] = []
        if matched_rule:
            extracted_reqs.append(
                RegulatoryRequirementItem(
                    rule_id=getattr(matched_rule, "id", None),
                    standard=standard,
                    clause=clause_id,
                    target_ifc_type=target_types[0] if target_types else "IfcProduct",
                    parameter=getattr(matched_rule, "parameter", "") or "ComplianceCheck",
                    operator=getattr(matched_rule, "operator", "==") or "==",
                    value=getattr(matched_rule, "value", ""),
                    unit=getattr(matched_rule, "unit", None),
                    severity=getattr(matched_rule, "severity", "critical") or "critical",
                    description=text,
                )
            )

        # Build mock or connected cross-referenced nodes
        cross_referenced_clauses: list[RegulatoryClauseNode] = []
        for xref in cross_refs[:5]:
            cross_referenced_clauses.append(
                RegulatoryClauseNode(
                    clause_id=xref,
                    standard=standard,
                    section=f"Cross-Reference {xref}",
                    title=f"Related provision {xref}",
                    text=f"Referenced requirement from parent clause {clause_id}",
                    target_ifc_types=target_types,
                    cross_references=[],
                )
            )

        return RegulatoryGraphContextResponse(
            clause=clause_node,
            parent_section=f"{section_num}: {section_title}",
            cross_referenced_clauses=cross_referenced_clauses,
            governed_ifc_types=target_types,
            extracted_requirements=extracted_reqs,
        )

    def ingest_regulatory_graph(self) -> dict[str, int]:
        """Ingest all catalog rules and standards into the graph database.

        Creates:
        - (:Standard)
        - (:Section)
        - (:Clause)
        - (:Requirement)
        - (:IfcClass)
        And relationships (:HAS_SECTION), (:CONTAINS_CLAUSE), (:MANDATES), (:APPLIES_TO).

        Returns:
            Dict with total nodes and relationships created.
        """
        if not self.graph_service or not self.graph_service.provider:
            return {"nodes": 0, "relationships": 0, "status": "skipped_no_provider"}

        all_rules = self.rules_service.list_rules()
        standards_nodes: dict[str, dict[str, Any]] = {}
        section_nodes: dict[str, dict[str, Any]] = {}
        clause_nodes: dict[str, dict[str, Any]] = {}
        requirement_nodes: dict[str, dict[str, Any]] = {}
        ifc_class_nodes: dict[str, dict[str, Any]] = {}

        has_section_edges: list[dict[str, Any]] = []
        contains_clause_edges: list[dict[str, Any]] = []
        mandates_edges: list[dict[str, Any]] = []
        applies_to_edges: list[dict[str, Any]] = []

        for rule in all_rules:
            std_name = getattr(rule, "standard", "IBC 2024") or "IBC 2024"
            std_id = f"STD_{std_name.replace(' ', '_')}"
            standards_nodes[std_id] = {
                "id": std_id,
                "name": std_name,
                "title": _CURATED_STANDARDS_MAP.get(std_name, {}).get("title", std_name),
            }

            clause_str = getattr(rule, "clause", "") or getattr(rule, "code", "") or f"Rule_{rule.id}"
            parts = clause_str.split(".")
            sec_num = parts[0] if parts else "General"
            sec_id = f"SEC_{std_id}_{sec_num}"

            section_nodes[sec_id] = {
                "id": sec_id,
                "number": sec_num,
                "standard": std_name,
                "name": f"Section {sec_num}",
            }
            has_section_edges.append({"source_id": std_id, "target_id": sec_id})

            clause_id = f"CLS_{std_id}_{clause_str}"
            clause_nodes[clause_id] = {
                "id": clause_id,
                "clause_id": clause_str,
                "standard": std_name,
                "title": getattr(rule, "name", ""),
                "description": getattr(rule, "description", ""),
            }
            contains_clause_edges.append({"source_id": sec_id, "target_id": clause_id})

            req_id = f"REQ_{rule.id}"
            requirement_nodes[req_id] = {
                "id": req_id,
                "rule_id": rule.id,
                "parameter": getattr(rule, "parameter", "") or "",
                "operator": getattr(rule, "operator", "") or "",
                "value": str(getattr(rule, "value", "")),
                "severity": getattr(rule, "severity", "critical") or "critical",
            }
            mandates_edges.append({"source_id": clause_id, "target_id": req_id})

            target_class = getattr(rule, "target_ifc_class", "") or "IfcProduct"
            for tc in [t.strip() for t in target_class.split(",") if t.strip()]:
                class_id = f"IFC_{tc}"
                ifc_class_nodes[class_id] = {"id": class_id, "name": tc}
                applies_to_edges.append({"source_id": req_id, "target_id": class_id})

        # Batch write nodes
        self.graph_service.add_nodes_batch("Standard", list(standards_nodes.values()))
        self.graph_service.add_nodes_batch("Section", list(section_nodes.values()))
        self.graph_service.add_nodes_batch("Clause", list(clause_nodes.values()))
        self.graph_service.add_nodes_batch("Requirement", list(requirement_nodes.values()))
        self.graph_service.add_nodes_batch("IfcClass", list(ifc_class_nodes.values()))

        # Batch write edges
        self.graph_service.add_edges_batch("HAS_SECTION", has_section_edges)
        self.graph_service.add_edges_batch("CONTAINS_CLAUSE", contains_clause_edges)
        self.graph_service.add_edges_batch("MANDATES", mandates_edges)
        self.graph_service.add_edges_batch("APPLIES_TO", applies_to_edges)

        total_nodes = (
            len(standards_nodes)
            + len(section_nodes)
            + len(clause_nodes)
            + len(requirement_nodes)
            + len(ifc_class_nodes)
        )
        total_edges = (
            len(has_section_edges)
            + len(contains_clause_edges)
            + len(mandates_edges)
            + len(applies_to_edges)
        )

        logger.info(
            "Regulatory knowledge graph ingested: %d nodes, %d edges across %d rules",
            total_nodes,
            total_edges,
            len(all_rules),
        )

        return {
            "nodes": total_nodes,
            "edges": total_edges,
            "rules_count": len(all_rules),
            "status": "success",
        }
