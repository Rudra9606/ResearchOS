"""Project Service - handles project management operations."""

from uuid import UUID
import logging
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.crud.project import (
    create_project,
    get_project_by_id,
    get_user_projects,
    update_project,
    delete_project,
)
from app.core.config import settings
from app.models.document import Document
from app.models.research_job import ResearchJob
from app.models.research_report import ResearchReport
from app.models.research_run import ResearchRun
from app.schemas.project import ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)


def create_user_project(
    db: Session,
    project_data: ProjectCreate,
    user_id: UUID,
):
    """Create a new research project for a user."""
    return create_project(
        db=db,
        project_data=project_data,
        user_id=user_id,
    )


def get_project(
    db: Session,
    project_id: UUID,
    user_id: UUID,
):
    """Get a project by ID with ownership check."""
    return get_project_by_id(
        db=db,
        project_id=project_id,
        user_id=user_id,
    )


def list_user_projects(
    db: Session,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
):
    """List all projects for a user."""
    return get_user_projects(
        db=db,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )


def update_user_project(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    project_data: ProjectUpdate,
):
    """Update a user's project."""
    return update_project(
        db=db,
        project_id=project_id,
        user_id=user_id,
        project_data=project_data,
    )


def delete_user_project(
    db: Session,
    project_id: UUID,
    user_id: UUID,
) -> bool:
    """Delete a project and its stored artifacts, unless a worker is using them."""
    project = get_project_by_id(db, project_id, user_id)
    if project is None:
        return False

    run_ids = select(ResearchRun.id).where(ResearchRun.project_id == project_id)
    document_ids = select(Document.id).where(
        Document.project_id == project_id,
        Document.user_id == user_id,
    )
    project_jobs = db.scalars(
        select(ResearchJob)
        .where(or_(ResearchJob.research_run_id.in_(run_ids), ResearchJob.document_id.in_(document_ids)))
        .with_for_update()
    ).all()
    if any(job.status in {"queued", "running", "cancel_requested"} for job in project_jobs):
        raise ValueError("Project has background work in progress. Cancel or wait for it before deleting the project.")

    document_paths = list(db.scalars(
        select(Document.file_path).where(
            Document.project_id == project_id,
            Document.user_id == user_id,
        )
    ).all())
    report_paths = list(db.scalars(
        select(ResearchReport.file_path)
        .join(ResearchRun, ResearchReport.research_run_id == ResearchRun.id)
        .where(ResearchRun.project_id == project_id, ResearchReport.file_path.is_not(None))
    ).all())

    if not delete_project(db, project_id, user_id):
        return False

    allowed_roots = [
        (Path(settings.UPLOAD_DIR).resolve() / str(user_id)).resolve(),
        (Path("reports").resolve() / str(user_id)).resolve(),
    ]
    for stored_path in [*document_paths, *report_paths]:
        candidate = Path(stored_path).resolve()
        if not any(root in candidate.parents for root in allowed_roots):
            logger.warning("Skipped project artifact outside its owner storage directory")
            continue
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to remove a deleted project's stored artifact")
    return True
