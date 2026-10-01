"""Hybrid specification and document graph retriever using Vector, BM25, and Topological RRF."""

import re
from typing import Any, Optional

from app.logging_config import get_logger
from app.modules.contracts.graph import GraphRagCitation, GraphRagToolCall
from app.services.embedding_service import EmbeddingService
from app.services.graph_database import GraphService
from app.services.graph_rag.constants import _DOC_QUERY_STOPWORDS
from app.services.graph_rag.fusion import compute_reciprocal_rank_fusion

logger = get_logger(__name__)


class DocumentGraphRetriever:
    """Multi-stream hybrid retriever across regulatory documents and specification graphs."""

    def __init__(
        self,
        graph_service: GraphService,
        embedding_service: Optional[EmbeddingService] = None,
        projects_service: Optional[Any] = None,
    ):
        self.graph_service = graph_service
        self.embedding_service = embedding_service or EmbeddingService()
        self.projects_service = projects_service

    async def retrieve(
        self,
        query: str,
        document_id: Optional[int] = None,
        target_classes: Optional[list[str]] = None,
        concrete_clauses: Optional[list[str]] = None,
        abstract_themes: Optional[list[str]] = None,
        intent_type: str = "compliance_check",
        project_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Perform hybrid RRF retrieval across Vector, BM25, and Graph streams."""
        citations: list[GraphRagCitation] = []
        cypher_runs: list[str] = []
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        # 1. Specialized handling for Document Inventory
        if intent_type == "document_inventory":
            client_docs = []
            if self.projects_service and project_id:
                try:
                    client_docs = self.projects_service.get_client_documents_by_project(project_id) or []
                except Exception as exc:
                    logger.debug("Notice querying client documents for inventory: %s", exc)

            graph_docs = []
            if self.graph_service and self.graph_service.provider:
                try:
                    cypher_doc_summary = """
                    MATCH (d:Document)
                    OPTIONAL MATCH (d)-[:HAS_SECTION]->(s:DocumentSection)
                    RETURN d.id as doc_id, d.title as title, count(s) as root_sections
                    ORDER BY d.id ASC
                    """
                    graph_docs = self.graph_service.execute(cypher_doc_summary, {}) or []
                except Exception as exc:
                    logger.debug("Notice querying graph documents for inventory: %s", exc)

            text_lines = []
            total_count = max(len(client_docs), len(graph_docs))
            if client_docs:
                text_lines.append(f"### Project Document & Specification Inventory (Total: {len(client_docs)} document{'s' if len(client_docs) != 1 else ''}):")
                for d in client_docs:
                    doc_id = d.get("id") or "doc"
                    title = d.get("title") or d.get("file_name") or f"Document {doc_id}"
                    dtype = d.get("document_type") or "specification"
                    cde_state = d.get("cde_state") or "SHARED"
                    ref_tag = f"Doc: {title}"
                    text_lines.append(f"- [{ref_tag}] Type: {dtype}, CDE State: {cde_state}")
                    citations.append(
                        GraphRagCitation(
                            id=f"doc_inv_{doc_id}",
                            source_type="document",
                            title=f"Specification: {title}",
                            reference=title,
                            snippet=f"Attached project specification '{title}' (Type: {dtype}, CDE State: {cde_state}).",
                            score=2.0,
                            retrieval_method="graph",
                        )
                    )
            elif graph_docs:
                text_lines.append(f"### Knowledge Graph Document Specifications (Total: {len(graph_docs)}):")
                for d in graph_docs:
                    doc_id = d.get("doc_id") or 1
                    title = d.get("title") or f"Document {doc_id}"
                    sec_count = d.get("root_sections", 0)
                    ref_tag = f"Doc: {title}"
                    text_lines.append(f"- [{ref_tag}] Sections: {sec_count}")
                    citations.append(
                        GraphRagCitation(
                            id=f"graph_doc_{doc_id}",
                            source_type="document",
                            title=f"Document: {title}",
                            reference=title,
                            snippet=f"Specification '{title}' with {sec_count} sections.",
                            score=2.0,
                            retrieval_method="graph",
                        )
                    )
            else:
                text_lines.append("### Project Document & Specification Inventory:\nTotal documents: 0.\nNo specification documents attached to this project.")

            return {
                "text": "\n".join(text_lines),
                "citations": citations,
                "tool_call": GraphRagToolCall(
                    tool_name="query_document_inventory",
                    arguments={"project_id": project_id, "total_documents": total_count},
                    output_summary=f"Found {total_count} document(s) for project {project_id}.",
                    status="success",
                ),
                "cypher": "",
                "nodes": nodes,
                "edges": [],
            }

        if not self.graph_service or not self.graph_service.provider:
            return {
                "text": "Document graph persistence provider not connected.",
                "citations": citations,
                "tool_call": GraphRagToolCall(
                    tool_name="hybrid_rrf_retrieval",
                    arguments={"query": query, "document_id": document_id},
                    output_summary="Provider offline",
                    status="error",
                ),
                "cypher": None,
                "nodes": [],
                "edges": [],
            }

        # Determine search terms for BM25
        search_terms: list[str] = []
        if concrete_clauses:
            search_terms.extend(concrete_clauses)
        words = [
            w for w in re.findall(r"\b[a-zA-Z0-9\.\-]+\b", query)
            if len(w) > 2 and w.lower() not in _DOC_QUERY_STOPWORDS
        ]
        if words:
            search_terms.extend(words[:3])

        streams: dict[str, list[dict[str, Any]]] = {
            "vector": [],
            "bm25": [],
            "graph": [],
        }

        # -------------------------------------------------------------------
        # Stream 1: Dense Vector Similarity (Neo4j native HNSW)
        # -------------------------------------------------------------------
        try:
            query_embedding = await self.embedding_service.get_embedding(query)
            cypher_vector = """
            CALL db.index.vector.queryNodes('document_section_vector', 10, $emb)
            YIELD node as s, score
            RETURN s.id as id, s.document_id as doc_id, s.section_number as sec_num,
                   s.section_name as title, s.summary as summary, s.page_number as page,
                   score as stream_score
            ORDER BY score DESC
            """
            v_rows = self.graph_service.execute(cypher_vector, {"emb": query_embedding})
            if v_rows:
                # Discard low-similarity distant noise unless explicit domain terms exist
                filtered_v_rows = [r for r in v_rows if (r.get("stream_score") or 0.0) >= 0.60]
                if not filtered_v_rows and (search_terms or concrete_clauses or target_classes or abstract_themes):
                    filtered_v_rows = v_rows[:3]
                streams["vector"] = filtered_v_rows
                cypher_runs.append(cypher_vector.strip())
        except Exception as exc:
            logger.debug("Native vector index search skipped or unavailable: %s", exc)

        # -------------------------------------------------------------------
        # Stream 2: Lexical BM25 (Neo4j native Fulltext)
        # -------------------------------------------------------------------
        try:
            if search_terms:
                lucene_query = " OR ".join(f"{term}*" for term in search_terms)
                cypher_bm25 = """
                CALL db.index.fulltext.queryNodes('document_section_fulltext', $query)
                YIELD node as s, score
                RETURN s.id as id, s.document_id as doc_id, s.section_number as sec_num,
                       s.section_name as title, s.summary as summary, s.page_number as page,
                       score as stream_score
                ORDER BY score DESC
                LIMIT 10
                """
                b_rows = self.graph_service.execute(cypher_bm25, {"query": lucene_query})
                if b_rows:
                    streams["bm25"] = b_rows
                    cypher_runs.append(cypher_bm25.strip())
        except Exception as exc:
            logger.debug("Fulltext BM25 index search skipped or unavailable: %s", exc)

        # -------------------------------------------------------------------
        # Stream 3: Topological Graph Expansion (Section -> Clause -> Subclause)
        # -------------------------------------------------------------------
        if concrete_clauses:
            for clause in concrete_clauses:
                cypher_graph = """
                MATCH (s:DocumentSection)
                WHERE s.section_number = $clause OR s.section_number STARTS WITH $clause
                OPTIONAL MATCH (s)-[:HAS_SUBSECTION*1..2]->(sub:DocumentSection)
                RETURN s.id as id, s.document_id as doc_id, s.section_number as sec_num,
                       s.section_name as title, s.summary as summary, s.page_number as page,
                       1.0 as stream_score
                LIMIT 5
                """
                g_rows = self.graph_service.execute(cypher_graph, {"clause": clause})
                if g_rows:
                    streams["graph"].extend(g_rows)
                    cypher_runs.append(cypher_graph.strip())

        # Fallback if indices are not yet built or populated
        if not any(streams.values()):
            cypher_fallback = """
            MATCH (s:DocumentSection)
            RETURN s.id as id, s.document_id as doc_id, s.section_number as sec_num,
                   s.section_name as title, s.summary as summary, s.page_number as page,
                   0.5 as stream_score
            LIMIT 5
            """
            fb_rows = self.graph_service.execute(cypher_fallback, {})
            if fb_rows:
                streams["vector"] = fb_rows
                cypher_runs.append(cypher_fallback.strip())

        # Fused Top-K ranking using Reciprocal Rank Fusion
        fused_sections = compute_reciprocal_rank_fusion(streams, k=60, top_n=6)

        text_lines: list[str] = []
        for sec in fused_sections:
            sec_num = sec.get("sec_num") or "Sec"
            title = sec.get("title") or "Specification Provision"
            summary = sec.get("summary") or "Section requirement"
            page = sec.get("page")
            score = sec.get("rrf_score", 0.0)

            ref_tag = f"Section {sec_num}" if sec_num != "Sec" else title
            page_tag = f", p. {page}" if page else ""
            text_lines.append(f"- [Doc: {ref_tag}{page_tag}] {title}: {summary}")

            citation_id = f"doc_{sec_num}" if sec_num != "Sec" else f"doc_{sec.get('id')}"
            citations.append(
                GraphRagCitation(
                    id=citation_id,
                    source_type="document",
                    title=f"{ref_tag}: {title}",
                    reference=ref_tag,
                    snippet=summary,
                    page_number=page,
                    score=round(score, 6),
                    retrieval_method="hybrid_rrf",
                    rrf_score=round(score, 6),
                    properties={
                        "target_classes": target_classes or [],
                        "stream_ranks": sec.get("stream_ranks", {}),
                    },
                )
            )

            nodes.append({
                "id": str(sec.get("id")),
                "label": f"{sec_num}: {title[:20]}",
                "type": "DocumentSection",
            })

        output_summary = f"Fused {len(fused_sections)} sections via RRF (k=60) across Vector, BM25, and Graph."
        combined_cypher = "\n\n// --- Combined RRF Retrieval Streams ---\n".join(cypher_runs[:2]) if cypher_runs else None

        return {
            "text": "\n".join(text_lines),
            "citations": citations,
            "tool_call": GraphRagToolCall(
                tool_name="hybrid_rrf_retrieval",
                arguments={
                    "vector_candidates": len(streams["vector"]),
                    "bm25_candidates": len(streams["bm25"]),
                    "graph_candidates": len(streams["graph"]),
                    "top_selected": len(fused_sections),
                },
                output_summary=output_summary,
                cypher_query=combined_cypher,
                status="success",
            ),
            "cypher": combined_cypher,
            "nodes": nodes,
            "edges": edges,
        }
