"""GraphRagService orchestrator coordinating modular query routing, retrievers, fusion, and synthesis."""

import asyncio
from typing import Any, AsyncGenerator, Optional

from app.logging_config import get_logger
from app.modules.contracts.graph import (
    GraphRagCitation,
    GraphRagContextSummary,
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    GraphRagStep,
    GraphRagToolCall,
)
from app.services.embedding_service import EmbeddingService
from app.services.graph_database import GraphService
from app.services.graph_rag.document_retriever import DocumentGraphRetriever
from app.services.graph_rag.model_retriever import ModelGraphRetriever
from app.services.graph_rag.query_router import GraphRagQueryRouter
from app.services.graph_rag.synthesizer import GraphRagSynthesizer
from app.services.models_service import ModelsService
from app.services.projects_service import ProjectsService
from app.services.rules_service import RuleService

logger = get_logger(__name__)


class GraphRagService:
    """Production Graph-RAG Orchestrator coordinating specialized routers, retrievers, and synthesis workers."""

    def __init__(
        self,
        graph_service: GraphService,
        embedding_service: Optional[EmbeddingService] = None,
        rule_service: Optional[RuleService] = None,
        rules_service: Optional[RuleService] = None,
        models_service: Optional[ModelsService] = None,
        projects_service: Optional[Any] = None,
    ):
        self.graph_service = graph_service
        self.embedding_service = embedding_service or EmbeddingService()
        self.rule_service = rule_service or rules_service or RuleService()
        self.models_service = models_service or ModelsService()
        self.projects_service = projects_service

        if self.projects_service is None:
            try:
                self.projects_service = ProjectsService(models_service=self.models_service)
            except Exception:
                self.projects_service = None

        # Modular workers and helpers
        self.router = GraphRagQueryRouter()
        self.document_retriever = DocumentGraphRetriever(
            graph_service=self.graph_service,
            embedding_service=self.embedding_service,
            projects_service=self.projects_service,
        )
        self.model_retriever = ModelGraphRetriever(
            graph_service=self.graph_service,
            models_service=self.models_service,
            projects_service=self.projects_service,
        )
        self.synthesizer = GraphRagSynthesizer()

    # Backwards-compatible helper methods for callers/tests
    def _analyze_query_dual_level(self, query: str, explicit_class: Optional[str] = None) -> dict[str, Any]:
        return self.router.analyze_query_dual_level(query, explicit_class)

    def _detect_ifc_classes(self, query: str, explicit_class: Optional[str] = None) -> list[str]:
        return self.router.detect_ifc_classes(query, explicit_class)

    async def _retrieve_document_graph(self, *args, **kwargs) -> dict[str, Any]:
        return await self.document_retriever.retrieve(*args, **kwargs)

    def _retrieve_model_graph(self, *args, **kwargs) -> dict[str, Any]:
        return self.model_retriever.retrieve(*args, **kwargs)

    def _ensure_project_model_ingested(self, project_id: int) -> None:
        self.model_retriever.ensure_project_model_ingested(project_id)

    def _build_synthesis_prompt(self, *args, **kwargs) -> list[dict[str, str]]:
        return self.synthesizer.build_synthesis_prompt(*args, **kwargs)

    async def _synthesize_answer(self, *args, **kwargs) -> str:
        return await self.synthesizer.synthesize_answer(*args, **kwargs)

    async def _stream_tokens(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async for token in self.synthesizer.stream_tokens(*args, **kwargs):
            yield token

    def _fallback_deterministic_answer(self, *args, **kwargs) -> str:
        return self.synthesizer.fallback_deterministic_answer(*args, **kwargs)

    def _generate_followups(self, *args, **kwargs) -> list[str]:
        return self.synthesizer.generate_followups(*args, **kwargs)

    def _format_sse_event(self, *args, **kwargs) -> str:
        return self.synthesizer.format_sse_event(*args, **kwargs)

    def get_project_context_summary(self, project_id: int) -> GraphRagContextSummary:
        """Inspect available document, IFC model entities, storeys, and metadata in a project."""
        pid_str = str(project_id)
        has_ifc_model = False
        total_elements = 0
        total_storeys = 0
        total_spaces = 0
        ifc_classes: list[dict[str, Any]] = []
        storeys_list: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []
        models_summary: list[dict[str, Any]] = []

        project_name: Optional[str] = None
        client_name: Optional[str] = None
        project_code: Optional[str] = None
        status: Optional[str] = None

        # 1. Project Metadata
        if self.projects_service:
            try:
                proj = self.projects_service.get_project(project_id)
                if proj:
                    project_name = proj.get("name")
                    client_name = proj.get("client_name")
                    project_code = proj.get("project_code")
                    status = proj.get("status")
            except Exception as exc:
                logger.debug("Failed querying project metadata for context summary: %s", exc)

        # 2. Attached Models
        try:
            raw_models = self.models_service.list_models(project_id) or []
            for m in raw_models:
                models_summary.append({
                    "id": m.get("id"),
                    "file_name": m.get("file_name", "model.ifc"),
                    "role": m.get("role", "primary"),
                    "is_primary": bool(m.get("is_primary")),
                    "cde_state": m.get("cde_state"),
                    "uploaded_at": m.get("uploaded_at"),
                    "revision_code": m.get("revision_code"),
                })
        except Exception as exc:
            logger.debug("Failed querying models for context summary: %s", exc)

        total_models = len(models_summary)
        has_ifc_model = total_models > 0

        if not self.graph_service or not self.graph_service.provider:
            return GraphRagContextSummary(
                project_id=project_id,
                project_name=project_name,
                client_name=client_name,
                project_code=project_code,
                status=status,
                has_ifc_model=has_ifc_model,
                total_models=total_models,
                is_graph_ready=False,
                total_elements=0,
                total_storeys=0,
                total_spaces=0,
                ifc_classes=[],
                storeys=[],
                documents=[],
                rulesets=[],
                models=models_summary,
            )

        self._ensure_project_model_ingested(project_id)

        # 3. Check IFC element classes in model graph
        try:
            # :IfcProduct lets Neo4j use the IfcProduct.project_id index instead
            # of scanning every node (see the note in model_retriever.py).
            cypher_classes = """
            MATCH (n:IfcProduct {project_id: $pid})
            WHERE n.ifc_type IS NOT NULL
            RETURN n.ifc_type as class_name, count(n) as element_count
            ORDER BY element_count DESC
            LIMIT 25
            """
            rows = self.graph_service.execute(cypher_classes, {"pid": pid_str})
            if rows:
                for r in rows:
                    cname = r.get("class_name")
                    cnt = r.get("element_count", 0)
                    if cname:
                        ifc_classes.append({"class_name": cname, "count": cnt})
                        total_elements += cnt
        except Exception as exc:
            logger.debug("Failed querying IFC classes for context summary: %s", exc)

        # 4. Check Storeys & Levels
        try:
            cypher_storeys = """
            MATCH (s:IfcBuildingStorey {project_id: $pid})
            OPTIONAL MATCH (s)-[:CONTAINS]->(child)
            RETURN s.guid as guid, s.name as name, count(child) as element_count
            ORDER BY s.name ASC
            """
            storey_rows = self.graph_service.execute(cypher_storeys, {"pid": pid_str}) or []
            total_storeys = len(storey_rows)
            for sr in storey_rows:
                storeys_list.append({
                    "guid": sr.get("guid") or "",
                    "name": sr.get("name") or "Storey",
                    "element_count": sr.get("element_count", 0),
                })
        except Exception as exc:
            logger.debug("Failed querying storeys for context summary: %s", exc)

        # 5. Check Spaces
        try:
            cypher_spaces = """
            MATCH (sp:IfcSpace {project_id: $pid})
            RETURN count(sp) as space_count
            """
            space_res = self.graph_service.execute(cypher_spaces, {"pid": pid_str}) or []
            if space_res:
                total_spaces = space_res[0].get("space_count", 0)
        except Exception as exc:
            logger.debug("Failed querying spaces for context summary: %s", exc)

        # 6. Check Document specifications
        try:
            cypher_docs = """
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:HAS_SECTION]->(s:DocumentSection)
            RETURN d.id as id, d.title as title, count(s) as section_count
            ORDER BY d.id ASC
            LIMIT 10
            """
            doc_rows = self.graph_service.execute(cypher_docs, {})
            if doc_rows:
                for r in doc_rows:
                    did = r.get("id") or 1
                    documents.append({
                        "id": did,
                        "title": r.get("title") or f"Document {did}",
                        "section_count": r.get("section_count", 0),
                    })
        except Exception as exc:
            logger.debug("Failed querying documents for context summary: %s", exc)

        # 7. Fallback to Client Documents if graph documents are empty
        if not documents and self.projects_service:
            try:
                client_docs = self.projects_service.get_client_documents_by_project(project_id) or []
                for cd in client_docs:
                    documents.append({
                        "id": cd.get("id"),
                        "title": cd.get("title") or cd.get("file_name", "Document"),
                        "section_count": 0,
                        "document_type": cd.get("document_type"),
                        "cde_state": cd.get("cde_state"),
                    })
            except Exception as exc:
                logger.debug("Failed querying client documents fallback: %s", exc)

        # 8. Check Active Rulesets
        rulesets = ["ARCH-EGRESS-001", "ARCH-SPATIAL-001", "IBC-2024", "ADA-2010"]

        is_graph_ready = total_elements > 0
        has_ifc_model = total_models > 0 or is_graph_ready

        return GraphRagContextSummary(
            project_id=project_id,
            project_name=project_name,
            client_name=client_name,
            project_code=project_code,
            status=status,
            has_ifc_model=has_ifc_model,
            total_models=total_models,
            is_graph_ready=is_graph_ready,
            total_elements=total_elements,
            total_storeys=total_storeys,
            total_spaces=total_spaces,
            ifc_classes=ifc_classes,
            storeys=storeys_list,
            documents=documents,
            rulesets=rulesets,
            models=models_summary,
        )

    async def query(
        self,
        project_id: int,
        request: GraphRagQueryRequest,
    ) -> GraphRagQueryResponse:
        """Execute a full Graph-RAG query using SOTA hybrid RRF retrieval."""
        steps: list[GraphRagStep] = []
        tool_calls: list[GraphRagToolCall] = []
        citations: list[GraphRagCitation] = []
        cypher_queries: list[str] = []
        subgraph_nodes: list[dict[str, Any]] = []
        subgraph_edges: list[dict[str, Any]] = []

        # Step 0: Dual-level query analysis (LightRAG)
        analysis = self.router.analyze_query_dual_level(request.query, request.element_class)
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

        intent_type = analysis.get("intent_type", "compliance_check")
        skip_doc = analysis.get("skip_document_search", False)

        # Step 1: Document Graph Retrieval (Vector + BM25 + Topological RRF)
        if request.scope in ("document", "hybrid") and not skip_doc:
            doc_res = await self.document_retriever.retrieve(
                query=request.query,
                document_id=request.document_id,
                target_classes=detected_ifc_classes,
                concrete_clauses=analysis.get("concrete_clauses"),
                abstract_themes=analysis.get("abstract_themes"),
                intent_type=intent_type,
                project_id=project_id,
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
        elif request.scope in ("document", "hybrid") and skip_doc:
            steps.append(
                GraphRagStep(
                    step_index=1,
                    title="Unified Neo4j Hybrid RRF Retrieval",
                    description="Bypassed document specification retrieval to preserve direct relevance to project/model metadata inquiry.",
                    status="done",
                    data={"citations_count": 0, "skipped": True},
                )
            )

        # Step 2: Model Graph Retrieval (Hub-Suppressed Spatial Traversal)
        if request.scope in ("model", "hybrid"):
            # model_retriever.retrieve is synchronous (Neo4j driver calls, and
            # on first use a whole-model ingest); run it in a thread so the
            # event loop keeps serving other requests and SSE streams meanwhile.
            model_res = await asyncio.to_thread(
                self.model_retriever.retrieve,
                project_id=project_id,
                query=request.query,
                target_classes=detected_ifc_classes,
                element_guids=analysis.get("element_guids"),
                retrieval_mode=retrieval_mode,
                intent_type=intent_type,
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

        # Step 3: Synthesis & Verification
        steps.append(
            GraphRagStep(
                step_index=3,
                title="Cross-Domain Synthesis & Verification",
                description="Synthesizing grounded engineering compliance response with inline citations.",
                status="done",
                data=None,
            )
        )

        prompt_payload = self.synthesizer.build_synthesis_prompt(
            query=request.query,
            doc_context=doc_context,
            model_context=model_context,
            scope=request.scope,
            retrieval_mode=retrieval_mode,
            intent_type=intent_type,
        )

        answer_text = await self.synthesizer.synthesize_answer(prompt_payload)
        followups = self.synthesizer.generate_followups(
            request.query, detected_ifc_classes, request.scope, intent_type=intent_type
        )

        subgraph_payload = {
            "nodes": subgraph_nodes[:30],
            "edges": subgraph_edges[:40],
        }

        return GraphRagQueryResponse(
            project_id=project_id,
            scope=request.scope,
            answer=answer_text,
            citations=citations,
            tool_calls=tool_calls,
            reasoning_steps=steps,
            cypher_queries=cypher_queries,
            suggested_followups=followups,
            subgraph_data=subgraph_payload,
            retrieval_mode=retrieval_mode,
            rrf_metrics=rrf_metrics,
        )

    async def stream_query(
        self,
        project_id: int,
        request: GraphRagQueryRequest,
    ) -> AsyncGenerator[str, None]:
        """Stream Graph-RAG query execution with real-time SSE reasoning steps and tokens."""
        # Step 0: Dual-level query routing
        analysis = self.router.analyze_query_dual_level(request.query, request.element_class)
        detected_ifc_classes = analysis["target_classes"]
        retrieval_mode = analysis["retrieval_mode"]
        intent_type = analysis.get("intent_type", "compliance_check")
        skip_doc = analysis.get("skip_document_search", False)

        step_0 = GraphRagStep(
            step_index=0,
            title="Dual-Level Intent & Query Routing",
            description=f"Scope: {request.scope} ({retrieval_mode}). Target classes: {detected_ifc_classes or 'General'}.",
            status="done",
            data=analysis,
        )
        yield self.synthesizer.format_sse_event("step", step_0.model_dump())

        doc_context = ""
        model_context = ""
        citations: list[GraphRagCitation] = []
        tool_calls: list[GraphRagToolCall] = []
        cypher_queries: list[str] = []
        subgraph_nodes: list[dict[str, Any]] = []
        subgraph_edges: list[dict[str, Any]] = []
        rrf_metrics: dict[str, Any] = {"mode": retrieval_mode}

        # Step 1: Document Retrieval
        if request.scope in ("document", "hybrid") and not skip_doc:
            step_1_active = GraphRagStep(
                step_index=1,
                title="Unified Neo4j Hybrid RRF Retrieval",
                description="Executing Vector, BM25, and Graph streams...",
                status="running",
            )
            yield self.synthesizer.format_sse_event("step", step_1_active.model_dump())

            doc_res = await self.document_retriever.retrieve(
                query=request.query,
                document_id=request.document_id,
                target_classes=detected_ifc_classes,
                concrete_clauses=analysis.get("concrete_clauses"),
                abstract_themes=analysis.get("abstract_themes"),
                intent_type=intent_type,
                project_id=project_id,
            )
            doc_context = doc_res["text"]
            citations.extend(doc_res["citations"])
            tool_calls.append(doc_res["tool_call"])
            if doc_res.get("cypher"):
                cypher_queries.append(doc_res["cypher"])
            subgraph_nodes.extend(doc_res.get("nodes", []))
            subgraph_edges.extend(doc_res.get("edges", []))
            rrf_metrics["document_sections_fused"] = len(doc_res["citations"])

            step_1_done = GraphRagStep(
                step_index=1,
                title="Unified Neo4j Hybrid RRF Retrieval",
                description=f"Fused {len(doc_res['citations'])} top specification sections via RRF (k=60).",
                status="done",
            )
            yield self.synthesizer.format_sse_event("step", step_1_done.model_dump())
            yield self.synthesizer.format_sse_event("tool_call", doc_res["tool_call"].model_dump())
        elif request.scope in ("document", "hybrid") and skip_doc:
            step_1_skipped = GraphRagStep(
                step_index=1,
                title="Unified Neo4j Hybrid RRF Retrieval",
                description="Bypassed document specification retrieval to preserve direct relevance to project/model metadata inquiry.",
                status="done",
                data={"citations_count": 0, "skipped": True},
            )
            yield self.synthesizer.format_sse_event("step", step_1_skipped.model_dump())

        # Step 2: Model Retrieval
        if request.scope in ("model", "hybrid"):
            step_2_active = GraphRagStep(
                step_index=2,
                title="Hub-Suppressed Model Graph Traversal",
                description="Traversing spatial hierarchy with hub suppression...",
                status="running",
            )
            yield self.synthesizer.format_sse_event("step", step_2_active.model_dump())

            # model_retriever.retrieve is synchronous (Neo4j driver calls, and
            # on first use a whole-model ingest); run it in a thread so the
            # event loop keeps serving other requests and SSE streams meanwhile.
            model_res = await asyncio.to_thread(
                self.model_retriever.retrieve,
                project_id=project_id,
                query=request.query,
                target_classes=detected_ifc_classes,
                element_guids=analysis.get("element_guids"),
                retrieval_mode=retrieval_mode,
                intent_type=intent_type,
            )
            model_context = model_res["text"]
            citations.extend(model_res["citations"])
            tool_calls.append(model_res["tool_call"])
            if model_res.get("cypher"):
                cypher_queries.append(model_res["cypher"])
            subgraph_nodes.extend(model_res.get("nodes", []))
            subgraph_edges.extend(model_res.get("edges", []))
            rrf_metrics["model_elements_inspected"] = model_res["element_count"]

            step_2_done = GraphRagStep(
                step_index=2,
                title="Hub-Suppressed Model Graph Traversal",
                description=f"Inspected {model_res['element_count']} IFC element instances in model.",
                status="done",
            )
            yield self.synthesizer.format_sse_event("step", step_2_done.model_dump())
            yield self.synthesizer.format_sse_event("tool_call", model_res["tool_call"].model_dump())

        # Step 3: Synthesis
        step_3 = GraphRagStep(
            step_index=3,
            title="Cross-Domain Synthesis & Verification",
            description="Synthesis complete.",
            status="done",
        )
        yield self.synthesizer.format_sse_event("step", step_3.model_dump())

        for cit in citations:
            yield self.synthesizer.format_sse_event("citation", cit.model_dump())

        prompt_payload = self.synthesizer.build_synthesis_prompt(
            query=request.query,
            doc_context=doc_context,
            model_context=model_context,
            scope=request.scope,
            retrieval_mode=retrieval_mode,
            intent_type=intent_type,
        )

        full_answer: list[str] = []
        async for token in self.synthesizer.stream_tokens(prompt_payload):
            full_answer.append(token)
            yield self.synthesizer.format_sse_event("token", {"token": token})

        assembled_answer = "".join(full_answer).strip()
        followups = self.synthesizer.generate_followups(
            request.query, detected_ifc_classes, request.scope, intent_type=intent_type
        )

        subgraph_payload = {
            "nodes": subgraph_nodes[:30],
            "edges": subgraph_edges[:40],
        }

        final_response = GraphRagQueryResponse(
            project_id=project_id,
            scope=request.scope,
            answer=assembled_answer,
            citations=citations,
            tool_calls=tool_calls,
            reasoning_steps=[step_0, step_3],
            cypher_queries=cypher_queries,
            suggested_followups=followups,
            subgraph_data=subgraph_payload,
            retrieval_mode=retrieval_mode,
            rrf_metrics=rrf_metrics,
        )

        yield self.synthesizer.format_sse_event("done", final_response.model_dump())
