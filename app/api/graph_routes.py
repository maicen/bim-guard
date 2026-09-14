"""FastAPI router for on-demand and parallel graph intelligence operations."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.dependencies import get_graph_service, get_models_service
from app.api.projects import ProjectAccessChecker, get_project_access_checker
from app.modules.comparator.issue_schema import build_issue_proof_graph
from app.modules.contracts import (
    ElementRelationshipsResponse,
    GraphHealResponse,
    GraphStatusContract,
    IssueProofGraphContract,
    SpatialTreeResponse,
)
from app.modules.ifc_reader.bot_graph import build_bot_graph, get_element_relationships
from app.modules.ifc_reader.ifc_graph import (
    build_ifc_graph,
    build_ifc_graph_summary,
    build_spatial_tree,
    ingest_ifc_to_graph,
)
from app.modules.ifc_reader.ifc_spatial import IFCSpatialAdjacency, heal_spatial_boundaries
from app.services.graph_database import GraphService
from app.services.models_service import ModelsService

logger = logging.getLogger("bimguard.api.graph")

router = APIRouter(prefix="/graph", tags=["Graph & Spatial Intelligence"])


def _run_background_ingest(path: str, graph_service: GraphService, project_id: str) -> None:
    """Execute graph ingestion in an asynchronous background thread."""
    try:
        import ifcopenshell

        model = ifcopenshell.open(path)
        stats = ingest_ifc_to_graph(model, graph_service, project_id=project_id)
        logger.info("Background graph ingestion succeeded for project %s: %s", project_id, stats)
    except Exception as exc:
        logger.error("Background graph ingestion failed for project %s: %s", project_id, exc, exc_info=True)


@router.post(
    "/{project_id}/ingest",
    summary="Ingest project IFC into graph database on demand or in background",
)
async def ingest_project_graph(
    project_id: int,
    background_tasks: BackgroundTasks,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    models_service: Annotated[ModelsService, Depends(get_models_service)],
    graph_service: Annotated[GraphService, Depends(get_graph_service)],
    background: bool = Query(False, description="Run ingestion asynchronously in the background"),
) -> dict[str, Any] | GraphStatusContract:
    """Ingest project IFC model into property graph database (Neo4j / KùzuDB)."""
    project_access(project_id)

    path = models_service.resolve_primary_path(project_id)
    if path is None or not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No primary IFC model found for project {project_id}.",
        )

    if background:
        background_tasks.add_task(_run_background_ingest, str(path), graph_service, str(project_id))
        return {
            "status": "queued",
            "project_id": project_id,
            "message": f"Graph ingestion for project {project_id} queued in background.",
        }

    try:
        import ifcopenshell

        model = ifcopenshell.open(str(path))
        ingest_stats = ingest_ifc_to_graph(model, graph_service, project_id=str(project_id))
        graph = build_ifc_graph(model)
        summary = build_ifc_graph_summary(graph)

        adj = IFCSpatialAdjacency(model, fallback_to_geometric=True).build()

        return GraphStatusContract(
            project_id=project_id,
            node_count=ingest_stats.get("nodes", graph.number_of_nodes()),
            edge_count=ingest_stats.get("relationships", graph.number_of_edges()),
            has_spatial_boundaries=adj.has_boundaries,
            is_geometric_fallback=adj.is_geometric_fallback,
            centrality_summary=summary.get("centrality_summary", {}),
        )
    except Exception as exc:
        logger.error("Graph ingestion failed for project %d: %s", project_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph ingestion failed: {exc}",
        )


@router.get(
    "/{project_id}/status",
    response_model=GraphStatusContract,
    summary="Get project relationship graph metrics, boundaries, and centrality",
)
def get_graph_status(
    project_id: int,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    models_service: Annotated[ModelsService, Depends(get_models_service)],
) -> GraphStatusContract:
    """Inspect the topological relationships, boundary status, and network centrality of a project's model."""
    project_access(project_id)

    path = models_service.resolve_primary_path(project_id)
    if path is None or not path.exists():
        return GraphStatusContract(
            project_id=project_id,
            node_count=0,
            edge_count=0,
            has_spatial_boundaries=False,
            is_geometric_fallback=False,
            centrality_summary={},
        )

    try:
        import ifcopenshell

        model = ifcopenshell.open(str(path))
        graph = build_ifc_graph(model)
        summary = build_ifc_graph_summary(graph)
        adj = IFCSpatialAdjacency(model, fallback_to_geometric=True).build()

        return GraphStatusContract(
            project_id=project_id,
            node_count=summary["node_count"],
            edge_count=summary["edge_count"],
            has_spatial_boundaries=adj.has_boundaries,
            is_geometric_fallback=adj.is_geometric_fallback,
            centrality_summary=summary.get("centrality_summary", {}),
        )
    except Exception as exc:
        logger.warning("Failed to generate graph status for project %d: %s", project_id, exc)
        return GraphStatusContract(
            project_id=project_id,
            node_count=0,
            edge_count=0,
            has_spatial_boundaries=False,
            is_geometric_fallback=False,
            centrality_summary={},
        )


