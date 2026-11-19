"""
tests/api/test_stage3_ipl_guard.py — Stage 3 IPL Domain Enforcement Tests.

Covers:
1. IPL question is allowed.
2. IPL team question is allowed.
3. IPL statistics question is allowed.
4. International cricket question is rejected.
5. Football question is rejected.
6. Other league question is rejected.
7. General knowledge question is rejected.
8. IPL follow-up is allowed using existing context.
9. Unrelated new question is rejected despite previous IPL context.
10. Rejected question does not invoke SQL.
11. Rejected question does not invoke RAG.
12. Rejected question does not invoke the main answer-generation chain.
13. Rejected question returns HTTP 200.
14. Existing authentication still requires a valid JWT.
15. Existing IPL chat functionality remains unaffected.
"""

import uuid
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from app.ai.ipl_guard import IPL_RESTRICTION_MESSAGE, is_ipl_relevant
from app.api.rate_limit import reset_rate_limiter
from app.core.security import AuthenticatedUser, get_current_user
from app.main import app


@pytest.fixture
def auth_client():
    """Client fixture with a verified AuthenticatedUser dependency override and clean rate limiter."""
    reset_rate_limiter()
    user = AuthenticatedUser(
        id=uuid.uuid4(),
        email="ipl_tester@cricketgpt.com",
        role="authenticated",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_current_user, None)
    reset_rate_limiter()


@pytest.fixture
def unauth_client():
    """Client fixture without any dependency overrides (real auth path)."""
    reset_rate_limiter()
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as client:
        yield client
    reset_rate_limiter()


# ---------------------------------------------------------------------------
# 1. IPL Question is Allowed
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_ipl_question_allowed(mock_route, auth_client: TestClient):
    mock_route.return_value = "Kolkata Knight Riders won IPL 2024."

    response = auth_client.post("/api/chat", json={"question": "Who won IPL 2024?"})

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "Who won IPL 2024?"
    assert data["answer"] == "Kolkata Knight Riders won IPL 2024."
    mock_route.assert_called_once_with("Who won IPL 2024?")


