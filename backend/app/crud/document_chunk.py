from uuid import UUID
from typing import List

from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk


def create_document_chunk(
    db: Session,
    document_id: UUID,
    chunk_index: int,
    content: str,
    chunk_metadata: dict | None = None,
    embedding: list[float] | None = None,
) -> DocumentChunk:
    """Create a document chunk."""
    chunk = DocumentChunk(
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        chunk_metadata=chunk_metadata,
        embedding=embedding,
    )

    try:
        db.add(chunk)
        db.commit()
        db.refresh(chunk)
        return chunk
    except Exception:
        db.rollback()
        raise


def get_document_chunks(
    db: Session,
    document_id: UUID,
) -> List[DocumentChunk]:
    """Get all chunks for a document."""
    from sqlalchemy import select

    statement = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(db.scalars(statement).all())


def delete_document_chunks(
    db: Session,
    document_id: UUID,
) -> bool:
    """Delete all chunks for a document."""
    from sqlalchemy import delete

    try:
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise