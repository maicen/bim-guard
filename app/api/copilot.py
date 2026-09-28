"""FastAPI router for Graph-RAG Copilot conversation persistence."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_copilot_service
from app.api.projects import ProjectAccessChecker, get_project_access_checker
from app.auth import CurrentUser, get_current_user
from app.logging_config import get_logger
from app.modules.contracts.copilot import (
    ChatConversationCreatePayload,
    ChatConversationDetail,
    ChatConversationSummary,
    ChatConversationUpdatePayload,
    ChatMessagesBatchPayload,
)
from app.services.copilot_service import CopilotService

logger = get_logger(__name__)

router = APIRouter(prefix="/copilot", tags=["Graph-RAG Copilot"])


@router.get(
    "/conversations",
    response_model=list[ChatConversationSummary],
    summary="List conversations for a project",
)
def list_conversations(
    project_id: Annotated[int, Query(description="Governing project ID")],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    copilot_service: Annotated[CopilotService, Depends(get_copilot_service)],
) -> list[ChatConversationSummary]:
    """Retrieve all conversations for the selected project, ordered by pin and activity."""
    project_access(project_id)
    user_id = str(current_user.id) if current_user and getattr(current_user, "id", None) else None
    return copilot_service.list_conversations(project_id=project_id, user_id=user_id)


@router.post(
    "/conversations",
    response_model=ChatConversationDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation thread",
)
def create_conversation(
    payload: ChatConversationCreatePayload,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    copilot_service: Annotated[CopilotService, Depends(get_copilot_service)],
) -> ChatConversationDetail:
    """Initialize a persistent chat thread within a project."""
    project_access(payload.project_id)
    user_id = str(current_user.id) if current_user and getattr(current_user, "id", None) else None
    return copilot_service.create_conversation(
        project_id=payload.project_id,
        payload=payload,
        user_id=user_id,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ChatConversationDetail,
    summary="Get conversation detail with messages",
)
def get_conversation(
    conversation_id: str,
    project_id: Annotated[int, Query(description="Governing project ID")],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    copilot_service: Annotated[CopilotService, Depends(get_copilot_service)],
) -> ChatConversationDetail:
    """Fetch complete conversation history and messages."""
    project_access(project_id)
    conversation = copilot_service.get_conversation(
        conversation_id=conversation_id,
        project_id=project_id,
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found in project {project_id}",
        )
    return conversation


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ChatConversationSummary,
    summary="Update conversation metadata (title, pin, scope)",
)
def update_conversation(
    conversation_id: str,
    payload: ChatConversationUpdatePayload,
    project_id: Annotated[int, Query(description="Governing project ID")],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    copilot_service: Annotated[CopilotService, Depends(get_copilot_service)],
) -> ChatConversationSummary:
    """Update title, pinned status, or retrieval scope of a conversation."""
    project_access(project_id)
    updated = copilot_service.update_conversation(
        conversation_id=conversation_id,
        project_id=project_id,
        payload=payload,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found in project {project_id}",
        )
    return updated


@router.delete(
    "/conversations/{conversation_id}",
    summary="Delete conversation and its messages",
)
def delete_conversation(
    conversation_id: str,
    project_id: Annotated[int, Query(description="Governing project ID")],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    copilot_service: Annotated[CopilotService, Depends(get_copilot_service)],
) -> dict[str, Any]:
    """Permanently delete a conversation and its messages."""
    project_access(project_id)
    success = copilot_service.delete_conversation(
        conversation_id=conversation_id,
        project_id=project_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found in project {project_id}",
        )
    return {"deleted": True, "conversation_id": conversation_id}


@router.post(
    "/conversations/{conversation_id}/messages",
    summary="Append or update messages in conversation",
)
def save_conversation_messages(
    conversation_id: str,
    payload: ChatMessagesBatchPayload,
    project_id: Annotated[int, Query(description="Governing project ID")],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    copilot_service: Annotated[CopilotService, Depends(get_copilot_service)],
) -> dict[str, Any]:
    """Append one or more message turns to the conversation thread."""
    project_access(project_id)
    try:
        copilot_service.save_messages(
            conversation_id=conversation_id,
            project_id=project_id,
            messages=payload.messages,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return {"saved": len(payload.messages), "conversation_id": conversation_id}
