"""
tests/api/test_stage4_conversations.py — Stage 4 Persistent Conversations & Chat History Tests.

Covers:
1. Create conversation.
2. List only the authenticated user's conversations.
3. Retrieve conversation messages.
4. Save user and assistant messages.
5. Delete conversation.
6. Prevent accessing another user's conversation.
7. Prevent inserting messages into another user's conversation.
8. Chat creates a conversation when no conversation_id is supplied.
9. Chat continues an existing conversation.
10. Previous stored IPL context supports follow-up questions.
11. Existing IPL-only guard still rejects unrelated questions.
12. JWT authentication remains enforced.
13. Public cricket statistics endpoints remain accessible.
14. Failed LLM responses do not create misleading assistant messages.
15. Existing chat functionality remains unaffected.
"""

from datetime import datetime, timezone
import uuid
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from app.ai.ipl_guard import IPL_RESTRICTION_MESSAGE
from app.api.rate_limit import reset_rate_limiter
from app.core.security import AuthenticatedUser, get_current_user
from app.main import app
from app.services.conversations.conversation_service import add_message


@pytest.fixture
def auth_user():
    return AuthenticatedUser(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        email="stage4_tester@cricketgpt.com",
        role="authenticated",
    )


@pytest.fixture
def other_user():
    return AuthenticatedUser(
        id=UUID("99999999-9999-9999-9999-999999999999"),
        email="attacker@cricketgpt.com",
        role="authenticated",
    )


@pytest.fixture
def auth_client(auth_user):
    reset_rate_limiter()
    app.dependency_overrides[get_current_user] = lambda: auth_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_current_user, None)
    reset_rate_limiter()


@pytest.fixture
def unauth_client():
    reset_rate_limiter()
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as client:
        yield client
    reset_rate_limiter()


# ---------------------------------------------------------------------------
# 1. Create Conversation
# ---------------------------------------------------------------------------

@patch("app.api.routes.conversations.create_conversation")
def test_create_conversation(mock_create, auth_client: TestClient, auth_user):
    conv_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_create.return_value = {
        "id": conv_id,
        "user_id": auth_user.id,
        "title": "My IPL Chat",
        "created_at": now,
        "updated_at": now,
    }

    response = auth_client.post("/api/conversations", json={"title": "My IPL Chat"})

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == str(conv_id)
    assert data["title"] == "My IPL Chat"
    mock_create.assert_called_once_with(user_id=auth_user.id, title="My IPL Chat")


# ---------------------------------------------------------------------------
# 2. List Only Authenticated User's Conversations
# ---------------------------------------------------------------------------

@patch("app.api.routes.conversations.list_conversations")
def test_list_only_authenticated_users_conversations(mock_list, auth_client: TestClient, auth_user):
    now = datetime.now(timezone.utc)
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()
    mock_list.return_value = [
        {"id": c1_id, "user_id": auth_user.id, "title": "IPL 2024", "created_at": now, "updated_at": now},
        {"id": c2_id, "user_id": auth_user.id, "title": "CSK Stats", "created_at": now, "updated_at": now},
    ]

    response = auth_client.get("/api/conversations")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "IPL 2024"
    assert data[1]["title"] == "CSK Stats"
    mock_list.assert_called_once_with(user_id=auth_user.id, limit=50, offset=0)


# ---------------------------------------------------------------------------
# 3. Retrieve Conversation Messages
# ---------------------------------------------------------------------------

