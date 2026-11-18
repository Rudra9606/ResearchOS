from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.research_source import ResearchSource
from app.models.research_run import ResearchRun
from app.models.project import ResearchProject
from app.schemas.research_source import ResearchSourceCreate


def create_research_source(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    source_data: ResearchSourceCreate
) -> ResearchSource:
    """Create a research source."""

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

    if source_data.url:
        existing = db.scalar(
            select(ResearchSource).where(
                ResearchSource.research_run_id == research_run_id,
                ResearchSource.url == source_data.url,
            )
        )
        if existing is not None:
            return existing

    new_source = ResearchSource(
        research_run_id=research_run_id,
        title=source_data.title,
        url=source_data.url,
        source_type=source_data.source_type,
        authors=source_data.authors,
        publication_date=source_data.publication_date,
        publisher=source_data.publisher,
        summary=source_data.summary
    )

    try:
        db.add(new_source)
        db.commit()
        db.refresh(new_source)
        return new_source
    except Exception:
        db.rollback()
        raise


def get_research_source_by_id(
    db: Session,
    source_id: UUID,
    user_id: UUID
):
    """Retrieve a research source."""

    statement = (
        select(ResearchSource)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchSource.id == source_id,
            ResearchProject.user_id == user_id
        )
    )

    return db.scalar(statement)


def get_research_run_sources(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
):
    """Retrieve sources collected during a research run."""

    statement = (
        select(ResearchSource)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchSource.research_run_id == research_run_id,
            ResearchProject.user_id == user_id
        )
        .order_by(ResearchSource.accessed_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def count_research_run_sources(db: Session, research_run_id: UUID, user_id: UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(ResearchSource)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchSource.research_run_id == research_run_id,
            ResearchProject.user_id == user_id,
        )
    ) or 0


def delete_research_source(
    db: Session,
    source_id: UUID,
    user_id: UUID
) -> bool:
    """Delete a research source."""

    source = get_research_source_by_id(
        db, source_id, user_id
    )

    if source is None:
        return False

    try:
        db.delete(source)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
