from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.crud.message import (
    create_message,
    get_message_by_id,
    get_conversation_messages,
    delete_message,
)
from app.schemas.conversation import MessageCreate, MessageResponse
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def create_message_endpoint(
    conversation_id: UUID,
    message_data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Send a message in a conversation."""
    try:
        message = create_message(
            db, conversation_id, current_user.id, message_data, role="user"
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return message


@router.get("/{message_id}", response_model=MessageResponse)
def get_message(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve a message by ID."""
    message = get_message_by_id(
        db=db,
        message_id=message_id,
        user_id=current_user.id,
    )
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or access denied.",
        )
    return message


@router.get("/conversation/{conversation_id}", response_model=list[MessageResponse])
def list_messages(
    conversation_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve messages from a conversation."""
    messages = get_conversation_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return messages


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message_endpoint(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a message."""
    success = delete_message(
        db=db,
        message_id=message_id,
        user_id=current_user.id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or access denied.",
        )
