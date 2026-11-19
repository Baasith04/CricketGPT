"""
app/api/routes/conversations.py — Conversation Management API Endpoints.

Provides authenticated endpoints for creating, listing, viewing, updating,
and deleting conversations and retrieving their messages.
"""
from __future__ import annotations

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.error_logging import log_sanitized_exception
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.conversations import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationUpdate,
    DeleteConversationResponse,
    MessageResponse,
)
from app.services.conversations.conversation_service import (
    create_conversation,
    delete_conversation,
    get_conversation,
    get_conversation_messages,
    list_conversations,
    update_conversation_title,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
)
def create_new_conversation(
    payload: ConversationCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        conv = create_conversation(user_id=current_user.id, title=payload.title)
        return ConversationResponse(**conv)
    except Exception as exc:
        log_sanitized_exception(logger, "Failed to create conversation", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create conversation.",
        ) from exc


@router.get(
    "",
    response_model=List[ConversationResponse],
    summary="List all conversations for the authenticated user",
)
def get_user_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        convs = list_conversations(user_id=current_user.id, limit=limit, offset=offset)
        return [ConversationResponse(**c) for c in convs]
    except Exception as exc:
        log_sanitized_exception(logger, "Failed to list conversations", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve conversations.",
        ) from exc


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Retrieve a conversation and its messages",
)
def get_single_conversation(
    conversation_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        conv = get_conversation(conversation_id=conversation_id, user_id=current_user.id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )

        raw_messages = get_conversation_messages(
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
        messages = [MessageResponse(**m) for m in (raw_messages or [])]

        return ConversationDetailResponse(
            id=conv["id"],
            user_id=conv["user_id"],
            title=conv["title"],
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
            messages=messages,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log_sanitized_exception(logger, f"Failed to get conversation {conversation_id}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve conversation.",
        ) from exc


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update conversation title",
)
def update_title(
    conversation_id: UUID,
    payload: ConversationUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        updated = update_conversation_title(
            conversation_id=conversation_id,
            user_id=current_user.id,
            title=payload.title,
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
        return ConversationResponse(**updated)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log_sanitized_exception(logger, f"Failed to update conversation {conversation_id}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update conversation.",
        ) from exc


@router.delete(
    "/{conversation_id}",
    response_model=DeleteConversationResponse,
    summary="Delete a conversation and its messages",
)
def remove_conversation(
    conversation_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        deleted = delete_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
        return DeleteConversationResponse(status="deleted", id=conversation_id)
    except HTTPException:
        raise
    except Exception as exc:
        log_sanitized_exception(logger, f"Failed to delete conversation {conversation_id}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete conversation.",
        ) from exc
