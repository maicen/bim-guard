"""Backward-compatibility facade for GraphRagService.

All implementation details are now modularized under `app.services.graph_rag`:
- `GraphRagQueryRouter`: Query intent classification & LightRAG routing.
- `DocumentGraphRetriever`: Native HNSW Vector + Fulltext BM25 + Section Graph RRF.
- `ModelGraphRetriever`: IFC BIM model graph traversal, spatial hierarchy, & inventory.
- `GraphRagSynthesizer`: LiteLLM answer generation, streaming, & follow-ups.
- `compute_reciprocal_rank_fusion`: Core RRF ranking math.
"""

from app.services.graph_rag import (
    _DOC_QUERY_STOPWORDS,
    _IFC_KEYWORD_MAP,
    _RAG_SYSTEM_PROMPT,
    _STOP_ENTITIES,
    _THEME_KEYWORDS,
    DocumentGraphRetriever,
    GraphRagQueryRouter,
    GraphRagService,
    GraphRagSynthesizer,
    ModelGraphRetriever,
    compute_reciprocal_rank_fusion,
)

__all__ = [
    "GraphRagService",
    "GraphRagQueryRouter",
    "DocumentGraphRetriever",
    "ModelGraphRetriever",
    "GraphRagSynthesizer",
    "compute_reciprocal_rank_fusion",
    "_IFC_KEYWORD_MAP",
    "_THEME_KEYWORDS",
    "_STOP_ENTITIES",
    "_DOC_QUERY_STOPWORDS",
    "_RAG_SYSTEM_PROMPT",
]
