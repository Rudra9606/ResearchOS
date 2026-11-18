from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# Accepted research depths
ResearchDepth = Literal["basic", "standard", "comprehensive"]


# Research request schema
class ResearchRequest(BaseModel):
    research_topic: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Topic the user wants to research"
    )

    research_depth: ResearchDepth = Field(
        default="standard",
        description="Depth of research"
    )

    project_id: UUID | None = Field(
        default=None,
        description="Associated research project ID"
    )


# Research response schema
class ResearchResponse(BaseModel):
    id: UUID
    research_topic: str
    research_depth: str
    status: str
    progress: int = 0
    current_step: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Research status response
class ResearchStatusResponse(BaseModel):
    research_run_id: UUID
    status: str
    progress: int
    current_step: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)