"""FastAPI router for managing configured Unstructured parsing-engine instances."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_unstructured_instances_service
from app.logging_config import get_logger
from app.modules.contracts import (
    UnstructuredInstanceCreateRequest,
    UnstructuredInstanceResponse,
    UnstructuredInstanceTestResponse,
    UnstructuredInstanceUpdateRequest,
)
from app.services.unstructured_instances_service import UnstructuredInstancesService

logger = get_logger(__name__)

router = APIRouter()


def _to_response(row: dict[str, Any]) -> UnstructuredInstanceResponse:
    return UnstructuredInstanceResponse(
        id=row["id"],
        name=row.get("name", ""),
        kind=row.get("kind", ""),
        api_url=row.get("api_url", ""),
        has_api_key=bool((row.get("api_key") or "").strip()),
        strategy=row.get("strategy") or "auto",
        is_default=bool(row.get("is_default", False)),
        is_enabled=bool(row.get("is_enabled", True)),
        notes=row.get("notes", ""),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


@router.get("", response_model=list[UnstructuredInstanceResponse], summary="List configured parsing engines")
def list_instances(
    service: Annotated[UnstructuredInstancesService, Depends(get_unstructured_instances_service)],
) -> list[UnstructuredInstanceResponse]:
    """Return all configured Unstructured parsing-engine instances."""
    return [_to_response(row) for row in service.list_instances()]


@router.post(
    "",
    response_model=UnstructuredInstanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a parsing engine instance",
)
def create_instance(
    payload: UnstructuredInstanceCreateRequest,
    service: Annotated[UnstructuredInstancesService, Depends(get_unstructured_instances_service)],
) -> UnstructuredInstanceResponse:
    """Register a new local or hosted Unstructured instance."""
    try:
        created = service.create_instance(
            name=payload.name,
            kind=payload.kind,
            api_url=payload.api_url,
            api_key=payload.api_key,
            strategy=payload.strategy or "auto",
            is_default=bool(payload.is_default),
            is_enabled=payload.is_enabled if payload.is_enabled is not None else True,
            notes=payload.notes or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(created)


@router.get("/{instance_id}", response_model=UnstructuredInstanceResponse, summary="Get a parsing engine instance")
def get_instance(
    instance_id: int,
    service: Annotated[UnstructuredInstancesService, Depends(get_unstructured_instances_service)],
) -> UnstructuredInstanceResponse:
    """Retrieve a single configured Unstructured instance by ID."""
    row = service.get_instance(instance_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unstructured instance {instance_id} not found.",
        )
    return _to_response(row)


@router.put("/{instance_id}", response_model=UnstructuredInstanceResponse, summary="Update a parsing engine instance")
def update_instance(
    instance_id: int,
    payload: UnstructuredInstanceUpdateRequest,
    service: Annotated[UnstructuredInstancesService, Depends(get_unstructured_instances_service)],
) -> UnstructuredInstanceResponse:
    """Update metadata for an existing configured Unstructured instance."""
    try:
        updated = service.update_instance(
            instance_id,
            name=payload.name,
            api_url=payload.api_url,
            api_key=payload.api_key,
            strategy=payload.strategy,
            is_default=payload.is_default,
            is_enabled=payload.is_enabled,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unstructured instance {instance_id} not found.",
        )
    return _to_response(updated)


@router.delete("/{instance_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a parsing engine instance")
def delete_instance(
    instance_id: int,
    service: Annotated[UnstructuredInstancesService, Depends(get_unstructured_instances_service)],
) -> None:
    """Delete a configured Unstructured instance by ID."""
    if not service.get_instance(instance_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unstructured instance {instance_id} not found.",
        )
    service.delete_instance(instance_id)


@router.post(
    "/{instance_id}/test",
    response_model=UnstructuredInstanceTestResponse,
    summary="Check connectivity to a configured parsing engine",
)
def test_instance(
    instance_id: int,
    service: Annotated[UnstructuredInstancesService, Depends(get_unstructured_instances_service)],
) -> UnstructuredInstanceTestResponse:
    """Ping a configured instance to confirm it is reachable and responding."""
    row = service.get_instance(instance_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unstructured instance {instance_id} not found.",
        )

    import httpx

    kind = row.get("kind")
    api_url = (row.get("api_url") or "").rstrip("/")
    try:
        if kind == "local":
            # The open-source unstructured-api server exposes a plain
            # GET /healthcheck (no auth) — see the Docker installation docs.
            response = httpx.get(f"{api_url}/healthcheck", timeout=5.0)
            response.raise_for_status()
            return UnstructuredInstanceTestResponse(ok=True, detail=response.text.strip())

        from app.modules.module1_doc_parser.unstructured_extractor import UnstructuredExtractor

        extractor = UnstructuredExtractor(
            api_key=row.get("api_key") or None,
            api_url=api_url or None,
            strategy=row.get("strategy") or "auto",
            kind="hosted",
            name=row.get("name"),
        )
        extractor._ensure_workflow()
        return UnstructuredInstanceTestResponse(ok=True, detail="Workflow API reachable.")
    except Exception as exc:
        logger.warning(
            "Unstructured instance test failed id=%s kind=%s error=%s", instance_id, kind, exc
        )
        return UnstructuredInstanceTestResponse(ok=False, detail=str(exc))
