"""Unit tests for Reciprocal Rank Fusion and SOTA Graph-RAG routing."""

from unittest.mock import MagicMock

from app.services.graph_rag_service import (
    GraphRagService,
    compute_reciprocal_rank_fusion,
)


def test_reciprocal_rank_fusion_formula():
    """Verify RRF formula correctly merges disparate candidate streams."""
    vector_stream = [
        {"id": "doc_101", "title": "Vector First"},
        {"id": "doc_102", "title": "Vector Second"},
    ]
    bm25_stream = [
        {"id": "doc_102", "title": "BM25 First"},
        {"id": "doc_103", "title": "BM25 Second"},
    ]
    graph_stream = [
        {"id": "doc_102", "title": "Graph First"},
        {"id": "doc_101", "title": "Graph Second"},
    ]

    rankings = {
        "vector": vector_stream,
        "bm25": bm25_stream,
        "graph": graph_stream,
    }

    fused = compute_reciprocal_rank_fusion(rankings, k=60, id_key="id")

    # doc_102 appeared in all 3 streams (rank 2, 1, 1), so it must have highest RRF score
    assert len(fused) == 3
    assert fused[0]["id"] == "doc_102"
    # RRF score for doc_102: 1/(60+2) + 1/(60+1) + 1/(60+1)
    expected_score = round(1.0 / 62 + 1.0 / 61 + 1.0 / 61, 6)
    assert fused[0]["rrf_score"] == expected_score
    assert fused[0]["rrf_stream_ranks"] == {"vector": 2, "bm25": 1, "graph": 1}

    # doc_101 appeared in vector (rank 1) and graph (rank 2)
    assert fused[1]["id"] == "doc_101"
    expected_score_101 = round(1.0 / 61 + 1.0 / 62, 6)
    assert fused[1]["rrf_score"] == expected_score_101


def test_dual_level_query_analysis():
    """Verify LightRAG dual-level query analysis extracts entities and themes."""
    service = GraphRagService(graph_service=MagicMock())

    # Concrete query with clause code and element class
    analysis = service._analyze_query_dual_level(
        "What is the minimum exit door clear width under Section 1017.2?"
    )
    assert "IfcDoor" in analysis["target_classes"]
    assert "1017.2" in analysis["concrete_clauses"]
    assert "egress" in analysis["abstract_themes"]
    assert "accessibility" in analysis["abstract_themes"]
    assert analysis["retrieval_mode"] == "hybrid_rrf"

    # Global summarization query
    global_analysis = service._analyze_query_dual_level(
        "Give me an overall summary of primary fire and egress compliance risks across all corridors."
    )
    assert global_analysis["retrieval_mode"] == "global"
    assert "fire_protection" in global_analysis["abstract_themes"]
    assert "egress" in global_analysis["abstract_themes"]
