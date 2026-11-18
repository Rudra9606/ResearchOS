from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict
from app.schemas.rag import RAGEvidence


# Create conversation
class ConversationCreate(BaseModel):
    project_id: UUID
    title: str | None = Field(
        default=None,
        max_length=255
    )


# Send message
class MessageCreate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=20000
    )


# Message response
class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    agent_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Conversation response
class ConversationResponse(BaseModel):
    id: UUID
    project_id: UUID
    user_id: UUID
    thread_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Conversation history response
class ConversationHistoryResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[MessageResponse]


class ConversationAskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    max_tokens: int = Field(default=800, ge=1, le=4000)


class ConversationTurnResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    citations: list[RAGEvidence]
    evidence_sufficient: bool
