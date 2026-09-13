"""Unit tests for explainable compliance proof graph generation."""

from __future__ import annotations

from app.modules.comparator.issue_schema import RiskBand, build_issue_proof_graph, make_issue
from app.modules.contracts import IssueProofGraphContract


def test_build_issue_proof_graph_from_dataclass():
    issue = make_issue(
        id="BGR-0042",
        element_id="3Kf7q8XzR1pP2mN4gV8xQ",
        rule_id="GC-001.03",
        title="Galvanic dissimilar metal coupling",
        mechanism="GC-001 galvanic",
        band=RiskBand.CRITICAL,
        score=0.89,
        metadata={
            "anode_material": "GalvanisedSteel",
            "cathode_material": "SS316",
            "voltage_v": 0.74,
            "area_ratio": 0.02,
        },
        citations=[
            {
                "standard": "NASA-STD-6012",
                "clause": "Table 2",
                "reason": "voltage gap exceeds harsh environment threshold",
            }
        ],
        mitigation="Insert dielectric insulator between dissimilar metals.",
    )

    proof_dict = build_issue_proof_graph(issue)

    # Validate against strict Pydantic contract
    contract = IssueProofGraphContract(**proof_dict)
    assert contract.issue_id == "BGR-0042"
    assert contract.rule_id == "GC-001.03"
    assert contract.element_id == "3Kf7q8XzR1pP2mN4gV8xQ"

    # Verify node structure
    node_types = {n.node_type for n in contract.nodes}
    assert "asserted_fact" in node_types
    assert "rule_axiom" in node_types
    assert "inference_step" in node_types
    assert "verdict" in node_types

    # Verify edges exist and connect nodes
    node_ids = {n.id for n in contract.nodes}
    for edge in contract.edges:
        assert edge.source in node_ids
        assert edge.target in node_ids

    # Verify verdict node exists
    verdict_nodes = [n for n in contract.nodes if n.node_type == "verdict"]
    assert len(verdict_nodes) == 1
    assert "FAIL" in verdict_nodes[0].label
    assert verdict_nodes[0].metadata["band"] == "critical"
    assert verdict_nodes[0].metadata["score"] == 0.89


def test_build_issue_proof_graph_from_dict():
    issue_data = {
        "id": "ARCH-001",
        "element_id": "DOOR-GUID-12345",
        "rule_id": "ARCH-EGRESS-001",
        "title": "Door clear opening width less than 800mm",
        "band": "high",
        "score": 0.75,
        "metadata": {
            "clear_width_mm": 750.0,
            "required_width_mm": 800.0,
        },
        "citations": [
            {"standard": "BUILDING-CODE-PART9", "clause": "9.9.10.1"}
        ],
        "mitigation": "Increase door leaf dimension to meet code.",
    }

    proof_dict = build_issue_proof_graph(issue_data)
    contract = IssueProofGraphContract(**proof_dict)

    assert contract.issue_id == "ARCH-001"
    assert any("750.0" in n.label for n in contract.nodes)
    assert any("9.9.10.1" in n.label for n in contract.nodes)
    assert "DOOR-GUID-12345" in contract.explanation
