from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.ai.query_router.router import route_question

router = APIRouter(prefix="/api", tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        answer = route_question(request.question)

        return ChatResponse(
            question=request.question,
            answer=answer,
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to process your question.",
        )