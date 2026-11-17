import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.error_logging import log_sanitized_exception, sanitize_sensitive_text
from app.api.rate_limit import rate_limit_chat
from app.schemas.chat import ChatRequest, ChatResponse
from app.ai.query_router.router import route_question

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
    dependencies=[Depends(rate_limit_chat)],
)
def chat(request: ChatRequest):
    try:
        # 1. Try LangChain tool-calling agent (no-op when LANGCHAIN_ENABLED=false)
        answer = _try_langchain(request.question)

        # 2. Fall back to deterministic SQL/RAG router (always works)
        if answer is None:
            answer = route_question(request.question)

        return ChatResponse(
            question=request.question,
            answer=answer,
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
