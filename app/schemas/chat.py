from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="Optional ID of an existing conversation to continue.",
    )
    conversation_history: Optional[List[Union[ChatMessage, Dict[str, Any], str]]] = Field(
        default=None,
        description="Optional recent conversation history for contextual follow-up questions.",
    )
    history: Optional[List[Union[ChatMessage, Dict[str, Any], str]]] = Field(
        default=None,
        description="Alias for conversation_history.",
    )


class ChatResponse(BaseModel):
    question: str
    answer: str
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="ID of the conversation this message belongs to.",
    )