@patch("app.api.routes.conversations.get_conversation")
@patch("app.api.routes.conversations.get_conversation_messages")
def test_retrieve_conversation_messages(mock_msgs, mock_conv, auth_client: TestClient, auth_user):
    conv_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_conv.return_value = {
        "id": conv_id,
        "user_id": auth_user.id,
        "title": "IPL 2024",
        "created_at": now,
        "updated_at": now,
    }
    mock_msgs.return_value = [
        {
            "id": uuid.uuid4(),
            "conversation_id": conv_id,
            "user_id": auth_user.id,
            "role": "user",
            "content": "Who won IPL 2024?",
            "created_at": now,
        },
        {
            "id": uuid.uuid4(),
            "conversation_id": conv_id,
            "user_id": auth_user.id,
            "role": "assistant",
            "content": "KKR won IPL 2024.",
            "created_at": now,
        },
    ]

    response = auth_client.get(f"/api/conversations/{conv_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(conv_id)
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# 4. Save User and Assistant Messages (Service Level Verification)
# ---------------------------------------------------------------------------

@patch("app.services.conversations.conversation_service.get_db_connection")
def test_save_user_and_assistant_messages(mock_get_conn, auth_user):
    conv_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # 1. Ownership check returns row, insert returns row
    mock_cur.fetchone.side_effect = [
        (conv_id,),  # conv ownership check
        (msg_id, conv_id, auth_user.id, "user", "Who won IPL 2024?", now),  # insert returning
    ]
    cols = []
    for col_name in ["id", "conversation_id", "user_id", "role", "content", "created_at"]:
        c = MagicMock()
        c.name = col_name
        cols.append(c)
    mock_cur.description = cols

    res = add_message(conv_id, auth_user.id, "user", "Who won IPL 2024?")
    assert res["id"] == msg_id
    assert res["role"] == "user"
    mock_conn.commit.assert_called()


# ---------------------------------------------------------------------------
# 5. Delete Conversation
# ---------------------------------------------------------------------------

@patch("app.api.routes.conversations.delete_conversation")
def test_delete_conversation(mock_delete, auth_client: TestClient, auth_user):
    conv_id = uuid.uuid4()
    mock_delete.return_value = True

    response = auth_client.delete(f"/api/conversations/{conv_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    mock_delete.assert_called_once_with(conversation_id=conv_id, user_id=auth_user.id)


# ---------------------------------------------------------------------------
# 6. Prevent Accessing Another User's Conversation
# ---------------------------------------------------------------------------

@patch("app.api.routes.conversations.get_conversation")
def test_prevent_accessing_another_users_conversation(mock_conv, auth_client: TestClient):
    conv_id = uuid.uuid4()
    # Simulates query returning None because user_id does not match
    mock_conv.return_value = None

    response = auth_client.get(f"/api/conversations/{conv_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."


# ---------------------------------------------------------------------------
# 7. Prevent Inserting Messages into Another User's Conversation
# ---------------------------------------------------------------------------

@patch("app.services.conversations.conversation_service.get_db_connection")
def test_prevent_inserting_messages_into_another_users_conversation(mock_get_conn, other_user):
    conv_id = uuid.uuid4()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Ownership check returns None because conversation belongs to someone else
    mock_cur.fetchone.return_value = None

    with pytest.raises(PermissionError, match="Conversation not found or access denied"):
        add_message(conv_id, other_user.id, "user", "Attempting hijack")


# ---------------------------------------------------------------------------
# 8. Chat Creates a Conversation When No conversation_id is Supplied
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.create_conversation")
@patch("app.api.routes.chat.add_message")
@patch("app.api.routes.chat.route_question")
def test_chat_creates_conversation_when_no_conversation_id_supplied(
    mock_route, mock_add_msg, mock_create_conv, auth_client: TestClient, auth_user
):
    new_conv_id = uuid.uuid4()
    mock_create_conv.return_value = {"id": new_conv_id}
    mock_route.return_value = "Kolkata Knight Riders won IPL 2024."

    response = auth_client.post("/api/chat", json={"question": "Who won IPL 2024?"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Kolkata Knight Riders won IPL 2024."
    assert data["conversation_id"] == str(new_conv_id)
    mock_create_conv.assert_called_once()
    assert mock_add_msg.call_count == 2  # 1 user + 1 assistant


# ---------------------------------------------------------------------------
# 9. Chat Continues an Existing Conversation
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.get_conversation")
@patch("app.api.routes.chat.get_conversation_messages")
@patch("app.api.routes.chat.add_message")
@patch("app.api.routes.chat.route_question")
def test_chat_continues_existing_conversation(
    mock_route, mock_add_msg, mock_msgs, mock_conv, auth_client: TestClient, auth_user
):
    conv_id = uuid.uuid4()
    mock_conv.return_value = {"id": conv_id, "user_id": auth_user.id, "title": "IPL 2024"}
    mock_msgs.return_value = [
        {"role": "user", "content": "Which team won IPL 2024?"},
        {"role": "assistant", "content": "Kolkata Knight Riders won IPL 2024."},
    ]
    mock_route.return_value = "Shreyas Iyer was their captain."

    response = auth_client.post(
        "/api/chat",
        json={"question": "Who was their captain?", "conversation_id": str(conv_id)},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == str(conv_id)
    assert data["answer"] == "Shreyas Iyer was their captain."
    assert mock_add_msg.call_count == 2


# ---------------------------------------------------------------------------
# 10. Previous Stored IPL Context Supports Follow-up Questions
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.get_conversation")
@patch("app.api.routes.chat.get_conversation_messages")
@patch("app.api.routes.chat.add_message")
@patch("app.api.routes.chat.route_question")
def test_previous_stored_ipl_context_supports_followup_questions(
    mock_route, mock_add_msg, mock_msgs, mock_conv, auth_client: TestClient, auth_user
):
    conv_id = uuid.uuid4()
    mock_conv.return_value = {"id": conv_id, "user_id": auth_user.id}
    # Stored context in DB
    mock_msgs.return_value = [
        {"role": "user", "content": "Who scored the most runs in IPL 2025?"},
        {"role": "assistant", "content": "Virat Kohli scored 741 runs in IPL 2025."},
    ]
    mock_route.return_value = "His strike rate was 154.7."

    # Question does not mention IPL, but stored history does
    response = auth_client.post(
        "/api/chat",
        json={"question": "What was his strike rate?", "conversation_id": str(conv_id)},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "His strike rate was 154.7."
    mock_route.assert_called_once_with("What was his strike rate?")


# ---------------------------------------------------------------------------
# 11. Existing IPL-Only Guard Still Rejects Unrelated Questions
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.get_conversation")
@patch("app.api.routes.chat.get_conversation_messages")
@patch("app.api.routes.chat.add_message")
@patch("app.api.routes.chat.route_question")
def test_existing_ipl_only_guard_still_rejects_unrelated_questions(
    mock_route, mock_add_msg, mock_msgs, mock_conv, auth_client: TestClient, auth_user
):
    conv_id = uuid.uuid4()
    mock_conv.return_value = {"id": conv_id, "user_id": auth_user.id}
    mock_msgs.return_value = [
        {"role": "user", "content": "Who scored the most runs in IPL 2025?"},
        {"role": "assistant", "content": "Virat Kohli scored 741 runs."},
    ]

    response = auth_client.post(
        "/api/chat",
        json={"question": "Who won the FIFA World Cup?", "conversation_id": str(conv_id)},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == IPL_RESTRICTION_MESSAGE
    mock_route.assert_not_called()
    # Out of scope messages must NOT be saved to messages table
    mock_add_msg.assert_not_called()


# ---------------------------------------------------------------------------
# 12. JWT Authentication Remains Enforced
# ---------------------------------------------------------------------------

def test_jwt_authentication_remains_enforced(unauth_client: TestClient):
    conv_id = uuid.uuid4()
    assert unauth_client.get("/api/conversations").status_code == 401
    assert unauth_client.post("/api/conversations", json={"title": "Test"}).status_code == 401
    assert unauth_client.get(f"/api/conversations/{conv_id}").status_code == 401
    assert unauth_client.delete(f"/api/conversations/{conv_id}").status_code == 401
    assert unauth_client.post("/api/chat", json={"question": "Who won IPL 2024?"}).status_code == 401


# ---------------------------------------------------------------------------
# 13. Public Cricket Statistics Endpoints Remain Accessible
# ---------------------------------------------------------------------------

def test_public_cricket_statistics_endpoints_remain_accessible(unauth_client: TestClient):
    # Cricket endpoints should not require JWT
    assert unauth_client.get("/api/matches/1").status_code != 401
    assert unauth_client.get("/api/teams/csk").status_code != 401
    assert unauth_client.get("/api/leaderboards/batting").status_code != 401


# ---------------------------------------------------------------------------
# 14. Failed LLM Responses Do Not Create Misleading Assistant Messages
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.create_conversation")
@patch("app.api.routes.chat.add_message")
@patch("app.api.routes.chat.route_question")
def test_failed_llm_responses_do_not_create_misleading_assistant_messages(
    mock_route, mock_add_msg, mock_create_conv, auth_client: TestClient, auth_user
):
    conv_id = uuid.uuid4()
    mock_create_conv.return_value = {"id": conv_id}
    # Simulate LLM failure
    mock_route.side_effect = RuntimeError("AI provider timeout")

    response = auth_client.post("/api/chat", json={"question": "Who won IPL 2024?"})

    assert response.status_code == 500
    # User message was saved, but assistant message was NEVER saved
    for call in mock_add_msg.call_args_list:
        assert call.kwargs.get("role") != "assistant"


# ---------------------------------------------------------------------------
# 15. Existing Chat Functionality Remains Unaffected
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.create_conversation")
@patch("app.api.routes.chat.add_message")
@patch("app.api.routes.chat.route_question")
def test_existing_chat_functionality_remains_unaffected(
    mock_route, mock_add_msg, mock_create_conv, auth_client: TestClient
):
    conv_id = uuid.uuid4()
    mock_create_conv.return_value = {"id": conv_id}
    mock_route.return_value = "Sunrisers Hyderabad scored 287 against RCB in 2024."

    response = auth_client.post(
        "/api/chat",
        json={"question": "Highest team score in IPL 2024?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "Highest team score in IPL 2024?"
    assert data["answer"] == "Sunrisers Hyderabad scored 287 against RCB in 2024."
    assert data["conversation_id"] == str(conv_id)
