from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


ReportFormat = Literal["pdf", "docx", "html"]


# Research report creation
class ResearchReportCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=3,
        max_length=255
    )

    content: str | None = None

    report_format: ReportFormat = "pdf"


# Research report response
class ResearchReportResponse(BaseModel):
    id: UUID
    research_run_id: UUID
    title: str
    content: str | None = None
    report_format: str
    file_path: str | None = None
    generation_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Research report list
class ResearchReportListResponse(BaseModel):
    total: int
    reports: list[ResearchReportResponse]