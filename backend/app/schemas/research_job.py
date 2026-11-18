from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


JobStatus = Literal[
    "queued", "running", "cancel_requested", "cancelled", "completed", "failed"
]


class ResearchJobResponse(BaseModel):
    id: UUID
    job_type: Literal["research", "document"]
    status: JobStatus
    research_run_id: UUID | None = None
    document_id: UUID | None = None
    attempts: int
    max_attempts: int
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
