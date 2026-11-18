from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# Document upload information
class DocumentCreate(BaseModel):
    filename: str = Field(
        ...,
        min_length=1,
        max_length=255
    )

    file_type: str = Field(
        ...,
        max_length=50
    )

    file_size: int | None = Field(
        default=None,
        ge=0
    )


# Document response
class DocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    user_id: UUID
    filename: str
    file_type: str
    file_size: int | None = None
    processing_status: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Document processing status
class DocumentStatusResponse(BaseModel):
    document_id: UUID
    processing_status: str
    message: str | None = None


# Document list response
class DocumentListResponse(BaseModel):
    total: int
    documents: list[DocumentResponse]