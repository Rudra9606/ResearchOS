from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.conversation import Conversation
from app.schemas.conversation import MessageCreate


def create_conversation_turn(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
    user_content: str,
    assistant_content: str,
) -> tuple[Message, Message]:
    """Atomically persist both sides of a grounded assistant turn."""
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        ).with_for_update()
    )
    if conversation is None:
        raise ValueError("Conversation not found or access denied.")
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=user_content,
    )
    assistant_message = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        agent_name="ResearchOS RAG",
    )
    try:
        db.add_all([user_message, assistant_message])
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)
        return user_message, assistant_message
    except Exception:
        db.rollback()
        raise


def create_message(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
    message_data: MessageCreate,
    role: str = "user",
    agent_name: str | None = None
) -> Message:
    """Create a message inside a user's conversation."""

    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        )
    )

    if conversation is None:
        raise ValueError("Conversation not found or access denied.")

    new_message = Message(
        conversation_id=conversation_id,
        role=role,
        content=message_data.content,
        agent_name=agent_name
    )

    try:
        db.add(new_message)
        db.commit()
        db.refresh(new_message)
        return new_message
    except Exception:
        db.rollback()
        raise


def get_message_by_id(
    db: Session,
    message_id: UUID,
    user_id: UUID
):
    """Retrieve a message belonging to a user's conversation."""

    statement = (
        select(Message)
        .join(Conversation)
        .where(
            Message.id == message_id,
            Conversation.user_id == user_id
        )
    )

    return db.scalar(statement)


def get_conversation_messages(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
):
    """Retrieve messages from a conversation in chronological order."""

    statement = (
        select(Message)
        .join(Conversation)
        .where(
            Message.conversation_id == conversation_id,
            Conversation.user_id == user_id
        )
        .order_by(Message.created_at.asc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def get_recent_conversation_messages(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
    limit: int = 12,
):
    statement = (
        select(Message)
        .join(Conversation)
        .where(
            Message.conversation_id == conversation_id,
            Conversation.user_id == user_id,
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(reversed(db.scalars(statement).all()))


def delete_message(
    db: Session,
    message_id: UUID,
    user_id: UUID
) -> bool:
    """Delete a message belonging to a user's conversation."""

    message = get_message_by_id(db, message_id, user_id)

    if message is None:
        return False

    try:
        db.delete(message)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
