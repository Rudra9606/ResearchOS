from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# Research run creation
class ResearchRunCreate(BaseModel):
    project_id: UUID

    research_topic: str = Field(
        ...,
        min_length=5,
        max_length=500
    )

    research_depth: Literal["basic", "standard", "comprehensive"] = "standard"


# Research run response
class ResearchRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    research_topic: str
    research_depth: str
    status: str
    progress: int
    current_step: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Research run progress
class ResearchRunStatusResponse(BaseModel):
    research_run_id: UUID
    status: str
    progress: int
    current_step: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
