import logging

from fastapi import APIRouter, Depends, HTTPException

from app.ai.ipl_guard import IPL_RESTRICTION_MESSAGE, is_ipl_relevant
from app.ai.query_router.router import route_question
from app.api.error_logging import log_sanitized_exception, sanitize_sensitive_text
from app.api.rate_limit import rate_limit_chat
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.conversations.conversation_service import (
    add_message,
    create_conversation,
    get_conversation,
    get_conversation_messages,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Chat"])


def _try_langchain(question: str) -> str | None:
    """
    Attempt to answer via the LangChain tool-calling agent.
    Returns the answer string on success, or None to fall through to route_question().
    This function never raises — all exceptions are caught and logged.
    """
    try:
        from app.ai.llm.langchain_config import get_langchain_config
        cfg = get_langchain_config()
        if not cfg.enabled:
            return None

        from app.ai.langchain_agent import run_with_tools
        result = run_with_tools(question, cfg)
        if result and result.get("answer"):
            logger.info(
                "LangChain answered via %s (tools=%s, iterations=%d, elapsed=%.2fs).",
                result.get("provider", "unknown"),
                result.get("tools_called", []),
                result.get("iterations", 0),
                result.get("elapsed_seconds", 0.0),
            )
            return result["answer"]
    except Exception as exc:
        log_sanitized_exception(logger, "LangChain agent error (falling through to legacy router)", exc)
    return None


@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_chat),
):
    try:
        conversation_id = request.conversation_id
        trusted_history = None

        # 1. Resolve or verify existing conversation
        if conversation_id is not None:
            conv = get_conversation(conversation_id, current_user.id)
            if not conv:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found.",
                )
            raw_msgs = get_conversation_messages(conversation_id, current_user.id)
            if raw_msgs:
                trusted_history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in raw_msgs
                ]

        # 2. Determine conversation history to pass to IPL relevance guard
        # Prefer trusted database-stored history when conversation exists; fall back to client payload
        effective_history = (
            trusted_history
            if trusted_history is not None
            else (request.conversation_history or request.history)
        )

        # 3. Enforce IPL-only domain boundary before any tools, SQL, or RAG
        if not is_ipl_relevant(request.question, effective_history):
            # For out-of-domain questions:
            # - Do not create a conversation if one doesn't exist.
            # - Do not persist out-of-scope messages so stored context is not polluted.
            return ChatResponse(
                question=request.question,
                answer=IPL_RESTRICTION_MESSAGE,
                conversation_id=conversation_id,
            )

        # 4. If conversation_id is None, create a new conversation for this session
        if conversation_id is None:
            try:
                title = request.question[:50].strip() or "New Conversation"
                new_conv = create_conversation(user_id=current_user.id, title=title)
                conversation_id = new_conv["id"]
            except Exception as exc:
                logger.warning("Could not create persistent conversation: %s", exc)
                conversation_id = None

        # 5. Save the user message to persistent storage (if conversation exists)
        if conversation_id is not None:
            try:
                add_message(
                    conversation_id=conversation_id,
                    user_id=current_user.id,
                    role="user",
                    content=request.question,
                )
            except Exception as exc:
                logger.warning("Could not persist user message: %s", exc)

        # 6. Try LangChain tool-calling agent (no-op when LANGCHAIN_ENABLED=false)
        answer = _try_langchain(request.question)

        # 7. Fall back to deterministic SQL/RAG router (always works)
        if answer is None:
            answer = route_question(request.question)

        # 8. Only after successful generation, save the assistant message
        if conversation_id is not None:
            try:
                add_message(
                    conversation_id=conversation_id,
                    user_id=current_user.id,
                    role="assistant",
                    content=answer,
                )
            except Exception as exc:
                logger.warning("Could not persist assistant message: %s", exc)

        return ChatResponse(
            question=request.question,
            answer=answer,
            conversation_id=conversation_id,
        )

    except ValueError as exc:
        log_sanitized_exception(logger, "Validation error in POST /api/chat", exc)
        raise HTTPException(
            status_code=400,
            detail=sanitize_sensitive_text(str(exc)),
        ) from exc

    except Exception as exc:
        log_sanitized_exception(logger, "Unhandled error in POST /api/chat", exc)
        raise HTTPException(
            status_code=500,
            detail="Unable to process your question.",
        ) from exc
