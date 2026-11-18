from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# Agent execution response
class AgentExecutionResponse(BaseModel):
    id: UUID
    research_run_id: UUID
    agent_name: str
    status: str
    input_data: dict | None = None
    output_data: dict | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Agent execution list
class AgentExecutionListResponse(BaseModel):
    total: int
    executions: list[AgentExecutionResponse]


class AgentExecutionCreate(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=100)
    input_data: dict | None = None


# Agent status update
class AgentStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        description="Agent execution status"
    )

    error_message: str | None = None