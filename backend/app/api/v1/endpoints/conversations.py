from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.crud.conversation import (
    create_conversation,
    get_conversation_by_id,
    get_user_conversations,
    update_conversation_title,
    delete_conversation,
)
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationAskRequest,
    ConversationTurnResponse,
)
from app.crud.message import create_conversation_turn, get_recent_conversation_messages
from app.core.dependencies import get_current_user
from app.models.user import User
from app.providers.exceptions import ProviderError
from app.rag.qa import RAGQuestionAnsweringService
from app.rag.retrieval import RAGRetrievalService

router = APIRouter()


@router.post("/{conversation_id}/ask", response_model=ConversationTurnResponse)
async def ask_in_conversation(
    conversation_id: UUID,
    request: ConversationAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Answer a project-grounded question and persist both messages."""
    conversation = get_conversation_by_id(db, conversation_id, current_user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied.")

    previous_messages = get_recent_conversation_messages(
        db, conversation_id, current_user.id, limit=12
    )
    history = "\n".join(
        f"{message.role}: {message.content[:2000]}" for message in previous_messages
    )[-12000:]
    try:
        result = await RAGQuestionAnsweringService(RAGRetrievalService(db)).answer(
            request.query,
            user_id=current_user.id,
            project_id=conversation.project_id,
            max_tokens=request.max_tokens,
            conversation_context=history or None,
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The configured language model provider is unavailable.",
        ) from exc

    answer = result["answer"]
    citations = result["citations"]
    if citations:
        references = "\n".join(
            f"- {citation['citation']} {citation.get('document_filename') or 'Document'}, "
            f"chunk {citation['chunk_index']}"
            + (f" — {citation['source_url']}" if citation.get("source_url") else "")
            for citation in citations
        )
        answer = f"{answer}\n\nSources:\n{references}"
    try:
        user_message, assistant_message = create_conversation_turn(
            db,
            conversation_id,
            current_user.id,
            request.query,
            answer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "user_message": user_message,
        "assistant_message": assistant_message,
        "citations": citations,
        "evidence_sufficient": result["evidence_sufficient"],
    }


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation_endpoint(
    conversation_data: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new conversation for a project."""
    try:
        conversation = create_conversation(db, conversation_data, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return conversation


@router.get("/", response_model=list[ConversationResponse])
def list_conversations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve all conversations for the current user."""
    conversations = get_user_conversations(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return conversations


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve a conversation by ID."""
    conversation = get_conversation_by_id(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied.",
        )
    return conversation


@router.put("/{conversation_id}", response_model=ConversationResponse)
def update_conversation_endpoint(
    conversation_id: UUID,
    title: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update a conversation title."""
    conversation = update_conversation_title(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        title=title,
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied.",
        )
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_endpoint(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a conversation."""
    success = delete_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied.",
        )
