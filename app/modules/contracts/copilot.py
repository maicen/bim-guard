"""Graph-RAG Copilot conversation persistence contracts."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

__all__ = [
    "ChatMessagePayload",
    "ChatConversationSummary",
    "ChatConversationDetail",
    "ChatConversationCreatePayload",
    "ChatConversationUpdatePayload",
    "ChatMessagesBatchPayload",
]


class ChatMessagePayload(BaseModel):
    """A single turn within a Copilot conversation thread."""

    id: str = Field(..., description="Unique message identifier")
    role: str = Field(..., description="Message author role: user, assistant, or system")
    content: str = Field(default="", description="Message text content")
    citations: list[dict[str, Any]] = Field(
        default_factory=list, description="Grounded citations referenced in this message"
    )
    reasoning_steps: list[dict[str, Any]] = Field(
        default_factory=list, description="Chain-of-thought execution milestones"
    )
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list, description="Tool calls and Cypher executions"
    )
    cypher_queries: list[str] = Field(
        default_factory=list, description="Cypher queries executed during retrieval"
    )
    timestamp: Optional[str] = Field(
        default=None, description="Client display timestamp string"
    )
    created_at: Optional[str] = Field(
        default=None, description="ISO-8601 creation timestamp"
    )


class ChatConversationSummary(BaseModel):
    """Metadata for listing conversations in the persistent history sidebar."""

    id: str = Field(..., description="Conversation UUID")
    project_id: int = Field(..., description="Governing project ID")
    user_id: Optional[str] = Field(default=None, description="Owner user ID if authenticated")
    title: str = Field(default="New Conversation", description="Conversation topic title")
    scope: str = Field(default="hybrid", description="Retrieval scope: hybrid, document, or model")
    document_id: Optional[int] = Field(default=None, description="Optional focused document ID")
    element_class: Optional[str] = Field(default=None, description="Optional focused IFC class")
    is_pinned: bool = Field(default=False, description="Whether pinned to top of history")
    message_count: int = Field(default=0, description="Total messages in thread")
    last_message_preview: Optional[str] = Field(
        default=None, description="Preview snippet of the most recent message"
    )
    created_at: str = Field(..., description="ISO-8601 creation timestamp")
    updated_at: str = Field(..., description="ISO-8601 last update timestamp")


class ChatConversationDetail(BaseModel):
    """Full conversation including complete message history for thread restoration."""

    id: str = Field(..., description="Conversation UUID")
    project_id: int = Field(..., description="Governing project ID")
    user_id: Optional[str] = Field(default=None, description="Owner user ID if authenticated")
    title: str = Field(default="New Conversation", description="Conversation topic title")
    scope: str = Field(default="hybrid", description="Retrieval scope: hybrid, document, or model")
    document_id: Optional[int] = Field(default=None, description="Optional focused document ID")
    element_class: Optional[str] = Field(default=None, description="Optional focused IFC class")
    is_pinned: bool = Field(default=False, description="Whether pinned to top of history")
    created_at: str = Field(..., description="ISO-8601 creation timestamp")
    updated_at: str = Field(..., description="ISO-8601 last update timestamp")
    messages: list[ChatMessagePayload] = Field(
        default_factory=list, description="Ordered list of message turns"
    )


class ChatConversationCreatePayload(BaseModel):
    """Payload for initializing a new conversation thread."""

    project_id: int = Field(..., description="Governing project ID")
    title: Optional[str] = Field(default="New Conversation", description="Initial conversation title")
    scope: Optional[str] = Field(default="hybrid", description="Retrieval scope")
    document_id: Optional[int] = Field(default=None, description="Optional document focus")
    element_class: Optional[str] = Field(default=None, description="Optional IFC class focus")


class ChatConversationUpdatePayload(BaseModel):
    """Payload for updating conversation metadata (title, pinned status, scope)."""

    title: Optional[str] = Field(default=None, description="Updated conversation title")
    is_pinned: Optional[bool] = Field(default=None, description="Pinned state toggle")
    scope: Optional[str] = Field(default=None, description="Updated scope")
    document_id: Optional[int] = Field(default=None, description="Updated document focus")
    element_class: Optional[str] = Field(default=None, description="Updated IFC class focus")


class ChatMessagesBatchPayload(BaseModel):
    """Batch payload for appending message turns to a conversation."""

    messages: list[ChatMessagePayload] = Field(
        ..., description="Message turns to persist in this conversation"
    )
