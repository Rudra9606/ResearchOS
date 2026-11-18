from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.project import ResearchProject
from app.schemas.project import ProjectCreate, ProjectUpdate


def create_project(
    db: Session,
    project_data: ProjectCreate,
    user_id: UUID
) -> ResearchProject:
    """Create a new research project."""

    new_project = ResearchProject(
        user_id=user_id,
        title=project_data.title,
        research_topic=project_data.research_topic,
        description=project_data.description
    )

    try:
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        return new_project
    except Exception:
        db.rollback()
        raise


def get_project_by_id(
    db: Session,
    project_id: UUID,
    user_id: UUID
):
    """Get a project belonging to a specific user."""

    statement = select(ResearchProject).where(
        ResearchProject.id == project_id,
        ResearchProject.user_id == user_id
    )

    return db.scalar(statement)


def get_user_projects(
    db: Session,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
):
    """Get all projects belonging to a user."""

    statement = (
        select(ResearchProject)
        .where(ResearchProject.user_id == user_id)
        .order_by(ResearchProject.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def count_user_projects(db: Session, user_id: UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(ResearchProject).where(
            ResearchProject.user_id == user_id
        )
    ) or 0


def update_project(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    project_data: ProjectUpdate
):
    """Update a user's research project."""

    project = get_project_by_id(db, project_id, user_id)

    if project is None:
        return None

    update_data = project_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(project, field, value)

    try:
        db.commit()
        db.refresh(project)
        return project
    except Exception:
        db.rollback()
        raise


def delete_project(
    db: Session,
    project_id: UUID,
    user_id: UUID
) -> bool:
    """Delete a user's research project."""

    project = get_project_by_id(db, project_id, user_id)

    if project is None:
        return False

    try:
        db.delete(project)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
