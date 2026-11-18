import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.project import ResearchProject
from app.schemas.conversation import ConversationCreate


def create_conversation(
    db: Session,
    conversation_data: ConversationCreate,
    user_id: UUID
) -> Conversation:
    """Create a conversation for a user's project."""

    project = db.scalar(
        select(ResearchProject).where(
            ResearchProject.id == conversation_data.project_id,
            ResearchProject.user_id == user_id
        )
    )

    if project is None:
        raise ValueError("Project not found or access denied.")

    new_conversation = Conversation(
        project_id=conversation_data.project_id,
        user_id=user_id,
        thread_id=str(uuid.uuid4()),
        title=conversation_data.title
    )

    try:
        db.add(new_conversation)
        db.commit()
        db.refresh(new_conversation)
        return new_conversation
    except Exception:
        db.rollback()
        raise


def get_conversation_by_id(
    db: Session,
    conversation_id: UUID,
    user_id: UUID
):
    """Retrieve a conversation belonging to a user."""

    statement = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id
    )

    return db.scalar(statement)


def get_user_conversations(
    db: Session,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
):
    """Retrieve all conversations belonging to a user."""

    statement = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def update_conversation_title(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
    title: str
):
    """Update a conversation title."""

    conversation = get_conversation_by_id(
        db, conversation_id, user_id
    )

    if conversation is None:
        return None

    try:
        conversation.title = title
        db.commit()
        db.refresh(conversation)
        return conversation
    except Exception:
        db.rollback()
        raise


def delete_conversation(
    db: Session,
    conversation_id: UUID,
    user_id: UUID
) -> bool:
    """Delete a user's conversation."""

    conversation = get_conversation_by_id(
        db, conversation_id, user_id
    )

    if conversation is None:
        return False

    try:
        db.delete(conversation)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
