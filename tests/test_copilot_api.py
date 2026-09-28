"""Integration tests for Graph-RAG Copilot API routes (/api/copilot)."""

from fastapi.testclient import TestClient

from app.api.dependencies import get_copilot_service
from app.api.projects import get_project_access_checker
from app.auth import CurrentUser, get_current_user
from app.main import app
from app.services.copilot_service import CopilotService
from tests.test_copilot_service import DummyTable


def test_copilot_api_endpoints():
    client = TestClient(app)

    # Use in-memory repositories for test isolation
    conv_repo = DummyTable(pk="id")
    msg_repo = DummyTable(pk="id")
    test_svc = CopilotService(conversations_repo=conv_repo, messages_repo=msg_repo)

    fake_user = CurrentUser(
        id="usr_test_123",
        email="test@bim-guard.xyz",
        claims={"role": "authenticated"},
    )

    app.dependency_overrides[get_project_access_checker] = lambda: lambda pid: None
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_copilot_service] = lambda: test_svc

    try:
        # 1. Create a conversation
        create_res = client.post(
            "/api/copilot/conversations",
            json={
                "project_id": 42,
                "title": "Corridor Travel Distance Audit",
                "scope": "hybrid",
            },
        )
        assert create_res.status_code == 201
        data = create_res.json()
        conv_id = data["id"]
        assert data["title"] == "Corridor Travel Distance Audit"
        assert data["project_id"] == 42
        assert data["messages"] == []

        # 2. List conversations
        list_res = client.get("/api/copilot/conversations?project_id=42")
        assert list_res.status_code == 200
        items = list_res.json()
        assert len(items) == 1
        assert items[0]["id"] == conv_id
        assert items[0]["message_count"] == 0

        # 3. Append messages
        msg_payload = {
            "messages": [
                {
                    "id": "msg_u1",
                    "role": "user",
                    "content": "What is the common path of travel limit?",
                    "timestamp": "12:00",
                },
                {
                    "id": "msg_a1",
                    "role": "assistant",
                    "content": "The common path of travel shall not exceed 75 feet in sprinklered buildings.",
                    "citations": [{"id": "c1", "text": "IBC 1006.2.1"}],
                    "timestamp": "12:01",
                },
            ]
        }
        msg_res = client.post(
            f"/api/copilot/conversations/{conv_id}/messages?project_id=42",
            json=msg_payload,
        )
        assert msg_res.status_code == 200
        assert msg_res.json()["saved"] == 2

        # 4. Get conversation detail
        get_res = client.get(f"/api/copilot/conversations/{conv_id}?project_id=42")
        assert get_res.status_code == 200
        detail = get_res.json()
        assert len(detail["messages"]) == 2
        assert detail["messages"][0]["role"] == "user"
        assert detail["messages"][1]["role"] == "assistant"

        # 5. Patch conversation (Pin & Rename)
        patch_res = client.patch(
            f"/api/copilot/conversations/{conv_id}?project_id=42",
            json={"title": "IBC Common Path of Travel", "is_pinned": True},
        )
        assert patch_res.status_code == 200
        patched = patch_res.json()
        assert patched["title"] == "IBC Common Path of Travel"
        assert patched["is_pinned"] is True

        # 6. Delete conversation
        del_res = client.delete(f"/api/copilot/conversations/{conv_id}?project_id=42")
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True

        # 7. Verify 404 after deletion
        get_after = client.get(f"/api/copilot/conversations/{conv_id}?project_id=42")
        assert get_after.status_code == 404

    finally:
        app.dependency_overrides.pop(get_project_access_checker, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_copilot_service, None)
