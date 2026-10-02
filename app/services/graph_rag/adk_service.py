"""ADK-powered Graph-RAG service prototype."""

import json
from typing import Any, AsyncGenerator, Optional
from google.adk.agents import Agent

from app.logging_config import get_logger
from app.modules.contracts.graph import (
    GraphRagQueryRequest,
    GraphRagStep,
    GraphRagToolCall,
)
from app.services.embedding_service import EmbeddingService, get_shared_embedding_service
from app.services.graph_database import GraphService
from app.services.graph_rag.document_retriever import DocumentGraphRetriever
from app.services.graph_rag.model_retriever import ModelGraphRetriever
from app.services.models_service import ModelsService
from app.services.projects_service import ProjectsService
from app.services.graph_rag.synthesizer import GraphRagSynthesizer

logger = get_logger(__name__)

class GraphRagAdkService:
    """ADK-powered Graph-RAG Copilot."""

    def __init__(
        self,
        graph_service: GraphService,
        embedding_service: Optional[EmbeddingService] = None,
        models_service: Optional[ModelsService] = None,
        projects_service: Optional[Any] = None,
    ):
        self.graph_service = graph_service
        self.embedding_service = embedding_service or get_shared_embedding_service()
        self.models_service = models_service or ModelsService()
        self.projects_service = projects_service

        if self.projects_service is None:
            try:
                self.projects_service = ProjectsService(models_service=self.models_service)
            except Exception:
                self.projects_service = None

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

    async def stream_query(
        self,
        project_id: int,
        request: GraphRagQueryRequest,
    ) -> AsyncGenerator[str, None]:
        """Stream query using ADK Agent."""
        
        # 1. Define tools that bind the project_id context
        async def search_building_codes(search_query: str) -> dict:
            """Searches architectural specifications and building code documents for the project.
            
            Args:
                search_query: The query to search in the documents.
            """
            res = await self.document_retriever.retrieve(
                query=search_query,
                document_id=request.document_id,
                target_classes=[],
                intent_type="compliance_check",
                project_id=project_id,
            )
            # ADK tools should return dicts or strings
            return {"context": res.get("text", ""), "citations": res.get("citations", [])}

        async def inspect_bim_model(search_query: str) -> dict:
            """Inspects the 3D BIM model (IFC) and returns geometric or property information.
            
            Args:
                search_query: The query to inspect the model.
            """
            res = self.model_retriever.retrieve(
                query=search_query,
                project_id=project_id,
                target_classes=[],
                intent_type="compliance_check",
            )
            return {"context": res.get("text", ""), "cypher": res.get("cypher", "")}

        # 2. Configure ADK Agent
        agent = Agent(
            name="bim_copilot",
            model="gemini-2.5-flash",
            instruction="""You are an architectural BIM compliance assistant.
Use tools to search building codes or inspect the 3D BIM model as needed.
Answer the user's question clearly, citing specific building codes and model elements if available.""",
            tools=[search_building_codes, inspect_bim_model]
        )

        # 3. Stream execution and translate ADK events to frontend SSE format
        step_idx = 0
        
        # Start initial step
        step_0 = GraphRagStep(
            step_index=step_idx,
            title="ADK Agent Execution",
            description="Agent is thinking...",
            status="running"
        )
        yield self.synthesizer.format_sse_event("step", step_0.model_dump())

        from google.adk.runners import InMemoryRunner
        from google.genai.types import Content, Part
        from google.adk.events import Event
        
        runner = InMemoryRunner(agent)
        msg = Content(role='user', parts=[Part(text=request.query)])
        
        async for event in runner.run_async(user_id='demo', session_id='123', new_message=msg):
            if isinstance(event, Event):
                # The event holds the ADK output
                if hasattr(event, "output"):
                    output = getattr(event, "output")
                    if isinstance(output, str):
                        yield self.synthesizer.format_sse_event("token", output)
                    elif hasattr(output, "tool_name"):
                        tc = GraphRagToolCall(
                            name=output.tool_name,
                            args=getattr(output, "arguments", {}),
                            cypher_query=""
                        )
                        yield self.synthesizer.format_sse_event("tool_call", tc.model_dump())
                        step_idx += 1
                        step_t = GraphRagStep(
                            step_index=step_idx,
                            title=f"Running Tool: {output.tool_name}",
                            description=json.dumps(getattr(output, "arguments", {})),
                            status="running"
                        )
                        yield self.synthesizer.format_sse_event("step", step_t.model_dump())
                    else:
                        # Fallback for dict or other responses
                        if isinstance(output, dict) and "citations" in output:
                            for cit in output["citations"]:
                                if isinstance(cit, dict):
                                    yield self.synthesizer.format_sse_event("citation", cit)
                                else:
                                    yield self.synthesizer.format_sse_event("citation", cit.model_dump())
                        yield self.synthesizer.format_sse_event("token", str(output))
            elif hasattr(event, "text"):
                yield self.synthesizer.format_sse_event("token", getattr(event, "text"))

        step_done = GraphRagStep(
            step_index=step_idx,
            title="ADK Agent Execution",
            description="Finished processing.",
            status="done"
        )
        yield self.synthesizer.format_sse_event("step", step_done.model_dump())
        yield self.synthesizer.format_sse_event("done", {})

