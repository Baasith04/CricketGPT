import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.error_logging import log_sanitized_exception, sanitize_sensitive_text
from app.api.rate_limit import rate_limit_chat
from app.schemas.chat import ChatRequest, ChatResponse
from app.ai.query_router.router import route_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(rate_limit_chat)],
)
def chat(request: ChatRequest):
    try:
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