@router.get(
    "/{project_id}/spatial-tree",
    response_model=SpatialTreeResponse,
    summary="Get the project's IFC spatial containment tree",
)
def get_spatial_tree(
    project_id: int,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    models_service: Annotated[ModelsService, Depends(get_models_service)],
) -> SpatialTreeResponse:
    """Roll the model's spatial decomposition/containment relationships into a tree.

    Rooted at IfcProject, for a viewer panel that navigates the physical
    hierarchy (Project -> Site -> Building -> Storey -> Space -> Element)
    rather than IFC layer/category, which is all the existing Layers panel
    exposes.
    """
    project_access(project_id)

    path = models_service.resolve_primary_path(project_id)
    if path is None or not path.exists():
        return SpatialTreeResponse(project_id=project_id, root=None)

    try:
        import ifcopenshell

        model = ifcopenshell.open(str(path))
        graph = build_ifc_graph(model)
        tree = build_spatial_tree(graph)
        return SpatialTreeResponse(project_id=project_id, root=tree)
    except Exception as exc:
        logger.warning("Failed to build spatial tree for project %d: %s", project_id, exc)
        return SpatialTreeResponse(project_id=project_id, root=None)


@router.get(
    "/{project_id}/element/{guid}/relationships",
    response_model=ElementRelationshipsResponse,
    summary="Get one element's BOT/SAREF4BLDG classification and relationships",
)
def get_element_relationships_route(
    project_id: int,
    guid: str,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    models_service: Annotated[ModelsService, Depends(get_models_service)],
) -> ElementRelationshipsResponse:
    """Backs the Knowledge Graph-Enriched 3D Viewport.

    Click an element, see its BOT spatial containment/boundary interfaces
    and SAREF4BLDG typing.

    Builds the BOT graph on demand from the primary model file, the same way
    `/status` and `/spatial-tree` do, rather than depending on a persisted
    triplestore -- this works regardless of whether the project has ever had
    an `enable_shacl=True` analysis run.
    """
    project_access(project_id)

    path = models_service.resolve_primary_path(project_id)
    if path is None or not path.exists():
        return ElementRelationshipsResponse(project_id=project_id, guid=guid, exists=False)

    try:
        import ifcopenshell

        model = ifcopenshell.open(str(path))
        ifc_graph = build_ifc_graph(model)
        adjacency = IFCSpatialAdjacency(model, fallback_to_geometric=True).build()
        bot_graph = build_bot_graph(ifc_graph, adjacency)
        relationships = get_element_relationships(bot_graph, guid)
        return ElementRelationshipsResponse(project_id=project_id, guid=guid, **relationships)
    except Exception as exc:
        logger.warning(
            "Failed to resolve element relationships for project %d guid %s: %s",
            project_id,
            guid,
            exc,
        )
        return ElementRelationshipsResponse(project_id=project_id, guid=guid, exists=False)


@router.post(
    "/{project_id}/heal",
    response_model=GraphHealResponse,
    summary="Reconcile and synthesize missing spatial boundaries in IFC model",
)
def heal_model_boundaries(
    project_id: int,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    models_service: Annotated[ModelsService, Depends(get_models_service)],
) -> GraphHealResponse:
    """Trigger TopologicPy-inspired geometric spatial adjacency reconciliation and model healing."""
    project_access(project_id)

    path = models_service.resolve_primary_path(project_id)
    if path is None or not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No primary IFC model found for project {project_id}.",
        )

    try:
        import ifcopenshell

        model = ifcopenshell.open(str(path))
        heal_result = heal_spatial_boundaries(model)

        return GraphHealResponse(
            project_id=project_id,
            healed_spaces=heal_result.get("healed_spaces", 0),
            created_boundaries=heal_result.get("created_boundaries", 0),
            total_boundaries=heal_result.get("total_boundaries", 0),
            status=heal_result.get("status", "success"),
            message=heal_result.get("message", "Model healed successfully."),
        )
    except Exception as exc:
        logger.error("Spatial boundary healing failed for project %d: %s", project_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Spatial boundary healing failed: {exc}",
        )


@router.get(
    "/{project_id}/proof/{issue_id}",
    response_model=IssueProofGraphContract,
    summary="Retrieve explainable proof graph DAG for a specific finding",
)
def get_issue_proof(
    project_id: int,
    issue_id: str,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
) -> IssueProofGraphContract:
    """Generate the 4-layer deductive proof graph explaining why an issue was flagged.

    Looks the issue up in each runnable analysis slug's result
    (``run_analysis``, the same cache every other analyze.py endpoint reads)
    rather than fabricating one: a UI only ever asks this for an issue it is
    already showing, which means some prior analysis run produced it and
    ``run_analysis(..., use_cache=True)`` should find it in cache. 404s if no
    slug's result contains a matching issue id -- never a synthetic stand-in.
    """
    project_access(project_id)

    from app.services.analysis_runner import RUNNABLE_SLUGS, run_analysis

    for slug in RUNNABLE_SLUGS:
        result = run_analysis(slug, project_id, use_cache=True)
        for issue in result.get("audit_issues", []):
            if getattr(issue, "id", None) == issue_id:
                proof_data = build_issue_proof_graph(issue)
                return IssueProofGraphContract(**proof_data)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No issue {issue_id!r} found for project {project_id}.",
    )
