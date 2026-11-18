from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.project import ResearchProject
from app.schemas.document import DocumentCreate


def create_document(
    db: Session,
    document_data: DocumentCreate,
    project_id: UUID,
    user_id: UUID,
    file_path: str
) -> Document:
    """Register an uploaded document."""

    project = db.scalar(
        select(ResearchProject).where(
            ResearchProject.id == project_id,
            ResearchProject.user_id == user_id
        )
    )

    if project is None:
        raise ValueError("Project not found or access denied.")

    new_document = Document(
        project_id=project_id,
        user_id=user_id,
        filename=document_data.filename,
        file_type=document_data.file_type,
        file_size=document_data.file_size,
        file_path=file_path,
        processing_status="pending"
    )

    try:
        db.add(new_document)
        db.commit()
        db.refresh(new_document)
        return new_document
    except Exception:
        db.rollback()
        raise


def get_document_by_id(
    db: Session,
    document_id: UUID,
    user_id: UUID
):
    """Retrieve a document belonging to a user."""

    statement = select(Document).where(
        Document.id == document_id,
        Document.user_id == user_id
    )

    return db.scalar(statement)


def get_project_documents(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
):
    """Retrieve documents belonging to a project."""

    statement = (
        select(Document)
        .where(
            Document.project_id == project_id,
            Document.user_id == user_id
        )
        .order_by(Document.uploaded_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def count_project_documents(db: Session, project_id: UUID, user_id: UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(Document).where(
            Document.project_id == project_id,
            Document.user_id == user_id,
        )
    ) or 0


def update_document_status(
    db: Session,
    document_id: UUID,
    user_id: UUID,
    processing_status: str
):
    """Update document processing status."""

    allowed_statuses = [
        "pending",
        "queued",
        "processing",
        "completed",
        "failed",
        "cancelled",
    ]

    if processing_status not in allowed_statuses:
        raise ValueError("Invalid document processing status.")

    document = get_document_by_id(db, document_id, user_id)

    if document is None:
        return None

    try:
        document.processing_status = processing_status
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        raise


def delete_document(
    db: Session,
    document_id: UUID,
    user_id: UUID
) -> bool:
    """Delete a document database record."""

    document = get_document_by_id(db, document_id, user_id)

    if document is None:
        return False

    try:
        db.delete(document)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
