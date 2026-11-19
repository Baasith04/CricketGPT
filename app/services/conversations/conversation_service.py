"""
conversation_service.py — Service layer for persistent conversations and chat messages.

Encapsulates all database interactions for conversations and messages using
parameterized queries through psycopg 3, strictly enforcing user ownership.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def create_conversation(
    user_id: UUID,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new conversation record for the authenticated user.
    """
    clean_title = (title or "").strip() or "New Conversation"
    if len(clean_title) > 200:
        clean_title = clean_title[:197] + "..."

    query = """
        INSERT INTO public.conversations (user_id, title)
        VALUES (%s, %s)
        RETURNING id, user_id, title, created_at, updated_at;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, clean_title))
            row = cur.fetchone()
            conn.commit()
            if not row:
                raise RuntimeError("Failed to create conversation.")
            columns = [col.name for col in cur.description]
            return dict(zip(columns, row))


def get_conversation(
    conversation_id: UUID,
    user_id: UUID,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single conversation record strictly owned by user_id.
    Returns None if not found or if owned by another user.
    """
    query = """
        SELECT id, user_id, title, created_at, updated_at
        FROM public.conversations
        WHERE id = %s AND user_id = %s;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (conversation_id, user_id))
            row = cur.fetchone()
            if not row:
                return None
            columns = [col.name for col in cur.description]
            return dict(zip(columns, row))


def list_conversations(
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    List all conversations owned by user_id, ordered by most recently updated.
    """
    bounded_limit = max(1, min(limit, 100))
    bounded_offset = max(0, offset)

    query = """
        SELECT id, user_id, title, created_at, updated_at
        FROM public.conversations
        WHERE user_id = %s
        ORDER BY updated_at DESC
        LIMIT %s OFFSET %s;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, bounded_limit, bounded_offset))
            columns = [col.name for col in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def update_conversation_title(
    conversation_id: UUID,
    user_id: UUID,
    title: str,
) -> Optional[Dict[str, Any]]:
    """
    Update the title of a conversation owned by user_id.
    """
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("Conversation title cannot be empty.")
    if len(clean_title) > 200:
        clean_title = clean_title[:197] + "..."

    query = """
        UPDATE public.conversations
        SET title = %s, updated_at = timezone('utc'::text, now())
        WHERE id = %s AND user_id = %s
        RETURNING id, user_id, title, created_at, updated_at;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (clean_title, conversation_id, user_id))
            row = cur.fetchone()
            conn.commit()
            if not row:
                return None
            columns = [col.name for col in cur.description]
            return dict(zip(columns, row))


def delete_conversation(
    conversation_id: UUID,
    user_id: UUID,
) -> bool:
    """
    Delete a conversation and cascade-delete its messages.
    Returns True if deleted, False if not found or unauthorized.
    """
    query = """
        DELETE FROM public.conversations
        WHERE id = %s AND user_id = %s
        RETURNING id;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (conversation_id, user_id))
            row = cur.fetchone()
            conn.commit()
            return row is not None


def add_message(
    conversation_id: UUID,
    user_id: UUID,
    role: str,
    content: str,
) -> Dict[str, Any]:
    """
    Add a new message to a conversation.
    Strictly verifies conversation ownership before insertion.
    """
    if role not in ("user", "assistant"):
        raise ValueError(f"Invalid message role '{role}'. Must be 'user' or 'assistant'.")
    clean_content = content.strip()
    if not clean_content:
        raise ValueError("Message content cannot be empty.")

    # 1. Verify conversation ownership
    conv_check_query = """
        SELECT id FROM public.conversations
        WHERE id = %s AND user_id = %s;
    """
    insert_query = """
        INSERT INTO public.messages (conversation_id, user_id, role, content)
        VALUES (%s, %s, %s, %s)
        RETURNING id, conversation_id, user_id, role, content, created_at;
    """
    update_conv_query = """
        UPDATE public.conversations
        SET updated_at = timezone('utc'::text, now())
        WHERE id = %s AND user_id = %s;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(conv_check_query, (conversation_id, user_id))
            if not cur.fetchone():
                raise PermissionError("Conversation not found or access denied.")

            cur.execute(insert_query, (conversation_id, user_id, role, clean_content))
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Failed to insert message.")
            columns = [col.name for col in cur.description]
            msg_dict = dict(zip(columns, row))

            cur.execute(update_conv_query, (conversation_id, user_id))
            conn.commit()
            return msg_dict


def get_conversation_messages(
    conversation_id: UUID,
    user_id: UUID,
    limit: int = 100,
) -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve messages for a conversation ordered chronologically.
    Returns None if the conversation is not found or not owned by user_id.
    """
    # 1. Verify ownership
    conv_check_query = """
        SELECT id FROM public.conversations
        WHERE id = %s AND user_id = %s;
    """
    msg_query = """
        SELECT id, conversation_id, user_id, role, content, created_at
        FROM public.messages
        WHERE conversation_id = %s AND user_id = %s
        ORDER BY created_at ASC
        LIMIT %s;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(conv_check_query, (conversation_id, user_id))
            if not cur.fetchone():
                return None

            cur.execute(msg_query, (conversation_id, user_id, max(1, min(limit, 500))))
            columns = [col.name for col in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
