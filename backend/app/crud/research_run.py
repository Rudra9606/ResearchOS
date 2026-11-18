from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research_run import ResearchRun
from app.models.project import ResearchProject
from app.schemas.research_run import ResearchRunCreate


def create_research_run(
    db: Session,
    run_data: ResearchRunCreate,
    user_id: UUID
) -> ResearchRun:
    """Create a new research execution."""

    project = db.scalar(
        select(ResearchProject).where(
            ResearchProject.id == run_data.project_id,
            ResearchProject.user_id == user_id
        )
    )

    if project is None:
        raise ValueError("Project not found or access denied.")

    new_run = ResearchRun(
        project_id=run_data.project_id,
        research_topic=run_data.research_topic,
        research_depth=run_data.research_depth,
        status="pending",
        progress=0
    )

    try:
        db.add(new_run)
        db.commit()
        db.refresh(new_run)
        return new_run
    except Exception:
        db.rollback()
        raise


def get_research_run_by_id(
    db: Session,
    run_id: UUID,
    user_id: UUID
):
    """Retrieve a research run belonging to a user."""

    statement = (
        select(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchRun.id == run_id,
            ResearchProject.user_id == user_id
        )
    )

    return db.scalar(statement)


def get_project_research_runs(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
):
    """Retrieve research runs belonging to a project."""

    statement = (
        select(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchRun.project_id == project_id,
            ResearchProject.user_id == user_id
        )
        .order_by(ResearchRun.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def update_research_run_progress(
    db: Session,
    run_id: UUID,
    user_id: UUID,
    progress: int,
    current_step: str | None = None
):
    """Update research execution progress."""

    if not 0 <= progress <= 100:
        raise ValueError("Progress must be between 0 and 100.")

    run = get_research_run_by_id(db, run_id, user_id)

    if run is None:
        return None

    try:
        run.progress = progress
        run.current_step = current_step

        if run.status == "pending":
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)

        if progress == 100:
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(run)
        return run

    except Exception:
        db.rollback()
        raise


def start_research_run(db: Session, run_id: UUID, user_id: UUID, *, allow_queued: bool = False):
    """Atomically claim a pending run so concurrent requests cannot duplicate it."""
    statement = (
        select(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchRun.id == run_id,
            ResearchProject.user_id == user_id,
        )
        .with_for_update()
    )
    run = db.scalar(statement)
    if run is None:
        return None
    if run.status != "pending" and not (allow_queued and run.status == "queued"):
        return False

    try:
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return run
    except Exception:
        db.rollback()
        raise


def update_research_run_status(
    db: Session,
    run_id: UUID,
    user_id: UUID,
    status: str,
    error_message: str | None = None
):
    """Update research execution status."""

    allowed_statuses = [
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
    ]

    if status not in allowed_statuses:
        raise ValueError("Invalid research run status.")

    run = get_research_run_by_id(db, run_id, user_id)

    if run is None:
        return None

    try:
        run.status = status
        run.error_message = error_message

        if status == "running" and run.started_at is None:
            run.started_at = datetime.now(timezone.utc)

        if status in ["completed", "failed"]:
            run.completed_at = datetime.now(timezone.utc)

        if status == "completed":
            run.progress = 100

        db.commit()
        db.refresh(run)
        return run

    except Exception:
        db.rollback()
        raise


def delete_research_run(
    db: Session,
    run_id: UUID,
    user_id: UUID
) -> bool:
    """Delete a research execution."""

    run = get_research_run_by_id(db, run_id, user_id)

    if run is None:
        return False

    try:
        db.delete(run)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
