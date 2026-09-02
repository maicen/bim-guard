"""FastAPI router for the Digital Inspector agent."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_digital_inspector_service
from app.modules.contracts import InspectorQueryRequest, InspectorResponse
from app.services.digital_inspector_service import DigitalInspectorService

router = APIRouter()


@router.post("/{project_id}/inspect", response_model=InspectorResponse, summary="Ask the Digital Inspector a question about a project")
async def inspect_project(
    project_id: int,
    payload: InspectorQueryRequest,
    service: Annotated[DigitalInspectorService, Depends(get_digital_inspector_service)],
) -> InspectorResponse:
    """Run a natural-language query through the Digital Inspector agent.

    Tool-call progress streams on the existing `GET /api/events/{project_id}`
    SSE channel (same as an engine run) rather than a separate event system.
    """
    return await service.run_inspection(project_id, payload.query)
