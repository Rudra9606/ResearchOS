from typing import Any
from uuid import UUID

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.crud.research_report import (
    create_research_report,
    get_research_report_by_id,
    get_research_run_reports,
    count_research_run_reports,
    update_research_report,
    delete_research_report,
)
from app.schemas.research_report import (
    ResearchReportCreate,
    ResearchReportResponse,
    ResearchReportListResponse,
)
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.report_document import (
    ReportGenerateRequest,
    ReportGenerateResponse,
    StructuredResearchReport,
)
from app.crud.research_run import get_research_run_by_id
from app.agents.report_writer import ReportWriterAgent
from app.services.report_service import (
    export_report_document,
    safe_report_path,
)

router = APIRouter()


@router.post("/generate", response_model=ReportGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_report_endpoint(
    request: ReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportGenerateResponse:
    run = get_research_run_by_id(db, request.research_run_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found or access denied.")
    state = {
        "research_topic": run.research_topic,
        "research_sources": [
            {
                "title": source.title,
                "url": source.url,
                "source_type": source.source_type,
                "authors": [item.strip() for item in (source.authors or "").split(",") if item.strip()],
                "publication_date": source.publication_date,
                "publisher": source.publisher,
                "summary": source.summary,
            }
            for source in run.sources
        ],
        "verified_claims": [
            {
                "claim_text": claim.claim_text,
                "verification_status": claim.verification_status,
                "explanation": claim.explanation,
                "confidence_score": claim.confidence_score,
                "evidence": claim.evidence,
            }
            for claim in run.verified_claims
        ],
    }
    report = create_research_report(
        db,
        run.id,
        current_user.id,
        ResearchReportCreate(
            title=f"Research Report: {run.research_topic}",
            report_format=request.report_format,
        ),
    )
    update_research_report(db, report.id, current_user.id, generation_status="generating")
    try:
        state = await ReportWriterAgent().execute(state)
        if state.get("report_generation_status") != "completed":
            raise RuntimeError("Report writer did not produce a completed report.")
        structured = state["structured_report"]
        output_path = safe_report_path(current_user.id, report.id, request.report_format)
        export_report_document(
            StructuredResearchReport.model_validate(structured),
            state["structured_report"]["title"],
            request.report_format,
            str(output_path),
        )
        report = update_research_report(
            db,
            report.id,
            current_user.id,
            generation_status="completed",
            content=state["report_content"],
            file_path=str(output_path),
        )
        return ReportGenerateResponse(
            report_id=report.id,
            generation_status=report.generation_status,
            report_format=report.report_format,
            file_path=report.file_path,
        )
    except Exception as exc:
        update_research_report(
            db, report.id, current_user.id, generation_status="failed"
        )
        raise HTTPException(status_code=502, detail="Report generation failed.") from exc


@router.post("/", response_model=ResearchReportResponse, status_code=status.HTTP_201_CREATED)
def create_research_report_endpoint(
    research_run_id: UUID,
    report_data: ResearchReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a research report."""
    try:
        report = create_research_report(
            db=db,
            research_run_id=research_run_id,
            user_id=current_user.id,
            report_data=report_data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return report


@router.get("/", response_model=ResearchReportListResponse)
def list_research_reports(
    research_run_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve all reports for a research run."""
    reports = get_research_run_reports(
        db=db,
        research_run_id=research_run_id,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return ResearchReportListResponse(
        total=count_research_run_reports(db, research_run_id, current_user.id),
        reports=reports,
    )


@router.get("/{report_id}", response_model=ResearchReportResponse)
def get_research_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve a research report by ID."""
    report = get_research_report_by_id(
        db=db,
        report_id=report_id,
        user_id=current_user.id,
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research report not found or access denied.",
        )
    return report


@router.get("/{report_id}/download")
def download_research_report(
    report_id: UUID,
    format: str | None = Query(default=None, pattern="^(pdf|docx|html)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = get_research_report_by_id(db, report_id, current_user.id)
    if report is None or not report.file_path:
        raise HTTPException(status_code=404, detail="Report file not found or access denied.")
    path = Path(report.file_path).resolve()
    user_root = (Path("reports") / str(current_user.id)).resolve()
    if user_root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Report file not found.")
    if format and report.report_format != format:
        raise HTTPException(status_code=404, detail="Requested report format is unavailable.")
    return FileResponse(path=str(path), filename=path.name)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_research_report_endpoint(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a research report."""
    report = get_research_report_by_id(db=db, report_id=report_id, user_id=current_user.id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research report not found or access denied.",
        )
    if report.file_path:
        path = Path(report.file_path).resolve()
        user_root = (Path("reports") / str(current_user.id)).resolve()
        if user_root in path.parents and path.is_file():
            path.unlink()
    success = delete_research_report(
        db=db,
        report_id=report_id,
        user_id=current_user.id,
    )
