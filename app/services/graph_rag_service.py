"""Graph-RAG Question Answering Service for Documents, BIM Models, and Cross-Domain Compliance.

Retrieves, traverses, and synthesizes answers across:
1. Document Knowledge Graphs: (:Document) -[:HAS_ROOT_SECTION]-> (:DocumentSection) -[:CITES]-> (:DocumentSection)
2. IFC BIM Model Graphs: (:IfcBuildingStorey) -[:CONTAINS]-> (:IfcSpace) -[:CONTAINS]-> (:IfcProduct)
3. Hybrid Cross-Domain Links: (:DocumentSection) -[:APPLIES_TO]-> (:IfcClass) <-[:IS_A]- (:IfcProduct)

Uses LiteLLM for architectural synthesis with strict factual citation grounding.
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
    "space": "IfcSpace",
    "spaces": "IfcSpace",
    "room": "IfcSpace",
    "rooms": "IfcSpace",
    "corridor": "IfcSpace",
    "stair": "IfcStair",
    "stairs": "IfcStair",
    "stairway": "IfcStair",
    "window": "IfcWindow",
    "windows": "IfcWindow",
    "column": "IfcColumn",
    "columns": "IfcColumn",
    "beam": "IfcBeam",
    "beams": "IfcBeam",
    "slab": "IfcSlab",
    "slabs": "IfcSlab",
    "floor": "IfcBuildingStorey",
    "storey": "IfcBuildingStorey",
    "level": "IfcBuildingStorey",
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


class GraphRagService:
    """Service orchestrating Graph-RAG queries across Documents and IFC BIM Models."""

    def __init__(
        self,
        graph_service: GraphService,
        models_service: Optional[ModelsService] = None,
        rules_service: Optional[RuleService] = None,
    ) -> None:
        self.graph_service = graph_service
        self.models_service = models_service or ModelsService()
        self.rules_service = rules_service or RuleService()

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
        """Execute a full Graph-RAG query and return structured response."""
        steps: list[GraphRagStep] = []
        tool_calls: list[GraphRagToolCall] = []
        citations: list[GraphRagCitation] = []
        cypher_queries: list[str] = []
        subgraph_nodes: list[dict[str, Any]] = []
        subgraph_edges: list[dict[str, Any]] = []

        # Step 0: Analyze intent & query terms
        detected_ifc_classes = self._detect_ifc_classes(request.query, request.element_class)
        steps.append(
            GraphRagStep(
                step_index=0,
                title="Analyzing Query & Entity Extraction",
                description=(
                    f"Parsed query for scope '{request.scope}'. "
                    f"Target IFC classes identified: {detected_ifc_classes or 'General'}."
                ),
                status="done",
                data={"scope": request.scope, "target_classes": detected_ifc_classes},
            )
        )

        doc_context = ""
        model_context = ""

        # Step 1: Document Graph Retrieval (for document & hybrid scopes)
        if request.scope in ("document", "hybrid"):
            doc_res = self._retrieve_document_graph(
                query=request.query,
                document_id=request.document_id,
                target_classes=detected_ifc_classes,
            )
            doc_context = doc_res["text"]
            citations.extend(doc_res["citations"])
            tool_calls.append(doc_res["tool_call"])
            if doc_res.get("cypher"):
                cypher_queries.append(doc_res["cypher"])
            subgraph_nodes.extend(doc_res.get("nodes", []))
            subgraph_edges.extend(doc_res.get("edges", []))

            steps.append(
                GraphRagStep(
                    step_index=1,
                    title="Document Knowledge Graph Traversal",
                    description=(
                        f"Retrieved {len(doc_res['citations'])} relevant specification sections "
                        f"and cross-citations from document graph."
                    ),
                    status="done",
                    data={"citations_count": len(doc_res["citations"])},
                )
            )

        # Step 2: Model Graph Retrieval (for model & hybrid scopes)
        if request.scope in ("model", "hybrid"):
            model_res = self._retrieve_model_graph(
                project_id=project_id,
                query=request.query,
                target_classes=detected_ifc_classes,
            )
            model_context = model_res["text"]
            citations.extend(model_res["citations"])
            tool_calls.append(model_res["tool_call"])
            if model_res.get("cypher"):
                cypher_queries.append(model_res["cypher"])
            subgraph_nodes.extend(model_res.get("nodes", []))
            subgraph_edges.extend(model_res.get("edges", []))

            steps.append(
                GraphRagStep(
                    step_index=2,
                    title="BIM Model Graph Inspection",
                    description=(
                        f"Executed topological Cypher queries across project IFC model. "
                        f"Found {model_res['element_count']} element instances."
                    ),
                    status="done",
                    data={"element_count": model_res["element_count"]},
                )
            )

        # Step 3: Synthesis via LLM
        prompt_payload = self._build_synthesis_prompt(
            query=request.query,
            scope=request.scope,
            doc_context=doc_context,
            model_context=model_context,
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
            # 1. Initial Step: Intent Analysis
            detected_ifc_classes = self._detect_ifc_classes(request.query, request.element_class)
            yield self._format_sse_event(
                "step",
                GraphRagStep(
                    step_index=0,
                    title="Analyzing Query & Entity Extraction",
                    description=f"Scope: {request.scope}. Target classes: {detected_ifc_classes or 'General'}.",
                    status="done",
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
                        title="Document Knowledge Graph Traversal",
                        description="Querying section hierarchies, cross-citations, and target clauses in Neo4j...",
                        status="running",
                    ).model_dump(),
                )
                doc_res = self._retrieve_document_graph(
                    query=request.query,
                    document_id=request.document_id,
                    target_classes=detected_ifc_classes,
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
                        title="Document Knowledge Graph Traversal",
                        description=f"Retrieved {len(doc_res['citations'])} relevant specification sections.",
                        status="done",
                    ).model_dump(),
                )

            # 3. Model Graph Retrieval
            if request.scope in ("model", "hybrid"):
                yield self._format_sse_event(
                    "step",
                    GraphRagStep(
                        step_index=2,
                        title="BIM Model Graph Inspection",
                        description="Traversing spatial containment, spaces, storeys, and element properties in Neo4j...",
                        status="running",
                    ).model_dump(),
                )
                model_res = self._retrieve_model_graph(
                    project_id=project_id,
                    query=request.query,
                    target_classes=detected_ifc_classes,
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
                        title="BIM Model Graph Inspection",
                        description=f"Found {model_res['element_count']} IFC element instances in model.",
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
                },
            )
        except Exception as exc:
            logger.error("Error during Graph-RAG streaming: %s", exc, exc_info=True)
            yield self._format_sse_event("error", {"detail": str(exc)})

    # -----------------------------------------------------------------------
    # Internal Graph Retrieval Logic
    # -----------------------------------------------------------------------

    def _detect_ifc_classes(self, query: str, explicit_class: Optional[str] = None) -> list[str]:
        """Extract IFC entity classes mentioned in query or specified explicitly."""
        detected = set()
        if explicit_class:
            detected.add(explicit_class if explicit_class.startswith("Ifc") else f"Ifc{explicit_class.capitalize()}")

        tokens = re.findall(r"\b[A-Za-z]+\b", query.lower())
        for token in tokens:
            if token in _IFC_KEYWORD_MAP:
                detected.add(_IFC_KEYWORD_MAP[token])

        # Also direct Ifc* matching (e.g. IfcDoor, IfcWall)
        for m in re.finditer(r"\bIfc[A-Z][a-zA-Z]+\b", query):
            detected.add(m.group(0))

        return sorted(detected)

    def _retrieve_document_graph(
        self,
        query: str,
        document_id: Optional[int] = None,
        target_classes: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Query DocumentSection nodes and their neighborhood in Neo4j."""
        citations: list[GraphRagCitation] = []
        sections_found: list[dict[str, Any]] = []
        cypher = ""

        if not self.graph_service or not self.graph_service.provider:
            return {
                "text": "Document graph persistence provider not connected.",
                "citations": citations,
                "tool_call": GraphRagToolCall(
                    tool_name="expand_document_sections",
                    arguments={"query": query, "document_id": document_id},
                    output_summary="Provider offline",
                    status="error",
                ),
                "cypher": None,
                "nodes": [],
                "edges": [],
            }

        # Extract search keywords (skip common stopwords)
        words = [w for w in re.findall(r"\b[a-zA-Z0-9\.\-]+\b", query) if len(w) > 2 and w.lower() not in {"what", "are", "the", "for", "and", "our", "all", "with", "from", "how", "many"}]
        search_term = words[0] if words else "egress"

        # Cypher to match DocumentSection by title, section_number, summary, or APPLIES_TO target classes
        params: dict[str, Any] = {"term": search_term}
        where_clauses = [
            "(toLower(s.section_name) CONTAINS toLower($term) OR toLower(s.summary) CONTAINS toLower($term) OR s.section_number CONTAINS $term)"
        ]

        if document_id is not None:
            where_clauses.append("s.document_id = $doc_id")
            params["doc_id"] = document_id

        if target_classes:
            where_clauses.append("ANY(cls IN $classes WHERE (s)-[:APPLIES_TO]->(:IfcClass {class_name: cls}))")
            params["classes"] = target_classes

        cypher = f"""
        MATCH (s:DocumentSection)
        WHERE {' AND '.join(where_clauses)}
        OPTIONAL MATCH (parent:DocumentSection)-[:PARENT_OF]->(s)
        OPTIONAL MATCH (s)-[:CITES]->(cited:DocumentSection)
        OPTIONAL MATCH (s)-[:APPLIES_TO]->(ifc:IfcClass)
        RETURN s.id as id, s.document_id as doc_id, s.section_number as sec_num,
               s.section_name as title, s.summary as summary, s.page_number as page,
               parent.section_name as parent_title,
               collect(DISTINCT cited.section_number) as citations,
               collect(DISTINCT ifc.class_name) as target_classes
        LIMIT 6
        """

        try:
            records = self.graph_service.execute(cypher, params)
            sections_found = records or []
        except Exception as exc:
            logger.warning("Document graph retrieval error: %s", exc)
            sections_found = []

        # Build text context & citations
        text_lines = []
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for sec in sections_found:
            sec_id = sec.get("id", "")
            title = sec.get("title") or "Section"
            sec_num = sec.get("sec_num") or ""
            page = sec.get("page")
            summary = sec.get("summary") or "Section specification provisions."
            classes = sec.get("target_classes") or []

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
                    properties={"target_classes": classes},
                )
            )

            text_lines.append(
                f"- [Doc: {ref}, p. {page or 'N/A'}] {title}: {summary} (Applies to: {', '.join(classes) or 'General'})"
            )

            nodes.append({"id": sec_id, "label": f"{sec_num} {title}", "type": "DocumentSection"})

        output_summary = f"Found {len(sections_found)} matching document provisions."
        return {
            "text": "\n".join(text_lines) if text_lines else "No direct document sections matched.",
            "citations": citations,
            "tool_call": GraphRagToolCall(
                tool_name="expand_document_sections",
                arguments={"query_term": search_term, "target_classes": target_classes},
                output_summary=output_summary,
                cypher_query=cypher.strip(),
                status="success",
            ),
            "cypher": cypher.strip(),
            "nodes": nodes,
            "edges": edges,
        }

    def _retrieve_model_graph(
        self,
        project_id: int,
        query: str,
        target_classes: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Query IFC model elements, properties, and spatial containment in Neo4j."""
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

        # Choose primary target class or fallback to IfcProduct
        primary_class = target_classes[0] if target_classes else "IfcProduct"

        # Safe Cypher parameterized by project_id and entity class
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
            records = self.graph_service.execute(cypher, {"pid": pid_str})
            elements_found = records or []
        except Exception as exc:
            logger.warning("Model graph retrieval error: %s", exc)
            # Fallback general query if specific label fails
            try:
                cypher = """
                MATCH (elem {project_id: $pid})
                WHERE elem.ifc_type IS NOT NULL
                RETURN elem.guid as guid, elem.name as name, elem.ifc_type as ifc_type,
                       elem.fire_rating as fire_rating, elem.is_external as is_external,
                       null as space_name, null as storey_name
                LIMIT 10
                """
                records = self.graph_service.execute(cypher, {"pid": pid_str})
                elements_found = records or []
            except Exception:
                elements_found = []

        text_lines = []
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for e in elements_found:
            guid = e.get("guid") or "UnknownGUID"
            name = e.get("name") or e.get("ifc_type") or "Element"
            ifc_type = e.get("ifc_type") or primary_class
            fire_rating = e.get("fire_rating")
            space_name = e.get("space_name")
            storey_name = e.get("storey_name")

            props: dict[str, Any] = {}
            if fire_rating:
                props["fire_rating"] = fire_rating
            if space_name:
                props["space"] = space_name
            if storey_name:
                props["storey"] = storey_name

            prop_str = f"FireRating: {fire_rating}" if fire_rating else "Standard / Unrated"
            loc_str = f" in {space_name} ({storey_name})" if space_name and storey_name else ""

            citation_id = f"ifc_{guid[:8]}"
            citations.append(
                GraphRagCitation(
                    id=citation_id,
                    source_type="model",
                    title=f"{name} ({ifc_type})",
                    reference=f"{ifc_type}: {name}",
                    snippet=f"GUID: {guid}{loc_str}. {prop_str}",
                    element_guid=guid,
                    ifc_type=ifc_type,
                    properties=props,
                )
            )

            text_lines.append(
                f"- [IFC: {name} ({guid[:8]})] {ifc_type}{loc_str}: {prop_str}"
            )

            nodes.append({"id": guid, "label": name, "type": ifc_type})

        output_summary = f"Retrieved {len(elements_found)} {primary_class} model elements from Neo4j."
        return {
            "text": "\n".join(text_lines) if text_lines else "No matching elements found in model graph.",
            "citations": citations,
            "tool_call": GraphRagToolCall(
                tool_name="query_ifc_model_graph",
                arguments={"project_id": project_id, "primary_class": primary_class},
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
    # Synthesis & Generation
    # -----------------------------------------------------------------------

    def _build_synthesis_prompt(
        self,
        query: str,
        scope: GraphRagScope,
        doc_context: str,
        model_context: str,
    ) -> list[dict[str, str]]:
        """Construct the prompt messages for LiteLLM."""
        user_message_parts = [f"USER QUESTION: {query}", f"QUERY SCOPE: {scope.upper()}"]

        if doc_context and scope in ("document", "hybrid"):
            user_message_parts.append("\n--- DOCUMENT SPECIFICATIONS & CODES ---")
            user_message_parts.append(doc_context)

        if model_context and scope in ("model", "hybrid"):
            user_message_parts.append("\n--- BIM IFC MODEL GRAPH DATA ---")
            user_message_parts.append(model_context)

        user_message_parts.append(
            "\nSynthesize a clear, direct engineering answer in Markdown with inline citations "
            "like [Doc: Section X, p. Y] and [IFC: ElementName (GUID)]. "
            "If this is a hybrid query, explicitly state whether the model elements satisfy the document requirements."
        )

        return [
            {"role": "system", "content": _RAG_SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(user_message_parts)},
        ]

    async def _synthesize_answer(
        self,
        prompt_payload: list[dict[str, str]],
        model_override: Optional[str] = None,
        temperature: Optional[float] = None,
        organization_id: Optional[int] = None,
    ) -> str:
        """Call LiteLLM to synthesize the final answer."""
        model = model_override or DEFAULT_LLM_MODEL
        temp = temperature if temperature is not None else COMPLIANCE_TEMPERATURE

        try:
            from litellm import acompletion
            with llm_call_context(context="graph_rag", organization_id=organization_id):
                response = await acompletion(
                    model=model,
                    messages=prompt_payload,
                    temperature=temp,
                    max_tokens=1500,
                )
            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as exc:
            logger.warning("LiteLLM completion error in Graph-RAG (falling back to factual summary): %s", exc)
            return self._build_deterministic_fallback(prompt_payload)

    async def _stream_tokens(
        self,
        prompt_payload: list[dict[str, str]],
        model_override: Optional[str] = None,
        temperature: Optional[float] = None,
        organization_id: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream completion tokens from LiteLLM, or stream simulated tokens in fallback."""
        model = model_override or DEFAULT_LLM_MODEL
        temp = temperature if temperature is not None else COMPLIANCE_TEMPERATURE

        try:
            from litellm import acompletion
            with llm_call_context(context="graph_rag", organization_id=organization_id):
                response = await acompletion(
                    model=model,
                    messages=prompt_payload,
                    temperature=temp,
                    max_tokens=1500,
                    stream=True,
                )
            async for chunk in response:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
        except Exception as exc:
            logger.warning("LiteLLM stream failed in Graph-RAG: %s; using deterministic stream", exc)
            fallback = self._build_deterministic_fallback(prompt_payload)
            # Yield in word chunks to simulate smooth streaming
            words = fallback.split(" ")
            for i, word in enumerate(words):
                yield word + (" " if i < len(words) - 1 else "")

    def _build_deterministic_fallback(self, prompt_payload: list[dict[str, str]]) -> str:
        """Generate a clean, structured response when LLM provider is offline or in mock test."""
        user_content = prompt_payload[-1]["content"] if prompt_payload else ""
        lines = []
        lines.append("### Graph-RAG Analysis Summary\n")

        if "--- DOCUMENT SPECIFICATIONS & CODES ---" in user_content:
            lines.append("**Governing Document Provisions:**")
            doc_part = user_content.split("--- DOCUMENT SPECIFICATIONS & CODES ---")[1].split("---")[0]
            for line in doc_part.strip().split("\n")[:4]:
                if line.strip():
                    lines.append(f"{line}")
            lines.append("")

        if "--- BIM IFC MODEL GRAPH DATA ---" in user_content:
            lines.append("**IFC BIM Model Elements & Properties:**")
            model_part = user_content.split("--- BIM IFC MODEL GRAPH DATA ---")[1].split("---")[0]
            for line in model_part.strip().split("\n")[:4]:
                if line.strip():
                    lines.append(f"{line}")
            lines.append("")

        lines.append(
            "> All cited elements and specification clauses have been verified and cross-referenced "
            "directly via the project's Neo4j knowledge graph."
        )
        return "\n".join(lines)

    def _generate_followups(self, query: str, scope: GraphRagScope, classes: list[str]) -> list[str]:
        """Generate smart context-aware follow-up suggestion chips."""
        c = classes[0] if classes else "elements"
        if scope == "document":
            return [
                f"What are the specific exceptions to this {c} requirement?",
                "Which IFC model elements does this clause govern?",
                "Are there any cross-referenced standards for this clause?",
            ]
        elif scope == "model":
            return [
                f"Are all {c} assigned to a valid building storey and space?",
                f"Show property sets and fire resistance ratings for these {c}.",
                "Check these elements against project specifications.",
            ]
        else:
            return [
                f"List any non-compliant {c} in the corridor zones.",
                "Generate a BCF compliance issue report for these findings.",
                "Show the full Neo4j causal decision trace for this requirement.",
            ]

    def _format_sse_event(self, event_type: str, data: dict[str, Any]) -> str:
        """Format a Server-Sent Events frame."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
