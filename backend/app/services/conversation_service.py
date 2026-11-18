"""Conversation Service - handles persistent conversation history and message management."""

from uuid import UUID
from sqlalchemy.orm import Session

from app.crud.conversation import (
    create_conversation,
    get_conversation_by_id,
    get_user_conversations,
    update_conversation_title,
    delete_conversation,
)
from app.crud.message import (
    create_message,
    get_message_by_id,
    get_conversation_messages,
    delete_message,
)
from app.schemas.conversation import ConversationCreate, MessageCreate


def create_user_conversation(
    db: Session,
    conversation_data: ConversationCreate,
    user_id: UUID,
):
    """Create a conversation for a user's project."""
    return create_conversation(
        db=db,
        conversation_data=conversation_data,
        user_id=user_id,
    )


def get_conversation(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
):
    """Get a conversation by ID with ownership check."""
    return get_conversation_by_id(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id,
    )


def list_user_conversations(
    db: Session,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
):
    """List all conversations for a user."""
    return get_user_conversations(
        db=db,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )


def update_conversation(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
    title: str,
):
    """Update a conversation title."""
    return update_conversation_title(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id,
        title=title,
    )


def delete_user_conversation(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
) -> bool:
    """Delete a user's conversation."""
    return delete_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id,
    )


def add_message(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
    message_data: MessageCreate,
    role: str = "user",
    agent_name: str | None = None,
):
    """Add a message to a conversation."""
    return create_message(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id,
        message_data=message_data,
        role=role,
        agent_name=agent_name,
    )


def get_message(
    db: Session,
    message_id: UUID,
    user_id: UUID,
):
    """Get a message by ID with ownership check."""
    return get_message_by_id(
        db=db,
        message_id=message_id,
        user_id=user_id,
    )


def list_conversation_messages(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
):
    """List messages from a conversation."""
    return get_conversation_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )


def remove_message(
    db: Session,
    message_id: UUID,
    user_id: UUID,
) -> bool:
    """Delete a message."""
    return delete_message(
        db=db,
        message_id=message_id,
        user_id=user_id,
    )