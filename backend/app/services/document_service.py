"""Document Service - handles document validation, storage, and processing coordination."""

from uuid import UUID
from pathlib import Path
import os
import shutil

from sqlalchemy.orm import Session

from app.crud.document import (
    create_document,
    get_document_by_id,
    get_project_documents,
    update_document_status,
    delete_document,
)
from app.crud.document_chunk import (
    create_document_chunk,
    get_document_chunks,
    delete_document_chunks,
)
from app.schemas.document import DocumentCreate
from app.models.document import Document
from app.models.document_chunk import DocumentChunk

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
UPLOAD_DIR = Path("uploads")


def validate_upload_file(filename: str, file_size: int) -> str:
    """Validate file type and size. Returns safe file extension."""
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type '{file_ext}' not supported.")

    dangerous_extensions = {".exe", ".bat", ".sh", ".ps1", ".cmd", ".com", ".scr", ".vbs", ".js", ".jar"}
    if file_ext in dangerous_extensions:
        raise ValueError("Executable files are not allowed.")

    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"File size exceeds maximum limit of {MAX_FILE_SIZE // (1024 * 1024)} MB.")

    return file_ext


def save_uploaded_file(
    user_id: UUID,
    filename: str,
    content: bytes,
) -> tuple[str, str]:
    """Save uploaded file to disk. Returns (safe_filename, file_path)."""
    import uuid
    file_ext = os.path.splitext(filename)[1].lower()
    safe_filename = f"{uuid.uuid4()}{file_ext}"

    upload_dir = UPLOAD_DIR / str(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / safe_filename
    with open(file_path, "wb") as f:
        f.write(content)

    return safe_filename, str(file_path)


def register_document(
    db: Session,
    document_data: DocumentCreate,
    project_id: UUID,
    user_id: UUID,
    file_path: str,
) -> Document:
    """Register a document in the database."""
    return create_document(
        db=db,
        document_data=document_data,
        project_id=project_id,
        user_id=user_id,
        file_path=file_path,
    )


def get_document(
    db: Session,
    document_id: UUID,
    user_id: UUID,
) -> Document | None:
    """Get a document by ID with ownership check."""
    return get_document_by_id(
        db=db,
        document_id=document_id,
        user_id=user_id,
    )


def list_project_documents(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
):
    """List documents for a project."""
    return get_project_documents(
        db=db,
        project_id=project_id,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )


def update_document_processing_status(
    db: Session,
    document_id: UUID,
    user_id: UUID,
    processing_status: str,
) -> Document | None:
    """Update document processing status."""
    return update_document_status(
        db=db,
        document_id=document_id,
        user_id=user_id,
        processing_status=processing_status,
    )


def remove_document(
    db: Session,
    document_id: UUID,
    user_id: UUID,
) -> bool:
    """Delete a document and its physical file."""
    document = get_document_by_id(db, document_id, user_id)
    if not document:
        return False

    try:
        if document.file_path and os.path.exists(document.file_path):
            os.remove(document.file_path)
    except Exception:
        pass

    return delete_document(db=db, document_id=document_id, user_id=user_id)