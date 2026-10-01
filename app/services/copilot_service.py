"""Copilot conversation persistence service.

Persists Graph-RAG Copilot conversations and message turns to Supabase
(public.chat_conversations and public.chat_messages) with local/in-memory adapter fallback.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.logging_config import get_logger
from app.modules.contracts.copilot import (
    ChatConversationCreatePayload,
    ChatConversationDetail,
    ChatConversationSummary,
    ChatConversationUpdatePayload,
    ChatMessagePayload,
)
from app.services.persistence import PersistenceService

logger = get_logger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_json_parse(val: Any) -> Any:
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return json.loads(val)
        except Exception:
            return []
    return []


class CopilotService:
    """Supabase-backed store for Copilot persistent conversation history."""

    def __init__(
        self,
        conversations_repo: Any = None,
        messages_repo: Any = None,
    ):
        self._conversations = (
            conversations_repo
            if conversations_repo is not None
            else PersistenceService.get_table(
                "chat_conversations",
                {
                    "id": str,
                    "project_id": int,
                    "user_id": str,
                    "title": str,
                    "scope": str,
                    "document_id": int,
                    "element_class": str,
                    "is_pinned": bool,
                    "created_at": str,
                    "updated_at": str,
                },
                pk="id",
            )
        )
        self._messages = (
            messages_repo
            if messages_repo is not None
            else PersistenceService.get_table(
                "chat_messages",
                {
                    "id": str,
                    "conversation_id": str,
                    "role": str,
                    "content": str,
                    "citations": str,
                    "reasoning_steps": str,
                    "tool_calls": str,
                    "cypher_queries": str,
                    "timestamp": str,
                    "created_at": str,
                },
                pk="id",
            )
        )

    def list_conversations(
        self,
        project_id: int,
        user_id: Optional[str] = None,
    ) -> list[ChatConversationSummary]:
        """List conversations for a project, sorted by is_pinned desc, updated_at desc."""
        try:
            rows = self._conversations.rows_where("project_id = ?", [project_id])
        except Exception as exc:
            logger.warning("Failed querying chat_conversations: %s", exc)
            return []

        # Filter by user_id if supplied
        if user_id:
            rows = [r for r in rows if not r.get("user_id") or r.get("user_id") == str(user_id)]

        summaries: list[ChatConversationSummary] = []
        for row in rows:
            cid = str(row["id"])
            try:
                msg_rows = self._messages.rows_where("conversation_id = ?", [cid])
            except Exception:
                msg_rows = []

            # Sort messages chronologically
            msg_rows.sort(key=lambda m: str(m.get("created_at") or ""))
            last_content = msg_rows[-1].get("content") if msg_rows else None
            last_preview = (
                (last_content[:120] + "...") if last_content and len(last_content) > 120 else last_content
            )

            doc_id = row.get("document_id")
            if doc_id is not None:
                try:
                    doc_id = int(doc_id)
                except (ValueError, TypeError):
                    doc_id = None

            summaries.append(
                ChatConversationSummary(
                    id=cid,
                    project_id=int(row["project_id"]),
                    user_id=str(row["user_id"]) if row.get("user_id") else None,
                    title=str(row.get("title") or "New Conversation"),
                    scope=str(row.get("scope") or "hybrid"),
                    document_id=doc_id,
                    element_class=row.get("element_class"),
                    is_pinned=bool(row.get("is_pinned", False)),
                    message_count=len(msg_rows),
                    last_message_preview=last_preview,
                    created_at=str(row.get("created_at") or _utc_now_iso()),
                    updated_at=str(row.get("updated_at") or _utc_now_iso()),
                )
            )

        # Sort pinned first, then by updated_at descending
        def _sort_key(s: ChatConversationSummary) -> tuple[int, float]:
            ts = 0.0
            if s.updated_at:
                try:
                    ts = datetime.fromisoformat(s.updated_at.replace("Z", "+00:00")).timestamp()
                except Exception:
                    ts = 0.0
            return (0 if s.is_pinned else 1, -ts)

        summaries.sort(key=_sort_key)
        return summaries

    def create_conversation(
        self,
        project_id: int,
        payload: ChatConversationCreatePayload,
        user_id: Optional[str] = None,
    ) -> ChatConversationDetail:
        """Create a new conversation thread."""
        conv_id = str(uuid.uuid4())
        now = _utc_now_iso()

        row = {
            "id": conv_id,
            "project_id": int(project_id),
            "user_id": str(user_id) if user_id else None,
            "title": (payload.title or "New Conversation").strip(),
            "scope": payload.scope or "hybrid",
            "document_id": payload.document_id,
            "element_class": payload.element_class,
            "is_pinned": False,
            "created_at": now,
            "updated_at": now,
        }
        self._conversations.insert(row)

        return ChatConversationDetail(
            id=conv_id,
            project_id=int(project_id),
            user_id=str(user_id) if user_id else None,
            title=row["title"],
            scope=row["scope"],
            document_id=row["document_id"],
            element_class=row["element_class"],
            is_pinned=False,
            created_at=now,
            updated_at=now,
            messages=[],
        )

    def get_conversation(
        self,
        conversation_id: str,
        project_id: int,
    ) -> Optional[ChatConversationDetail]:
        """Fetch conversation details along with full message thread."""
        row = self._conversations.get(str(conversation_id))
        if not row:
            return None
        if int(row.get("project_id", 0)) != int(project_id):
            return None

        try:
            msg_rows = self._messages.rows_where("conversation_id = ?", [str(conversation_id)])
        except Exception:
            msg_rows = []

        msg_rows.sort(key=lambda m: str(m.get("created_at") or ""))

        messages: list[ChatMessagePayload] = []
        for m in msg_rows:
            messages.append(
                ChatMessagePayload(
                    id=str(m["id"]),
                    role=str(m.get("role", "user")),
                    content=str(m.get("content", "")),
                    citations=_safe_json_parse(m.get("citations")),
                    reasoning_steps=_safe_json_parse(m.get("reasoning_steps")),
                    tool_calls=_safe_json_parse(m.get("tool_calls")),
                    cypher_queries=_safe_json_parse(m.get("cypher_queries")),
                    timestamp=m.get("timestamp"),
                    created_at=m.get("created_at"),
                )
            )

        doc_id = row.get("document_id")
        if doc_id is not None:
            try:
                doc_id = int(doc_id)
            except (ValueError, TypeError):
                doc_id = None

        return ChatConversationDetail(
            id=str(row["id"]),
            project_id=int(row["project_id"]),
            user_id=str(row["user_id"]) if row.get("user_id") else None,
            title=str(row.get("title") or "New Conversation"),
            scope=str(row.get("scope") or "hybrid"),
            document_id=doc_id,
            element_class=row.get("element_class"),
            is_pinned=bool(row.get("is_pinned", False)),
            created_at=str(row.get("created_at") or _utc_now_iso()),
            updated_at=str(row.get("updated_at") or _utc_now_iso()),
            messages=messages,
        )

    def update_conversation(
        self,
        conversation_id: str,
        project_id: int,
        payload: ChatConversationUpdatePayload,
    ) -> Optional[ChatConversationSummary]:
        """Update conversation properties such as title, is_pinned, or scope."""
        row = self._conversations.get(str(conversation_id))
        if not row or int(row.get("project_id", 0)) != int(project_id):
            return None

        updates: dict[str, Any] = {"updated_at": _utc_now_iso()}
        if payload.title is not None:
            updates["title"] = payload.title.strip()
        if payload.is_pinned is not None:
            updates["is_pinned"] = bool(payload.is_pinned)
        if payload.scope is not None:
            updates["scope"] = payload.scope
        if payload.document_id is not None:
            updates["document_id"] = payload.document_id
        if payload.element_class is not None:
            updates["element_class"] = payload.element_class

        self._conversations.update(updates=updates, pk_values=str(conversation_id))
        updated_row = self._conversations.get(str(conversation_id)) or row
        updated_row.update(updates)

        msg_rows = self._messages.rows_where("conversation_id = ?", [str(conversation_id)])
        msg_rows.sort(key=lambda m: str(m.get("created_at") or ""))
        last_content = msg_rows[-1].get("content") if msg_rows else None
        last_preview = (
            (last_content[:120] + "...") if last_content and len(last_content) > 120 else last_content
        )

        doc_id = updated_row.get("document_id")
        if doc_id is not None:
            try:
                doc_id = int(doc_id)
            except (ValueError, TypeError):
                doc_id = None

        return ChatConversationSummary(
            id=str(conversation_id),
            project_id=int(updated_row["project_id"]),
            user_id=str(updated_row["user_id"]) if updated_row.get("user_id") else None,
            title=str(updated_row.get("title") or "New Conversation"),
            scope=str(updated_row.get("scope") or "hybrid"),
            document_id=doc_id,
            element_class=updated_row.get("element_class"),
            is_pinned=bool(updated_row.get("is_pinned", False)),
            message_count=len(msg_rows),
            last_message_preview=last_preview,
            created_at=str(updated_row.get("created_at") or _utc_now_iso()),
            updated_at=str(updated_row.get("updated_at") or _utc_now_iso()),
        )

    def delete_conversation(
        self,
        conversation_id: str,
        project_id: int,
    ) -> bool:
        """Delete conversation and cascade its messages."""
        row = self._conversations.get(str(conversation_id))
        if not row or int(row.get("project_id", 0)) != int(project_id):
            return False

        # Delete messages first
        try:
            msgs = self._messages.rows_where("conversation_id = ?", [str(conversation_id)])
            for m in msgs:
                self._messages.delete(str(m["id"]))
        except Exception as exc:
            logger.warning("Error deleting chat messages for conversation %s: %s", conversation_id, exc)

        # Delete conversation
        self._conversations.delete(str(conversation_id))
        return True

    def save_messages(
        self,
        conversation_id: str,
        project_id: int,
        messages: list[ChatMessagePayload],
    ) -> None:
        """Persist or upsert message turns to a conversation."""
        row = self._conversations.get(str(conversation_id))
        if not row or int(row.get("project_id", 0)) != int(project_id):
            raise ValueError(f"Conversation {conversation_id} not found in project {project_id}")

        now = _utc_now_iso()
        for msg in messages:
            row_dict = {
                "id": str(msg.id),
                "conversation_id": str(conversation_id),
                "role": msg.role,
                "content": msg.content or "",
                "citations": json.dumps(msg.citations) if not isinstance(msg.citations, str) else msg.citations,
                "reasoning_steps": json.dumps(msg.reasoning_steps) if not isinstance(msg.reasoning_steps, str) else msg.reasoning_steps,
                "tool_calls": json.dumps(msg.tool_calls) if not isinstance(msg.tool_calls, str) else msg.tool_calls,
                "cypher_queries": json.dumps(msg.cypher_queries) if not isinstance(msg.cypher_queries, str) else msg.cypher_queries,
                "timestamp": msg.timestamp or "",
                "created_at": msg.created_at or now,
            }
            existing = self._messages.get(str(msg.id))
            if existing:
                self._messages.update(updates=row_dict, pk_values=str(msg.id))
            else:
                self._messages.insert(row_dict)

        # Touch conversation updated_at
        self._conversations.update(
            updates={"updated_at": now},
            pk_values=str(conversation_id),
        )


DEFAULT_COPILOT_SERVICE = CopilotService()
