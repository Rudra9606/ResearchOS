from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# Create project request
class ProjectCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Research project title"
    )

    research_topic: str = Field(
        ...,
        min_length=5,
        description="Main research topic"
    )

    description: str | None = Field(
        default=None,
        description="Project description"
    )


# Update project request
class ProjectUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=3,
        max_length=255
    )

    research_topic: str | None = Field(
        default=None,
        min_length=5
    )

    description: str | None = None

    status: str | None = None


# Project response
class ProjectResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    research_topic: str
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Project list response
class ProjectListResponse(BaseModel):
    total: int
    projects: list[ProjectResponse]