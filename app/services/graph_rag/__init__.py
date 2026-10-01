"""Modular Graph-RAG system with dedicated routers, retrievers, fusion rankers, and synthesis workers."""

from app.services.graph_rag.constants import (
    _DOC_QUERY_STOPWORDS,
    _IFC_KEYWORD_MAP,
    _RAG_SYSTEM_PROMPT,
    _STOP_ENTITIES,
    _THEME_KEYWORDS,
)
from app.services.graph_rag.document_retriever import DocumentGraphRetriever
from app.services.graph_rag.fusion import compute_reciprocal_rank_fusion
from app.services.graph_rag.model_retriever import ModelGraphRetriever
from app.services.graph_rag.query_router import GraphRagQueryRouter
from app.services.graph_rag.service import GraphRagService
from app.services.graph_rag.synthesizer import GraphRagSynthesizer

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
