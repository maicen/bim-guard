"""Tests for CopilotService conversation and message persistence."""

from app.modules.contracts.copilot import (
    ChatConversationCreatePayload,
    ChatConversationUpdatePayload,
    ChatMessagePayload,
)
from app.services.copilot_service import CopilotService


class DummyTable:
    """In-memory table simulating table adapter for unit testing."""

    def __init__(self, pk: str = "id"):
        self.pk = pk
        self._data: dict[str, dict] = {}

    def get(self, pk_val: str):
        return self._data.get(str(pk_val))

    def insert(self, row: dict):
        pk_val = str(row[self.pk])
        self._data[pk_val] = dict(row)

    def update(self, *args, updates: dict | None = None, pk_values: str | None = None, **kwargs):
        target_updates = dict(updates if updates is not None else (args[0] if args else {}))
        pk_val = str(pk_values if pk_values is not None else target_updates.get(self.pk))
        if pk_val in self._data:
            self._data[pk_val].update(target_updates)

    def delete(self, pk_val: str):
        self._data.pop(str(pk_val), None)

    def rows_where(self, where_clause: str, params: list):
        field = where_clause.split(" = ")[0].strip()
        target = params[0]
        results = []
        for r in self._data.values():
            if str(r.get(field)) == str(target):
                results.append(dict(r))
        return results


def test_copilot_service_crud_flow():
    conv_repo = DummyTable(pk="id")
    msg_repo = DummyTable(pk="id")
    svc = CopilotService(conversations_repo=conv_repo, messages_repo=msg_repo)

    # 1. Create conversation
    create_payload = ChatConversationCreatePayload(
        project_id=101,
        title="Fire Door Clearance Requirements",
        scope="hybrid",
        element_class="IfcDoor",
    )
    detail = svc.create_conversation(project_id=101, payload=create_payload, user_id="user_abc")
    assert detail.id is not None
    assert detail.title == "Fire Door Clearance Requirements"
    assert detail.project_id == 101
    assert detail.user_id == "user_abc"
    assert detail.messages == []

    # 2. List conversations
    summaries = svc.list_conversations(project_id=101, user_id="user_abc")
    assert len(summaries) == 1
    assert summaries[0].id == detail.id
    assert summaries[0].message_count == 0

    # 3. Save messages
    msg1 = ChatMessagePayload(
        id="msg_1",
        role="user",
        content="What is the minimum door width under IBC 1010?",
        timestamp="10:00 AM",
    )
    msg2 = ChatMessagePayload(
        id="msg_2",
        role="assistant",
        content="Under IBC 1010.1.1, the minimum clear width of each door opening shall be 32 inches.",
        citations=[{"id": "doc_1", "text": "IBC 1010.1.1"}],
        timestamp="10:01 AM",
    )
    svc.save_messages(conversation_id=detail.id, project_id=101, messages=[msg1, msg2])

    # 4. Fetch detail with messages
    fetched = svc.get_conversation(conversation_id=detail.id, project_id=101)
    assert fetched is not None
    assert len(fetched.messages) == 2
    assert fetched.messages[0].content == "What is the minimum door width under IBC 1010?"
    assert fetched.messages[1].role == "assistant"
    assert len(fetched.messages[1].citations) == 1

    # 5. Check summary preview and count
    summaries = svc.list_conversations(project_id=101)
    assert len(summaries) == 1
    assert summaries[0].message_count == 2
    assert "minimum clear width" in (summaries[0].last_message_preview or "")

    # 6. Update conversation (Pin and Rename)
    update_payload = ChatConversationUpdatePayload(
        title="IBC 1010 Door Widths",
        is_pinned=True,
    )
    updated = svc.update_conversation(
        conversation_id=detail.id,
        project_id=101,
        payload=update_payload,
    )
    assert updated is not None
    assert updated.title == "IBC 1010 Door Widths"
    assert updated.is_pinned is True

    # 7. Delete conversation
    deleted = svc.delete_conversation(conversation_id=detail.id, project_id=101)
    assert deleted is True
    assert svc.get_conversation(detail.id, 101) is None
    assert len(svc.list_conversations(101)) == 0


def test_copilot_service_with_in_memory_table_adapter():
    """Test CopilotService end-to-end with real InMemoryTableAdapter to prevent signature drift."""
    from app.services.persistence import PersistenceService

    db = PersistenceService.get_isolated_db()
    conv_table = PersistenceService.get_table(
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
        db=db,
    )
    msg_table = PersistenceService.get_table(
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
        db=db,
    )

    svc = CopilotService(conversations_repo=conv_table, messages_repo=msg_table)

    # Create
    detail = svc.create_conversation(
        project_id=5006,
        payload=ChatConversationCreatePayload(project_id=5006, title="New Conversation", scope="hybrid"),
        user_id="user-123",
    )
    assert detail.id is not None

    # Save messages
    msg1 = ChatMessagePayload(id="m1", role="user", content="Hello")
    msg2 = ChatMessagePayload(id="m2", role="assistant", content="Hi there")
    svc.save_messages(conversation_id=detail.id, project_id=5006, messages=[msg1, msg2])

    # Rename conversation
    updated = svc.update_conversation(
        conversation_id=detail.id,
        project_id=5006,
        payload=ChatConversationUpdatePayload(title="Renamed Topic", is_pinned=True),
    )
    assert updated is not None
    assert updated.title == "Renamed Topic"
    assert updated.is_pinned is True

    # Check detail
    fetched = svc.get_conversation(conversation_id=detail.id, project_id=5006)
    assert fetched is not None
    assert len(fetched.messages) == 2

    # Delete
    assert svc.delete_conversation(conversation_id=detail.id, project_id=5006) is True

