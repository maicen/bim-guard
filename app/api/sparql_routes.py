"""FastAPI router for SPARQL endpoint integration."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.api.dependencies import get_graph_triplestore_service
from app.api.projects import ProjectAccessChecker, get_project_access_checker
from app.logging_config import get_logger
from app.services.graph_triplestore_service import GraphTriplestoreService

logger = get_logger(__name__)

router = APIRouter(prefix="/sparql", tags=["sparql"])


class SparqlQueryRequest(BaseModel):
    """Payload for POST /api/sparql/{project_id}."""
    query: str


@router.post("/{project_id}", summary="Execute SPARQL query on project named graph")
async def execute_sparql_query(
    project_id: int,
    request: Request,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    triplestore_service: Annotated[GraphTriplestoreService, Depends(get_graph_triplestore_service)],
) -> dict[str, Any]:
    """Execute a SPARQL query on the project's named graph.
    
    The query can be sent as JSON `{"query": "SELECT..."}` or as raw text/plain
    or application/sparql-query in the request body.
    """
    project_access(project_id)

    content_type = request.headers.get("content-type", "")
    query_str = ""
    
    if "application/json" in content_type:
        try:
            payload = await request.json()
            query_str = payload.get("query", "")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload.",
            )
    else:
        body = await request.body()
        query_str = body.decode("utf-8")
        
    query_str = query_str.strip()
    if not query_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SPARQL query string is required.",
        )
        
    try:
        results = triplestore_service.query(project_id, query_str)
        return results
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SPARQL query failed: {exc}",
        )
