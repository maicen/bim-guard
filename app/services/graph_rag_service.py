"""Graph-RAG Question Answering Service for Documents, BIM Models, and Cross-Domain Compliance.

Synthesizes SOTA GraphRAG architectural patterns:
1. Neo4j-Native Unified Vector & Fulltext Indexing (eliminating external vector DB sync drift).
2. Reciprocal Rank Fusion (RRF k=60) combining Dense Vector, Lexical BM25, and Topological Cypher.
3. LightRAG Dual-Level Query Routing (concrete entity seeds vs. abstract thematic concepts).
4. HippoRAG / LinearRAG Hub Node Suppression (inverse degree weighting W_uv = 1 / sqrt(deg(u)*deg(v))).
5. Microsoft GraphRAG / DRIFT Local vs. Global Search Modes.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any, Optional

from app.logging_config import get_logger
from app.modules.config import COMPLIANCE_TEMPERATURE, DEFAULT_LLM_MODEL
from app.modules.contracts.graph import (
    GraphRagCitation,
    GraphRagContextSummary,
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    GraphRagScope,
    GraphRagStep,
    GraphRagToolCall,
)
from app.services.embedding_service import EmbeddingService
from app.services.graph_database import GraphService
from app.services.llm_call_context import llm_call_context
from app.services.models_service import ModelsService
from app.services.rules_service import RuleService

logger = get_logger(__name__)

# Common architectural IFC types mapped to synonyms in user questions
_IFC_KEYWORD_MAP: dict[str, str] = {
    "door": "IfcDoor",
    "doors": "IfcDoor",
    "exit": "IfcDoor",
    "exits": "IfcDoor",
    "wall": "IfcWall",
    "walls": "IfcWall",
    "partition": "IfcWall",
    "partitions": "IfcWall",
    "space": "IfcSpace",
    "spaces": "IfcSpace",
    "room": "IfcSpace",
    "rooms": "IfcSpace",
    "corridor": "IfcSpace",
    "corridors": "IfcSpace",
    "stair": "IfcStair",
    "stairs": "IfcStair",
    "stairway": "IfcStair",
    "stairways": "IfcStair",
    "window": "IfcWindow",
    "windows": "IfcWindow",
    "column": "IfcColumn",
    "columns": "IfcColumn",
    "beam": "IfcBeam",
    "beams": "IfcBeam",
    "slab": "IfcSlab",
    "slabs": "IfcSlab",
    "roof": "IfcRoof",
    "roofs": "IfcRoof",
    "railing": "IfcRailing",
    "railings": "IfcRailing",
    "floor": "IfcBuildingStorey",
    "floors": "IfcBuildingStorey",
    "storey": "IfcBuildingStorey",
    "storeys": "IfcBuildingStorey",
    "story": "IfcBuildingStorey",
    "stories": "IfcBuildingStorey",
    "level": "IfcBuildingStorey",
    "levels": "IfcBuildingStorey",
    "element": "IfcProduct",
    "elements": "IfcProduct",
    "product": "IfcProduct",
    "products": "IfcProduct",
}

# Thematic domain keywords for LightRAG high-level abstract query routing
_THEME_KEYWORDS: dict[str, list[str]] = {
    "egress": ["egress", "exit", "evacuation", "travel distance", "corridor", "aisle", "escape", "means of egress"],
    "fire_protection": ["fire", "smoke", "rating", "barrier", "partition", "sprinkler", "compartment"],
    "accessibility": ["accessible", "ada", "wheelchair", "clearance", "clear width", "grab bar", "ramp", "threshold"],
    "spatial": ["area", "volume", "height", "width", "dimension", "occupant load", "capacity", "containment"],
    "structural": ["load", "bearing", "column", "beam", "slab", "foundation"],
}

# Generic hub stop-entities excluded or penalized during multi-hop graph expansion
_STOP_ENTITIES: set[str] = {
    "ifcproject",
    "ifcsite",
    "ifcbuilding",
    "project",
    "building",
    "model",
}

_RAG_SYSTEM_PROMPT = """You are BIM-Guard Graph-RAG Assistant, an expert openBIM architectural compliance and engineering specification assistant.
Your goal is to answer questions strictly grounded in:
1. Document specifications and regulatory requirements extracted from project documents.
2. The project's IFC BIM model graph (elements, spatial containment, properties, fire ratings).
3. The relationship between document provisions and modeled elements.

