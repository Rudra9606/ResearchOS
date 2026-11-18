from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# Research source response
class ResearchSourceResponse(BaseModel):
    id: UUID
    research_run_id: UUID
    title: str
    url: str | None = None
    source_type: str
    authors: str | None = None
    publication_date: datetime | None = None
    publisher: str | None = None
    summary: str | None = None
    accessed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Research source list
class ResearchSourceListResponse(BaseModel):
    total: int
    sources: list[ResearchSourceResponse]


# Research source creation
class ResearchSourceCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    url: str | None = None
    source_type: str = Field(..., max_length=50)
    authors: str | None = None
    publication_date: datetime | None = None
    publisher: str | None = None
    summary: str | None = None