from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, UploadFile, File
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.crud.document import (
    create_document,
    get_document_by_id,
    get_project_documents,
    count_project_documents,
    delete_document,
)
from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentListResponse,
)
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.models.user import User
import os
import uuid
from pathlib import Path
from zipfile import BadZipFile, ZipFile

# Allowed file types and max size
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx"}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024
MAX_ARCHIVE_UNPACKED_SIZE = 250 * 1024 * 1024
UPLOAD_DIR = Path(settings.UPLOAD_DIR)

router = APIRouter()


def validate_file(file: UploadFile) -> str:
    """Validate uploaded file type. Returns safe filename."""
    original_filename = file.filename or ""
    if not original_filename.strip() or len(original_filename) > 255 or "\x00" in original_filename:
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    file_ext = os.path.splitext(original_filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file_ext}' not supported.",
        )

    return f"{uuid.uuid4()}{file_ext}"


def validate_file_content(file_path: Path, file_ext: str) -> None:
    """Check binary signatures and bound archive expansion before parsing."""
    if file_ext == ".pdf":
        with file_path.open("rb") as uploaded:
            if uploaded.read(5) != b"%PDF-":
                raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF.")
        return

    if file_ext not in {".docx", ".xlsx"}:
        return

    try:
        with ZipFile(file_path) as archive:
            entries = archive.infolist()
            required_entry = "word/document.xml" if file_ext == ".docx" else "xl/workbook.xml"
            entry_names = {entry.filename for entry in entries}
            if "[Content_Types].xml" not in entry_names or required_entry not in entry_names:
                raise HTTPException(status_code=400, detail="Uploaded Office document is invalid.")
            if sum(entry.file_size for entry in entries) > MAX_ARCHIVE_UNPACKED_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Expanded Office document exceeds the supported size limit.",
                )
    except BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Uploaded Office document is invalid.") from exc


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: UUID,
    background: bool = Query(default=False),
    file: UploadFile = File(...),
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Upload a document for processing."""
    from app.crud.project import get_project_by_id
    project = get_project_by_id(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied.",
        )

    original_filename = file.filename or ""
    safe_filename = validate_file(file)

    upload_dir = UPLOAD_DIR / str(current_user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / safe_filename
    file_size = 0
    try:
        with open(file_path, "wb") as destination:
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=(
                            "File size exceeds maximum limit of "
                            f"{MAX_FILE_SIZE // (1024 * 1024)} MB."
                        ),
                    )
                destination.write(chunk)
    except Exception:
        file_path.unlink(missing_ok=True)
        try:
            upload_dir.rmdir()
        except OSError:
            pass
        raise

    try:
        file_ext = Path(original_filename).suffix.lower()
        validate_file_content(file_path, file_ext)
    except Exception:
        file_path.unlink(missing_ok=True)
        try:
            upload_dir.rmdir()
        except OSError:
            pass
        raise

    document_data = DocumentCreate(
        filename=original_filename,
        file_type=os.path.splitext(original_filename)[1].lower().lstrip("."),
        file_size=file_size,
    )

    try:
        document = create_document(
            db=db,
            document_data=document_data,
            project_id=project_id,
            user_id=current_user.id,
            file_path=str(file_path),
        )
    except Exception:
        file_path.unlink(missing_ok=True)
        try:
            upload_dir.rmdir()
        except OSError:
            pass
        raise

    if background:
        from app.crud.research_job import enqueue_document_job

        try:
            job = enqueue_document_job(db, document)
            if response is not None:
                response.headers["X-ResearchOS-Job-ID"] = str(job.id)
        except Exception:
            delete_document(db, document.id, current_user.id)
            file_path.unlink(missing_ok=True)
            raise
    else:
        # Preserve the synchronous upload contract for existing integrations.
        from app.services.document_processing import process_document
        process_document(
            document_id=document.id,
            file_path=str(file_path),
            file_type=document_data.file_type,
            user_id=current_user.id,
        )

    db.refresh(document)
    return document


@router.get("/", response_model=DocumentListResponse)
def list_documents(
    project_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve documents for a project."""
    documents = get_project_documents(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return DocumentListResponse(
        total=count_project_documents(db, project_id, current_user.id),
        documents=documents,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve a document by ID."""
    document = get_document_by_id(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied.",
        )
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_endpoint(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a document."""
    document = get_document_by_id(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied.",
        )

    if document.file_path and os.path.exists(document.file_path):
        os.remove(document.file_path)

    success = delete_document(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied.",
        )