# ---------------------------------------------------------------------------
# 2. IPL Team Question is Allowed
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_ipl_team_question_allowed(mock_route, auth_client: TestClient):
    mock_route.return_value = "Ruturaj Gaikwad is the captain of Chennai Super Kings."

    response = auth_client.post(
        "/api/chat",
        json={"question": "Who is the captain of Chennai Super Kings?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Ruturaj Gaikwad is the captain of Chennai Super Kings."
    mock_route.assert_called_once()


# ---------------------------------------------------------------------------
# 3. IPL Statistics Question is Allowed
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_ipl_statistics_question_allowed(mock_route, auth_client: TestClient):
    mock_route.return_value = "Shubman Gill won the Orange Cap in 2023 with 890 runs."

    response = auth_client.post(
        "/api/chat",
        json={"question": "Who won the Orange Cap in 2023?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Shubman Gill won the Orange Cap in 2023 with 890 runs."
    mock_route.assert_called_once()


# ---------------------------------------------------------------------------
# 4. International Cricket Question is Rejected
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_international_cricket_question_rejected(mock_route, auth_client: TestClient):
    queries = [
        "Who has the most centuries in Test cricket?",
        "How many runs did Virat Kohli score in ODI cricket?",
        "Who won the 2023 Cricket World Cup?",
    ]

    for q in queries:
        response = auth_client.post("/api/chat", json={"question": q})
        assert response.status_code == 200
        data = response.json()
        assert data["question"] == q
        assert data["answer"] == IPL_RESTRICTION_MESSAGE

    mock_route.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Football Question is Rejected
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_football_question_rejected(mock_route, auth_client: TestClient):
    queries = [
        "Who won the FIFA World Cup 2022?",
        "How many goals has Messi scored?",
        "Which team won the Premier League?",
    ]

    for q in queries:
        response = auth_client.post("/api/chat", json={"question": q})
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == IPL_RESTRICTION_MESSAGE

    mock_route.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Other League Question is Rejected
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_other_league_question_rejected(mock_route, auth_client: TestClient):
    queries = [
        "Who won BBL 2023?",
        "Who has the most runs in PSL?",
        "How many teams play in The Hundred?",
    ]

    for q in queries:
        response = auth_client.post("/api/chat", json={"question": q})
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == IPL_RESTRICTION_MESSAGE

    mock_route.assert_not_called()


# ---------------------------------------------------------------------------
# 7. General Knowledge Question is Rejected
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_general_knowledge_question_rejected(mock_route, auth_client: TestClient):
    queries = [
        "What is the capital of France?",
        "Explain quicksort in Python",
        "How does photosynthesis work?",
    ]

    for q in queries:
        response = auth_client.post("/api/chat", json={"question": q})
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == IPL_RESTRICTION_MESSAGE

    mock_route.assert_not_called()


# ---------------------------------------------------------------------------
# 8. IPL Follow-up is Allowed Using Existing Context
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_ipl_followup_allowed_using_existing_context(mock_route, auth_client: TestClient):
    mock_route.return_value = "His strike rate was 154.7 in IPL 2025."

    history = [
        {"role": "user", "content": "Who scored the most runs in IPL 2025?"},
        {"role": "assistant", "content": "Virat Kohli scored 741 runs in IPL 2025."},
    ]

    response = auth_client.post(
        "/api/chat",
        json={
            "question": "What was his strike rate?",
            "conversation_history": history,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "His strike rate was 154.7 in IPL 2025."
    mock_route.assert_called_once_with("What was his strike rate?")


# ---------------------------------------------------------------------------
# 9. Unrelated New Question is Rejected Despite Previous IPL Context
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_unrelated_new_question_rejected_despite_previous_ipl_context(
    mock_route, auth_client: TestClient
):
    history = [
        {"role": "user", "content": "Which team won IPL 2024?"},
        {"role": "assistant", "content": "Kolkata Knight Riders won IPL 2024."},
    ]

    response = auth_client.post(
        "/api/chat",
        json={
            "question": "Who won the FIFA World Cup?",
            "conversation_history": history,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == IPL_RESTRICTION_MESSAGE
    mock_route.assert_not_called()


# ---------------------------------------------------------------------------
# 10. Rejected Question Does Not Invoke SQL
# ---------------------------------------------------------------------------

@patch("app.database.connection.get_db_connection")
@patch("app.api.routes.chat.route_question")
def test_rejected_question_does_not_invoke_sql(mock_route, mock_db, auth_client: TestClient):
    response = auth_client.post(
        "/api/chat",
        json={"question": "How many runs did Virat Kohli score in Test cricket?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == IPL_RESTRICTION_MESSAGE
    mock_db.assert_not_called()
    mock_route.assert_not_called()


# ---------------------------------------------------------------------------
# 11. Rejected Question Does Not Invoke RAG
# ---------------------------------------------------------------------------

@patch("app.ai.answer_service.answer_rag_narrative_question")
@patch("app.rag.retrieval.hybrid_retriever.hybrid_retrieve")
@patch("app.api.routes.chat.route_question")
def test_rejected_question_does_not_invoke_rag(
    mock_route, mock_rag_retrieve, mock_rag_answer, auth_client: TestClient
):
    response = auth_client.post(
        "/api/chat",
        json={"question": "What is the capital of Spain?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == IPL_RESTRICTION_MESSAGE
    mock_rag_answer.assert_not_called()
    mock_rag_retrieve.assert_not_called()
    mock_route.assert_not_called()


# ---------------------------------------------------------------------------
# 12. Rejected Question Does Not Invoke Main Answer Generation Chain
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat._try_langchain")
@patch("app.api.routes.chat.route_question")
def test_rejected_question_does_not_invoke_main_chain(
    mock_route, mock_langchain, auth_client: TestClient
):
    response = auth_client.post(
        "/api/chat",
        json={"question": "Who won BBL 2023?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == IPL_RESTRICTION_MESSAGE
    mock_langchain.assert_not_called()
    mock_route.assert_not_called()


# ---------------------------------------------------------------------------
# 13. Rejected Question Returns HTTP 200
# ---------------------------------------------------------------------------

def test_rejected_question_returns_http_200(auth_client: TestClient):
    response = auth_client.post(
        "/api/chat",
        json={"question": "Explain binary search in Python"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "Explain binary search in Python"
    assert data["answer"] == IPL_RESTRICTION_MESSAGE


# ---------------------------------------------------------------------------
# 14. Existing Authentication Still Requires a Valid JWT
# ---------------------------------------------------------------------------

def test_existing_authentication_still_requires_valid_jwt(unauth_client: TestClient):
    # Unauthenticated request for an IPL question
    ipl_res = unauth_client.post("/api/chat", json={"question": "Who won IPL 2024?"})
    assert ipl_res.status_code == 401

    # Unauthenticated request for a non-IPL question
    non_ipl_res = unauth_client.post(
        "/api/chat", json={"question": "Who won the FIFA World Cup?"}
    )
    assert non_ipl_res.status_code == 401


# ---------------------------------------------------------------------------
# 15. Existing IPL Chat Functionality Remains Unaffected
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_existing_ipl_chat_functionality_unaffected(mock_route, auth_client: TestClient):
    mock_route.return_value = "Chennai Super Kings have won 5 IPL titles."

    response = auth_client.post(
        "/api/chat",
        json={"question": "How many titles have CSK won?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Chennai Super Kings have won 5 IPL titles."
    mock_route.assert_called_once()


# ---------------------------------------------------------------------------
# 16. Unit Tests: Classifier Failure Handling and Safety
# ---------------------------------------------------------------------------

def test_guard_empty_question_rejected():
    assert is_ipl_relevant("") is False
    assert is_ipl_relevant("   ") is False


@patch("app.ai.llm.client.generate_response")
def test_guard_llm_failure_fails_closed(mock_llm):
    """Ensure that when LLM classifier raises an exception, the guard fails closed (False)."""
    mock_llm.side_effect = RuntimeError("All configured AI providers failed")

    # Ambiguous question that triggers LLM classification
    result = is_ipl_relevant("Who is considered the greatest player of all time?")
    assert result is False


@patch("app.ai.llm.client.generate_response")
def test_guard_llm_classifier_yes_allowed(mock_llm):
    """Ensure that when LLM classifier confirms YES, question is allowed."""
    mock_llm.return_value = "YES"

    result = is_ipl_relevant("Tell me about the 2008 final")
    assert result is True


def test_guard_handles_pydantic_and_dict_history():
    from app.schemas.chat import ChatMessage

    history_pydantic = [
        ChatMessage(role="user", content="Who won IPL 2024?"),
        ChatMessage(role="assistant", content="KKR won IPL 2024."),
    ]
    assert is_ipl_relevant("Who was their captain?", history_pydantic) is True

    history_strings = [
        "Who won IPL 2024?",
        "KKR won IPL 2024.",
    ]
    assert is_ipl_relevant("Who was their captain?", history_strings) is True

