from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.research_report import ResearchReport
from app.models.research_run import ResearchRun
from app.models.project import ResearchProject
from app.schemas.research_report import (
    ResearchReportCreate,
    ReportFormat
)


def create_research_report(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    report_data: ResearchReportCreate
) -> ResearchReport:
    """Create a research report."""

    run = db.scalar(
        select(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchRun.id == research_run_id,
            ResearchProject.user_id == user_id
        )
    )

    if run is None:
        raise ValueError("Research run not found or access denied.")

    new_report = ResearchReport(
        research_run_id=research_run_id,
        title=report_data.title,
        content=report_data.content,
        report_format=report_data.report_format,
        generation_status="pending"
    )

    try:
        db.add(new_report)
        db.commit()
        db.refresh(new_report)
        return new_report
    except Exception:
        db.rollback()
        raise


def get_research_report_by_id(
    db: Session,
    report_id: UUID,
    user_id: UUID
):
    """Retrieve a research report."""

    statement = (
        select(ResearchReport)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchReport.id == report_id,
            ResearchProject.user_id == user_id
        )
    )

    return db.scalar(statement)


def get_research_run_reports(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
):
    """Retrieve reports belonging to a research run."""

    statement = (
        select(ResearchReport)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchReport.research_run_id == research_run_id,
            ResearchProject.user_id == user_id
        )
        .order_by(ResearchReport.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def count_research_run_reports(db: Session, research_run_id: UUID, user_id: UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(ResearchReport)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchReport.research_run_id == research_run_id,
            ResearchProject.user_id == user_id,
        )
    ) or 0


def update_research_report(
    db: Session,
    report_id: UUID,
    user_id: UUID,
    generation_status: str | None = None,
    content: str | None = None,
    file_path: str | None = None
):
    """Update report content, file location, or status."""

    allowed_statuses = [
        "pending",
        "generating",
        "completed",
        "failed"
    ]

    if (
        generation_status is not None
        and generation_status not in allowed_statuses
    ):
        raise ValueError("Invalid report generation status.")

    report = get_research_report_by_id(
        db, report_id, user_id
    )

    if report is None:
        return None

    try:
        if generation_status is not None:
            report.generation_status = generation_status

        if content is not None:
            report.content = content

        if file_path is not None:
            report.file_path = file_path

        db.commit()
        db.refresh(report)
        return report

    except Exception:
        db.rollback()
        raise


def delete_research_report(
    db: Session,
    report_id: UUID,
    user_id: UUID
) -> bool:
    """Delete a research report database record."""

    report = get_research_report_by_id(
        db, report_id, user_id
    )

    if report is None:
        return False

    try:
        db.delete(report)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