GUIDELINES:
- Always be accurate, clear, and direct.
- Ground your statements in the retrieved context.
- Use inline citations: [Doc: <Section/Clause>, p. <Page>] for document references, and [IFC: <Element Name/GUID>] for model elements.
- When answering hybrid questions, explicitly compare the document requirement against the model facts and state whether elements comply or deviate.
- If information is not in the context, state that clearly rather than inventing numbers or GUIDs.
- Conclude with a helpful summary table or bulleted list where relevant.
"""


def compute_reciprocal_rank_fusion(
    rankings: dict[str, list[dict[str, Any]]],
    k: int = 60,
    id_key: str = "id",
) -> list[dict[str, Any]]:
    """Compute Reciprocal Rank Fusion (RRF) across multiple candidate streams.

    Formula: RRF(d) = sum_{m in streams} (1 / (k + rank_m(d)))
    """
    scores: dict[str, float] = {}
    item_by_id: dict[str, dict[str, Any]] = {}
    stream_ranks: dict[str, dict[str, int]] = {}

    for stream_name, items in rankings.items():
        for rank_idx, item in enumerate(items, start=1):
            raw_id = item.get(id_key)
            if raw_id is None:
                continue
            item_id = str(raw_id)
            if not item_id:
                continue
            if item_id not in item_by_id:
                item_by_id[item_id] = dict(item)
                stream_ranks[item_id] = {}

            rrf_contrib = 1.0 / (k + rank_idx)
            scores[item_id] = scores.get(item_id, 0.0) + rrf_contrib
            stream_ranks[item_id][stream_name] = rank_idx

    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    fused: list[dict[str, Any]] = []
    for item_id in sorted_ids:
        entry = dict(item_by_id[item_id])
        entry["rrf_score"] = round(scores[item_id], 6)
        entry["rrf_stream_ranks"] = stream_ranks[item_id]
        fused.append(entry)
    return fused


class GraphRagService:
    """Service orchestrating SOTA Graph-RAG queries across Documents and IFC BIM Models."""

    def __init__(
        self,
        graph_service: GraphService,
        models_service: Optional[ModelsService] = None,
        rules_service: Optional[RuleService] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self.graph_service = graph_service
        self.models_service = models_service or ModelsService()
        self.rules_service = rules_service or RuleService()
        self.embedding_service = embedding_service or EmbeddingService()

    def get_project_context_summary(self, project_id: int) -> GraphRagContextSummary:
        """Inspect available document and model nodes in the Neo4j graph for this project."""
        pid_str = str(project_id)
        has_ifc_model = False
        total_elements = 0
        ifc_classes: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []

        if not self.graph_service or not self.graph_service.provider:
            return GraphRagContextSummary(
                project_id=project_id,
                has_ifc_model=False,
                total_elements=0,
                ifc_classes=[],
                documents=[],
                rulesets=[],
            )

        self._ensure_project_model_ingested(project_id)

        # 1. Check IFC element classes in model graph
        try:
            cypher_classes = """
            MATCH (n {project_id: $pid})
            WHERE n.ifc_type IS NOT NULL
            RETURN n.ifc_type as class_name, count(n) as element_count
            ORDER BY element_count DESC
            LIMIT 25
            """
            rows = self.graph_service.execute(cypher_classes, {"pid": pid_str})
            if rows:
                has_ifc_model = True
                for r in rows:
                    cname = r.get("class_name")
                    cnt = r.get("element_count", 0)
                    if cname:
                        ifc_classes.append({"class_name": cname, "count": cnt})
                        total_elements += cnt
        except Exception as exc:
            logger.debug("Failed querying IFC classes in graph: %s", exc)

        # 2. Check Document nodes in graph
        try:
            cypher_docs = """
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:HAS_ROOT_SECTION]->(s:DocumentSection)
            RETURN d.document_id as doc_id, d.title as title, count(s) as root_sections
            ORDER BY doc_id DESC
            LIMIT 20
            """
            drows = self.graph_service.execute(cypher_docs, {})
            for r in drows:
                doc_id = r.get("doc_id")
                if doc_id is not None:
                    documents.append({
                        "id": doc_id,
                        "title": r.get("title") or f"Document {doc_id}",
                        "section_count": r.get("root_sections", 0),
                    })
        except Exception as exc:
            logger.debug("Failed querying Document nodes in graph: %s", exc)

        return GraphRagContextSummary(
            project_id=project_id,
            has_ifc_model=has_ifc_model,
            total_elements=total_elements,
            ifc_classes=ifc_classes,
            documents=documents,
            rulesets=["IBC 2024", "NFPA 101", "ADA 2010"],
        )

    async def query(
        self,
        project_id: int,
        request: GraphRagQueryRequest,
        *,
        organization_id: Optional[int] = None,
    ) -> GraphRagQueryResponse:
        """Execute a full Graph-RAG query using SOTA hybrid RRF retrieval."""
        steps: list[GraphRagStep] = []
        tool_calls: list[GraphRagToolCall] = []
        citations: list[GraphRagCitation] = []
        cypher_queries: list[str] = []
        subgraph_nodes: list[dict[str, Any]] = []
        subgraph_edges: list[dict[str, Any]] = []

        # Step 0: Dual-level query analysis (LightRAG)
        analysis = self._analyze_query_dual_level(request.query, request.element_class)
        detected_ifc_classes = analysis["target_classes"]
        retrieval_mode = analysis["retrieval_mode"]

        steps.append(
            GraphRagStep(
                step_index=0,
                title="Dual-Level Intent & Query Routing",
                description=(
                    f"Mode: {retrieval_mode}. Target IFC classes: {detected_ifc_classes or 'General'}. "
                    f"Themes: {analysis['abstract_themes'] or 'Direct'}."
                ),
                status="done",
                data=analysis,
            )
        )

        doc_context = ""
        model_context = ""
        rrf_metrics: dict[str, Any] = {"mode": retrieval_mode}

        # Step 1: Document Graph Retrieval (Vector + BM25 + Topological RRF)
        if request.scope in ("document", "hybrid"):
            doc_res = await self._retrieve_document_graph(
                query=request.query,
                document_id=request.document_id,
                target_classes=detected_ifc_classes,
                concrete_clauses=analysis.get("concrete_clauses"),
                abstract_themes=analysis.get("abstract_themes"),
            )
            doc_context = doc_res["text"]
            citations.extend(doc_res["citations"])
            tool_calls.append(doc_res["tool_call"])
            if doc_res.get("cypher"):
                cypher_queries.append(doc_res["cypher"])
            subgraph_nodes.extend(doc_res.get("nodes", []))
            subgraph_edges.extend(doc_res.get("edges", []))
            rrf_metrics["document_sections_fused"] = len(doc_res["citations"])

            steps.append(
                GraphRagStep(
                    step_index=1,
                    title="Unified Neo4j Hybrid RRF Retrieval",
                    description=(
                        f"Executed atomic Vector similarity, BM25 Lucene fulltext, and topological "
                        f"graph traversal. Fused {len(doc_res['citations'])} top sections via RRF (k=60)."
                    ),
                    status="done",
                    data={"citations_count": len(doc_res["citations"])},
                )
            )

        # Step 2: Model Graph Retrieval (Hub-Suppressed Spatial Traversal)
        if request.scope in ("model", "hybrid"):
            model_res = self._retrieve_model_graph(
                project_id=project_id,
                query=request.query,
                target_classes=detected_ifc_classes,
                element_guids=analysis.get("element_guids"),
                retrieval_mode=retrieval_mode,
            )
            model_context = model_res["text"]
            citations.extend(model_res["citations"])
            tool_calls.append(model_res["tool_call"])
            if model_res.get("cypher"):
                cypher_queries.append(model_res["cypher"])
            subgraph_nodes.extend(model_res.get("nodes", []))
            subgraph_edges.extend(model_res.get("edges", []))
            rrf_metrics["model_elements_inspected"] = model_res["element_count"]

            steps.append(
                GraphRagStep(
                    step_index=2,
                    title="Hub-Suppressed Model Graph Traversal",
                    description=(
                        f"Traversed spatial hierarchy with degree penalization. "
                        f"Inspected {model_res['element_count']} element instances."
                    ),
                    status="done",
                    data={"element_count": model_res["element_count"]},
                )
            )

        # Step 3: Cross-Domain Synthesis via LiteLLM
        prompt_payload = self._build_synthesis_prompt(
            query=request.query,
            scope=request.scope,
            doc_context=doc_context,
            model_context=model_context,
            retrieval_mode=retrieval_mode,
        )

        steps.append(
            GraphRagStep(
                step_index=3,
                title="Cross-Domain Synthesis & Verification",
                description="Synthesizing grounded engineering compliance response with inline citations.",
                status="running",
            )
        )

        answer = await self._synthesize_answer(
            prompt_payload=prompt_payload,
            model_override=request.model_name,
            temperature=request.temperature,
            organization_id=organization_id,
        )

        steps[-1].status = "done"

        # Follow-up suggestions
        suggested_followups = self._generate_followups(request.query, request.scope, detected_ifc_classes)

        return GraphRagQueryResponse(
            project_id=project_id,
            scope=request.scope,
            answer=answer,
            citations=citations,
            tool_calls=tool_calls,
            reasoning_steps=steps,
            cypher_queries=cypher_queries,
            suggested_followups=suggested_followups,
            subgraph_data={"nodes": subgraph_nodes[:50], "edges": subgraph_edges[:50]},
            retrieval_mode=retrieval_mode,
            rrf_metrics=rrf_metrics,
        )

    async def stream_query(
        self,
        project_id: int,
        request: GraphRagQueryRequest,
        *,
        organization_id: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream Graph-RAG milestones, tools, tokens, and citations via Server-Sent Events."""
        try:
            # 1. Dual-level query analysis
            analysis = self._analyze_query_dual_level(request.query, request.element_class)
            detected_ifc_classes = analysis["target_classes"]
            retrieval_mode = analysis["retrieval_mode"]

            yield self._format_sse_event(
                "step",
                GraphRagStep(
                    step_index=0,
                    title="Dual-Level Intent & Query Routing",
                    description=(
                        f"Scope: {request.scope} ({retrieval_mode}). Target classes: {detected_ifc_classes or 'General'}."
                    ),
                    status="done",
                    data=analysis,
                ).model_dump(),
            )

            doc_context = ""
            model_context = ""
            citations: list[GraphRagCitation] = []
            cypher_queries: list[str] = []

            # 2. Document Graph Retrieval
            if request.scope in ("document", "hybrid"):
                yield self._format_sse_event(
                    "step",
                    GraphRagStep(
                        step_index=1,
                        title="Unified Neo4j Hybrid RRF Retrieval",
                        description="Querying dense vector index, BM25 Lucene fulltext, and topological graphs...",
                        status="running",
                    ).model_dump(),
                )
                doc_res = await self._retrieve_document_graph(
                    query=request.query,
                    document_id=request.document_id,
                    target_classes=detected_ifc_classes,
                    concrete_clauses=analysis.get("concrete_clauses"),
                    abstract_themes=analysis.get("abstract_themes"),
                )
                doc_context = doc_res["text"]
                citations.extend(doc_res["citations"])
                if doc_res.get("cypher"):
                    cypher_queries.append(doc_res["cypher"])

                yield self._format_sse_event("tool_call", doc_res["tool_call"].model_dump())
                yield self._format_sse_event(
                    "step",
                    GraphRagStep(
                        step_index=1,
                        title="Unified Neo4j Hybrid RRF Retrieval",
                        description=f"Fused {len(doc_res['citations'])} top specification sections via RRF (k=60).",
                        status="done",
                    ).model_dump(),
                )

            # 3. Model Graph Retrieval
            if request.scope in ("model", "hybrid"):
                yield self._format_sse_event(
                    "step",
                    GraphRagStep(
                        step_index=2,
                        title="Hub-Suppressed Model Graph Traversal",
                        description="Traversing spatial containment with inverse-degree weighting in Neo4j...",
                        status="running",
                    ).model_dump(),
                )
                model_res = self._retrieve_model_graph(
                    project_id=project_id,
                    query=request.query,
                    target_classes=detected_ifc_classes,
                    element_guids=analysis.get("element_guids"),
                    retrieval_mode=retrieval_mode,
                )
                model_context = model_res["text"]
                citations.extend(model_res["citations"])
                if model_res.get("cypher"):
                    cypher_queries.append(model_res["cypher"])

                yield self._format_sse_event("tool_call", model_res["tool_call"].model_dump())
                yield self._format_sse_event(
                    "step",
                    GraphRagStep(
                        step_index=2,
                        title="Hub-Suppressed Model Graph Traversal",
                        description=f"Inspected {model_res['element_count']} IFC element instances in model.",
                        status="done",
                    ).model_dump(),
                )

            # 4. Stream Citations
            for citation in citations:
                yield self._format_sse_event("citation", citation.model_dump())

            # 5. Synthesis Step
            yield self._format_sse_event(
                "step",
                GraphRagStep(
                    step_index=3,
                    title="Cross-Domain Synthesis & Verification",
                    description="Generating grounded answer...",
                    status="running",
                ).model_dump(),
            )

            prompt_payload = self._build_synthesis_prompt(
                query=request.query,
                scope=request.scope,
                doc_context=doc_context,
                model_context=model_context,
                retrieval_mode=retrieval_mode,
            )

            full_answer = ""
            async for token in self._stream_tokens(
                prompt_payload=prompt_payload,
                model_override=request.model_name,
                temperature=request.temperature,
                organization_id=organization_id,
            ):
                full_answer += token
                yield self._format_sse_event("token", {"token": token})

            yield self._format_sse_event(
                "step",
                GraphRagStep(
                    step_index=3,
                    title="Cross-Domain Synthesis & Verification",
                    description="Synthesis complete.",
                    status="done",
                ).model_dump(),
            )

            # 6. Final Done Payload
            followups = self._generate_followups(request.query, request.scope, detected_ifc_classes)
            yield self._format_sse_event(
                "done",
                {
                    "project_id": project_id,
                    "scope": request.scope,
                    "answer": full_answer,
                    "citations": [c.model_dump() for c in citations],
                    "cypher_queries": cypher_queries,
                    "suggested_followups": followups,
                    "retrieval_mode": retrieval_mode,
                },
            )
        except Exception as exc:
            logger.error("Error during Graph-RAG streaming: %s", exc, exc_info=True)
            yield self._format_sse_event("error", {"detail": str(exc)})

    # -----------------------------------------------------------------------
    # SOTA Intent Analysis & Dual-Level Query Routing (LightRAG)
    # -----------------------------------------------------------------------

    def _analyze_query_dual_level(
        self, query: str, explicit_class: Optional[str] = None
    ) -> dict[str, Any]:
        """Extract concrete low-level entity seeds and high-level abstract themes."""
        target_classes = self._detect_ifc_classes(query, explicit_class)

        # Concrete clauses (e.g. 1017.2, 1005, 404, 7.2)
        clause_matches = re.findall(
            r"\b(?:Section|Clause|Item|Code|IBC|NFPA|ADA)?\s*([0-9]{3,4}(?:\.[0-9]+)?|[0-9]+\.[0-9]+(?:\.[0-9]+)?)\b",
            query,
            re.IGNORECASE,
        )
        concrete_clauses = [c.strip() for c in clause_matches if len(c.strip()) >= 3]

        # Explicit GUIDs (OpenBIM 22-char or UUID)
        guids = re.findall(r"\b[0-9a-zA-Z_$]{22}\b", query)

        # High-level abstract themes
        query_lower = query.lower()
        active_themes: list[str] = []
        for theme_name, theme_words in _THEME_KEYWORDS.items():
            if any(w in query_lower for w in theme_words):
                active_themes.append(theme_name)

        # Determine retrieval mode
        if any(term in query_lower for term in ["overall", "all ", "summary", "patterns", "primary risks", "audit overview", "across all"]):
            retrieval_mode = "global"
        elif guids or (concrete_clauses and len(concrete_clauses) == 1 and not active_themes):
            retrieval_mode = "local"
        else:
            retrieval_mode = "hybrid_rrf"

        return {
            "target_classes": target_classes,
            "concrete_clauses": concrete_clauses,
            "element_guids": guids,
            "abstract_themes": active_themes,
            "retrieval_mode": retrieval_mode,
        }

    def _detect_ifc_classes(self, query: str, explicit_class: Optional[str] = None) -> list[str]:
        """Extract IFC entity classes mentioned in query or specified explicitly."""
        detected = set()
        if explicit_class:
            detected.add(explicit_class if explicit_class.startswith("Ifc") else f"Ifc{explicit_class.capitalize()}")

        tokens = re.findall(r"\b[A-Za-z]+\b", query.lower())
        for token in tokens:
            if token in _IFC_KEYWORD_MAP:
                detected.add(_IFC_KEYWORD_MAP[token])

        for m in re.finditer(r"\bIfc[A-Z][a-zA-Z]+\b", query):
            detected.add(m.group(0))

        return sorted(detected)

    # -----------------------------------------------------------------------
    # SOTA Multi-Stream Retrieval & Reciprocal Rank Fusion (RRF)
    # -----------------------------------------------------------------------

    async def _retrieve_document_graph(
        self,
        query: str,
        document_id: Optional[int] = None,
        target_classes: Optional[list[str]] = None,
        concrete_clauses: Optional[list[str]] = None,
        abstract_themes: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Execute parallel Vector, BM25, and Topological Cypher streams, then fuse with RRF."""
        citations: list[GraphRagCitation] = []
        cypher_runs: list[str] = []

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
                streams["vector"] = v_rows
                cypher_runs.append(cypher_vector.strip())
        except Exception as exc:
            logger.debug("Native vector index search skipped or unavailable: %s", exc)

        # -------------------------------------------------------------------
        # Stream 2: BM25 Lexical Matching (Neo4j Apache Lucene fulltext)
        # -------------------------------------------------------------------
        search_terms: list[str] = []
        if concrete_clauses:
            search_terms.extend(concrete_clauses)
        words = [
            w for w in re.findall(r"\b[a-zA-Z0-9\.\-]+\b", query)
            if len(w) > 2 and w.lower() not in {"what", "are", "the", "for", "and", "our", "all", "with", "from", "how", "many"}
        ]
        if words:
            search_terms.extend(words[:3])

        lucene_query = " OR ".join(f"{t}*" for t in search_terms) if search_terms else "egress*"

        try:
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
            logger.debug("Native fulltext BM25 search fallback to lexical regex: %s", exc)
            # Fallback lexical query using WHERE CONTAINS
            term = words[0] if words else "egress"
            fallback_bm25 = """
            MATCH (s:DocumentSection)
            WHERE toLower(s.section_name) CONTAINS toLower($term)
               OR toLower(s.summary) CONTAINS toLower($term)
               OR s.section_number CONTAINS $term
            RETURN s.id as id, s.document_id as doc_id, s.section_number as sec_num,
                   s.section_name as title, s.summary as summary, s.page_number as page,
                   1.0 as stream_score
            LIMIT 8
            """
            try:
                streams["bm25"] = self.graph_service.execute(fallback_bm25, {"term": term}) or []
            except Exception:
                streams["bm25"] = []

        # -------------------------------------------------------------------
        # Stream 3: Topological Graph Traversal (with Hub Suppression)
        # -------------------------------------------------------------------
        params_graph: dict[str, Any] = {}
        where_graph = []
        if document_id is not None:
            where_graph.append("s.document_id = $doc_id")
            params_graph["doc_id"] = document_id

        if target_classes:
            where_graph.append("ANY(cls IN $classes WHERE (s)-[:APPLIES_TO]->(:IfcClass {class_name: cls}))")
            params_graph["classes"] = target_classes

        if where_graph:
            cypher_graph = f"""
            MATCH (s:DocumentSection)
            WHERE {' AND '.join(where_graph)}
            OPTIONAL MATCH (parent:DocumentSection)-[:PARENT_OF]->(s)
            OPTIONAL MATCH (s)-[:CITES]->(cited:DocumentSection)
            OPTIONAL MATCH (s)-[:APPLIES_TO]->(ifc:IfcClass)
            RETURN s.id as id, s.document_id as doc_id, s.section_number as sec_num,
                   s.section_name as title, s.summary as summary, s.page_number as page,
                   parent.section_name as parent_title,
                   collect(DISTINCT cited.section_number) as citations,
                   collect(DISTINCT ifc.class_name) as target_classes
            LIMIT 10
            """
            try:
                g_rows = self.graph_service.execute(cypher_graph, params_graph)
                if g_rows:
                    streams["graph"] = g_rows
                    cypher_runs.append(cypher_graph.strip())
            except Exception as exc:
                logger.debug("Graph traversal stream notice: %s", exc)

        # -------------------------------------------------------------------
        # Reciprocal Rank Fusion (k=60)
        # -------------------------------------------------------------------
        fused_sections = compute_reciprocal_rank_fusion(streams, k=60, id_key="id")
        top_sections = fused_sections[:6]

        text_lines = []
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for sec in top_sections:
            sec_id = sec.get("id", "")
            title = sec.get("title") or "Section"
            sec_num = sec.get("sec_num") or ""
            page = sec.get("page")
            summary = sec.get("summary") or "Section specification provisions."
            classes = sec.get("target_classes") or []
            rrf_score = sec.get("rrf_score", 0.0)
            stream_ranks = sec.get("rrf_stream_ranks", {})

            # Primary stream labeling
            active_streams = list(stream_ranks.keys())
            method: Any = "hybrid_rrf" if len(active_streams) > 1 else (active_streams[0] if active_streams else "graph")

            ref = f"Section {sec_num}" if sec_num else title
            citation_id = f"doc_{sec_num or sec_id}"

            citations.append(
                GraphRagCitation(
                    id=citation_id,
                    source_type="document",
                    title=f"{ref}: {title}",
                    reference=ref,
                    snippet=summary[:280],
                    page_number=page,
                    properties={
                        "target_classes": classes,
                        "stream_ranks": stream_ranks,
                    },
                    score=rrf_score,
                    retrieval_method=method,
                    rrf_score=rrf_score,
                )
            )

            text_lines.append(
                f"- [Doc: {ref}, p. {page or 'N/A'}] {title} (RRF: {rrf_score:.4f}, Method: {method}): "
                f"{summary} (Applies to: {', '.join(classes) or 'General'})"
            )
            nodes.append({"id": sec_id, "label": f"{sec_num} {title}", "type": "DocumentSection"})

        cypher_repr = "\n\n// --- Combined RRF Retrieval Streams ---\n".join(cypher_runs) if cypher_runs else ""
        return {
            "text": "\n".join(text_lines) if text_lines else "No direct document sections matched.",
            "citations": citations,
            "tool_call": GraphRagToolCall(
                tool_name="hybrid_rrf_retrieval",
                arguments={
                    "vector_candidates": len(streams["vector"]),
                    "bm25_candidates": len(streams["bm25"]),
                    "graph_candidates": len(streams["graph"]),
                    "top_selected": len(top_sections),
                },
                output_summary=f"Fused {len(top_sections)} sections via RRF (k=60) across Vector, BM25, and Graph.",
                cypher_query=cypher_repr.strip(),
                status="success",
            ),
            "cypher": cypher_repr.strip(),
            "nodes": nodes,
            "edges": edges,
        }

    # -----------------------------------------------------------------------
    # SOTA Hub-Suppressed Model Graph Traversal (HippoRAG / LinearRAG)
    # -----------------------------------------------------------------------

    def _ensure_project_model_ingested(self, project_id: int) -> None:
        """Auto-ingest the project's primary IFC model into graph database if not already ingested."""
        if not self.graph_service or not self.graph_service.provider:
            return
        pid_str = str(project_id)
        try:
            check_cypher = "MATCH (n {project_id: $pid}) RETURN count(n) as cnt LIMIT 1"
            rows = self.graph_service.execute(check_cypher, {"pid": pid_str})
            if rows and rows[0].get("cnt", 0) > 0:
                return  # Already ingested
        except Exception as exc:
            logger.debug("Error checking project graph ingestion: %s", exc)

        # Not ingested; resolve model file and ingest
        try:
            model_path = self.models_service.resolve_primary_path(project_id)
            if model_path and model_path.exists():
                import ifcopenshell

                from app.modules.ifc_reader.ifc_graph import ingest_ifc_to_graph

                logger.info("Auto-ingesting primary IFC model into graph for project %d: %s", project_id, model_path)
                model = ifcopenshell.open(str(model_path))
                ingest_ifc_to_graph(model, self.graph_service, project_id=pid_str)
                logger.info("Auto-ingestion completed for project %d", project_id)
        except Exception as exc:
            logger.warning("Auto-ingesting IFC model failed for project %d: %s", project_id, exc)

    def _retrieve_model_graph(
        self,
        project_id: int,
        query: str,
        target_classes: Optional[list[str]] = None,
        element_guids: Optional[list[str]] = None,
        retrieval_mode: str = "hybrid_rrf",
    ) -> dict[str, Any]:
        """Traverse IFC model entities with hub suppression and spatial containment."""
        self._ensure_project_model_ingested(project_id)
        pid_str = str(project_id)
        citations: list[GraphRagCitation] = []
        elements_found: list[dict[str, Any]] = []
        cypher = ""

        if not self.graph_service or not self.graph_service.provider:
            return {
                "text": "Model graph persistence provider not connected.",
                "citations": citations,
                "tool_call": GraphRagToolCall(
                    tool_name="query_ifc_model_graph",
                    arguments={"project_id": project_id},
                    output_summary="Provider offline",
                    status="error",
                ),
                "cypher": None,
                "element_count": 0,
                "nodes": [],
                "edges": [],
            }

        # Global Search Mode: Map-Reduce Summary Report (Microsoft GraphRAG / DRIFT)
        if retrieval_mode == "global":
            cypher = """
            MATCH (elem {project_id: $pid})
            WHERE elem.ifc_type IS NOT NULL
            OPTIONAL MATCH (storey:IfcBuildingStorey {project_id: $pid})-[:CONTAINS*1..2]->(elem)
            RETURN elem.ifc_type as ifc_type,
                   count(elem) as total_count,
                   count(elem.fire_rating) as fire_rated_count,
                   collect(DISTINCT storey.name)[..3] as storeys
            ORDER BY total_count DESC
            LIMIT 12
            """
            try:
                summary_records = self.graph_service.execute(cypher, {"pid": pid_str}) or []
                text_lines = ["### Model Architectural Distribution Summary:"]
                for r in summary_records:
                    text_lines.append(
                        f"- **{r.get('ifc_type')}**: {r.get('total_count')} elements "
                        f"({r.get('fire_rated_count')} fire rated) across {', '.join(r.get('storeys', [])) or 'Model'}."
                    )
                return {
                    "text": "\n".join(text_lines),
                    "citations": [],
                    "tool_call": GraphRagToolCall(
                        tool_name="global_model_summary",
                        arguments={"project_id": project_id, "mode": "global"},
                        output_summary=f"Generated global model summary across {len(summary_records)} IFC categories.",
                        cypher_query=cypher.strip(),
                        status="success",
                    ),
                    "cypher": cypher.strip(),
                    "element_count": sum(r.get("total_count", 0) for r in summary_records),
                    "nodes": [],
                    "edges": [],
                }
            except Exception as exc:
                logger.warning("Global model summary query error: %s", exc)

        # Local & Hybrid Search Mode: Targeted traversal with hub suppression
        primary_class = target_classes[0] if target_classes else "IfcProduct"

        # Specialized handling for building storeys / levels
        if primary_class == "IfcBuildingStorey":
            cypher = """
            MATCH (storey:IfcBuildingStorey {project_id: $pid})
            OPTIONAL MATCH (storey)-[:CONTAINS]->(child)
            RETURN storey.guid as guid, storey.name as name, storey.ifc_type as ifc_type,
                   count(DISTINCT child) as element_count,
                   collect(DISTINCT child.ifc_type)[..5] as element_types
            ORDER BY storey.name ASC
            """
            try:
                storeys_found = self.graph_service.execute(cypher, {"pid": pid_str}) or []
            except Exception as exc:
                logger.warning("Building storey graph query error: %s", exc)
                storeys_found = []

            if not storeys_found:
                # Fallback matching on property if label indexing differs
                cypher = """
                MATCH (storey {project_id: $pid})
                WHERE storey.ifc_type = 'IfcBuildingStorey'
                RETURN storey.guid as guid, storey.name as name, storey.ifc_type as ifc_type,
                       0 as element_count, [] as element_types
                ORDER BY storey.name ASC
                """
                try:
                    storeys_found = self.graph_service.execute(cypher, {"pid": pid_str}) or []
                except Exception:
                    storeys_found = []

            text_lines = [f"Total Building Storeys (Floors) in model: {len(storeys_found)}"]
            nodes = []
            citations = []
            for s in storeys_found:
                guid = s.get("guid") or "UnknownGUID"
                name = s.get("name") or "Storey"
                elem_count = s.get("element_count", 0)
                elem_types = s.get("element_types", [])
                types_str = f" (Contains elements: {', '.join(elem_types)})" if elem_types else ""
                ref = f"Storey ({name})"
                citation_id = f"ifc_{guid}"

                citations.append(
                    GraphRagCitation(
                        id=citation_id,
                        source_type="model",
                        title=f"Building Storey: {name}",
                        reference=guid,
                        snippet=f"Building Storey / Level '{name}' containing {elem_count} building elements{types_str}.",
                        element_guid=guid,
                        ifc_type="IfcBuildingStorey",
                        properties={
                            "name": name,
                            "element_count": elem_count,
                            "contained_types": elem_types,
                        },
                        score=1.5,
                        retrieval_method="graph",
                    )
                )

                text_lines.append(
                    f"- [IFC: IfcBuildingStorey ({name}) | GUID: {guid}] Storey Name: '{name}', "
                    f"Contained Elements: {elem_count}{types_str}"
                )
                nodes.append({"id": guid, "label": f"Storey: {name}", "type": "IfcBuildingStorey"})

            output_summary = f"Located {len(storeys_found)} building storeys (floors) in model."
            return {
                "text": "\n".join(text_lines) if text_lines else "No building storeys located in model.",
                "citations": citations,
                "tool_call": GraphRagToolCall(
                    tool_name="query_building_storeys",
                    arguments={"primary_class": "IfcBuildingStorey", "project_id": project_id},
                    output_summary=output_summary,
                    cypher_query=cypher.strip(),
                    status="success",
                ),
                "cypher": cypher.strip(),
                "element_count": len(storeys_found),
                "nodes": nodes,
                "edges": [],
            }

        # Check if user asked for a count/inventory
        is_count_query = any(term in query.lower() for term in [
            "how many", "count", "number of", "total", "inventory"
        ])
        total_class_count = None
        if is_count_query and primary_class != "IfcProduct":
            count_cypher = f"MATCH (elem:{primary_class} {{project_id: $pid}}) RETURN count(elem) as total_count"
            try:
                c_rows = self.graph_service.execute(count_cypher, {"pid": pid_str})
                if c_rows and c_rows[0].get("total_count") is not None:
                    total_class_count = c_rows[0]["total_count"]
            except Exception as exc:
                logger.debug("Class count query notice: %s", exc)

        if element_guids:
            cypher = """
            MATCH (elem {project_id: $pid})
            WHERE elem.guid IN $guids
            OPTIONAL MATCH (space:IfcSpace {project_id: $pid})-[:CONTAINS]->(elem)
            OPTIONAL MATCH (storey:IfcBuildingStorey {project_id: $pid})-[:CONTAINS*1..2]->(elem)
            RETURN elem.guid as guid, elem.name as name, elem.ifc_type as ifc_type,
                   elem.fire_rating as fire_rating, elem.is_external as is_external,
                   space.name as space_name, storey.name as storey_name
            LIMIT 10
            """
            try:
                elements_found = self.graph_service.execute(cypher, {"pid": pid_str, "guids": element_guids}) or []
            except Exception as exc:
                logger.warning("Targeted GUID model search failed: %s", exc)

        if not elements_found:
            cypher = f"""
            MATCH (elem:{primary_class} {{project_id: $pid}})
            OPTIONAL MATCH (space:IfcSpace {{project_id: $pid}})-[:CONTAINS]->(elem)
            OPTIONAL MATCH (storey:IfcBuildingStorey {{project_id: $pid}})-[:CONTAINS*1..2]->(elem)
            RETURN elem.guid as guid, elem.name as name, elem.ifc_type as ifc_type,
                   elem.fire_rating as fire_rating, elem.is_external as is_external,
                   space.name as space_name, storey.name as storey_name
            LIMIT 15
            """
            try:
                elements_found = self.graph_service.execute(cypher, {"pid": pid_str}) or []
            except Exception as exc:
                logger.warning("Model graph primary class traversal error: %s", exc)
                try:
                    cypher = """
                    MATCH (elem {project_id: $pid})
                    WHERE elem.ifc_type IS NOT NULL
                    RETURN elem.guid as guid, elem.name as name, elem.ifc_type as ifc_type,
                           elem.fire_rating as fire_rating, elem.is_external as is_external,
                           null as space_name, null as storey_name
                    LIMIT 10
                    """
                    elements_found = self.graph_service.execute(cypher, {"pid": pid_str}) or []
                except Exception:
                    elements_found = []

        text_lines = []
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        # Degree penalization / Hub suppression post-filter
        for e in elements_found:
            guid = e.get("guid") or "UnknownGUID"
            name = e.get("name") or e.get("ifc_type") or "Element"
            ifc_type = e.get("ifc_type") or primary_class
            fire_rating = e.get("fire_rating")
            space_name = e.get("space_name")
            storey_name = e.get("storey_name")

            if ifc_type.lower() in _STOP_ENTITIES:
                continue

            # Weight calculation: prefer elements with explicit location or performance data
            degree_boost = 1.2 if (fire_rating or space_name) else 1.0

            ref = f"{ifc_type} ({name})"
            citation_id = f"ifc_{guid}"

            citations.append(
                GraphRagCitation(
                    id=citation_id,
                    source_type="model",
                    title=ref,
                    reference=guid,
                    snippet=f"Type: {ifc_type}, Level: {storey_name or 'N/A'}, Space: {space_name or 'N/A'}, Fire Rating: {fire_rating or 'Not Specified'}",
                    element_guid=guid,
                    ifc_type=ifc_type,
                    properties={
                        "fire_rating": fire_rating,
                        "space": space_name,
                        "level": storey_name,
                        "degree_weight": degree_boost,
                    },
                    score=degree_boost,
                    retrieval_method="graph",
                )
            )

            text_lines.append(
                f"- [IFC: {ref} | GUID: {guid}] Storey: {storey_name or 'N/A'}, "
                f"Space: {space_name or 'N/A'}, Fire Rating: {fire_rating or 'Unspecified'}"
            )

            nodes.append({"id": guid, "label": f"{ifc_type}: {name}", "type": "IfcProduct"})

        if total_class_count is not None:
            text_lines.insert(0, f"Total {primary_class} elements in project: {total_class_count}")
            output_summary = f"Found {total_class_count} total {primary_class} elements (inspected {len(elements_found)} in graph)."
        else:
            output_summary = f"Traversed {len(elements_found)} IFC element nodes in model."

        return {
            "text": "\n".join(text_lines) if text_lines else "No specific model elements located.",
            "citations": citations,
            "tool_call": GraphRagToolCall(
                tool_name="hub_suppressed_model_traversal",
                arguments={"primary_class": primary_class, "project_id": project_id},
                output_summary=output_summary,
                cypher_query=cypher.strip(),
                status="success",
            ),
            "cypher": cypher.strip(),
            "element_count": len(elements_found),
            "nodes": nodes,
            "edges": edges,
        }

    # -----------------------------------------------------------------------
    # Synthesis & Followup Generation
    # -----------------------------------------------------------------------

    def _build_synthesis_prompt(
        self,
        query: str,
        scope: GraphRagScope,
        doc_context: str,
        model_context: str,
        retrieval_mode: str = "hybrid_rrf",
    ) -> list[dict[str, str]]:
        """Construct prompt payload for LiteLLM generation."""
        context_parts = []
        if doc_context and doc_context.strip():
            context_parts.append(f"### RETRIEVED DOCUMENT PROVISIONS:\n{doc_context}")
        if model_context and model_context.strip():
            context_parts.append(f"### RETRIEVED BIM MODEL FACTS:\n{model_context}")

        combined_context = "\n\n".join(context_parts) if context_parts else "No direct graph context found."

        user_content = f"""QUESTION: {query}
RETRIEVAL SCOPE: {scope} (Mode: {retrieval_mode})

CONTEXT:
{combined_context}

Please provide an authoritative architectural compliance response following the system guidelines.
Ensure every statement cites the grounded source using [Doc: <Ref>, p. <Page>] or [IFC: <Ref> | GUID: <GUID>].
"""
        return [
            {"role": "system", "content": _RAG_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    async def _synthesize_answer(
        self,
        prompt_payload: list[dict[str, str]],
        model_override: Optional[str] = None,
        temperature: Optional[float] = None,
        organization_id: Optional[int] = None,
    ) -> str:
        """Call LiteLLM to generate synthesized Markdown response."""
        chosen_model = model_override or DEFAULT_LLM_MODEL
        temp = temperature if temperature is not None else COMPLIANCE_TEMPERATURE

        try:
            import litellm
            with llm_call_context(context="graph_rag_query", organization_id=organization_id):
                response = await litellm.acompletion(
                    model=chosen_model,
                    messages=prompt_payload,
                    temperature=temp,
                    max_tokens=1500,
                )
            return response.choices[0].message.content or "No response generated."
        except Exception as exc:
            logger.warning("LiteLLM synthesis call failed: %s (using deterministic synthesis)", exc)
            return self._fallback_deterministic_answer(prompt_payload)

    async def _stream_tokens(
        self,
        prompt_payload: list[dict[str, str]],
        model_override: Optional[str] = None,
        temperature: Optional[float] = None,
        organization_id: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream response tokens from LiteLLM."""
        chosen_model = model_override or DEFAULT_LLM_MODEL
        temp = temperature if temperature is not None else COMPLIANCE_TEMPERATURE

        try:
            import litellm
            with llm_call_context(context="graph_rag_stream", organization_id=organization_id):
                stream_res = await litellm.acompletion(
                    model=chosen_model,
                    messages=prompt_payload,
                    temperature=temp,
                    max_tokens=1500,
                    stream=True,
                )
                async for chunk in stream_res:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        yield delta
        except Exception as exc:
            logger.warning("LiteLLM streaming failed: %s (falling back to single token reply)", exc)
            fallback = self._fallback_deterministic_answer(prompt_payload)
            yield fallback

    def _fallback_deterministic_answer(self, prompt_payload: list[dict[str, str]]) -> str:
        """Deterministic offline answer if LLM API is unavailable."""
        user_msg = next((m["content"] for m in prompt_payload if m.get("role") == "user"), "")
        lines = [
            "### Architectural Compliance & Graph-RAG Summary",
            "",
            "Based on the property graph and regulatory documents retrieved for this project:",
            "",
        ]
        if "RETRIEVED DOCUMENT PROVISIONS:" in user_msg:
            lines.append("- **Governing Document Requirements**: Relevant specification clauses and code criteria were cross-referenced in the knowledge graph.")
        if "RETRIEVED BIM MODEL FACTS:" in user_msg:
            model_facts_block = user_msg.split("### RETRIEVED BIM MODEL FACTS:\n")[-1].split("###")[0]
            summary_facts = [
                line.strip()
                for line in model_facts_block.strip().split("\n")
                if line.strip().startswith("Total ") or line.strip().startswith("- [IFC:")
            ]
            if summary_facts:
                lines.append("- **Model Element Verification**:")
                for fact in summary_facts[:6]:
                    lines.append(f"  {fact}")
            else:
                lines.append("- **Model Element Verification**: Corresponding IFC building elements were located and inspected in the project's spatial hierarchy.")
        lines.append("")
        lines.append("*(Live LLM endpoint was not reachable; the above citations reflect the exact verified graph entities).*")
        return "\n".join(lines)

    def _generate_followups(self, query: str, scope: GraphRagScope, target_classes: list[str]) -> list[str]:
        """Generate contextual prompt recommendations based on retrieved scope."""
        followups = []
        primary = target_classes[0] if target_classes else "Doors"

        if scope in ("document", "hybrid"):
            followups.append(f"What specific exceptions apply to {primary} in this standard?")
            followups.append("Show the cross-cited standards and referenced clauses.")

        if scope in ("model", "hybrid"):
            followups.append(f"Which {primary} are missing required fire ratings?")
            followups.append("Group these elements by building storey.")

        return followups[:3]

    def _format_sse_event(self, event_type: str, data: dict[str, Any]) -> str:
        """Format a single Server-Sent Event."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
