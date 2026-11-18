from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ReportCitation(BaseModel):
    citation_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl | None = None
    authors: list[str] = Field(default_factory=list)
    publisher_or_venue: str | None = None
    publication_date: date | str | None = None
    source_type: str = "unknown"
    doi: str | None = None
    arxiv_id: str | None = None


class ReportSection(BaseModel):
    title: str
    available: bool = True
    content: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class StructuredResearchReport(BaseModel):
    title: str
    executive_summary: ReportSection
    research_objectives: ReportSection
    research_questions: ReportSection
    methodology: ReportSection
    web_research_findings: ReportSection
    academic_research_findings: ReportSection
    document_analysis_findings: ReportSection
    dataset_analysis_findings: ReportSection
    verified_claims: ReportSection
    limitations: ReportSection
    conclusion: ReportSection
    references: list[ReportCitation] = Field(default_factory=list)


class ReportGenerateRequest(BaseModel):
    research_run_id: UUID
    report_format: Literal["pdf", "docx", "html"] = "pdf"


class ReportGenerateResponse(BaseModel):
    report_id: UUID
    generation_status: str
    report_format: str
    file_path: str | None = None
