"""Document Processing Pipeline - text extraction, cleaning, chunking, embedding generation."""

import csv
import re
from typing import List
from uuid import UUID
from typing import Callable

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from openpyxl import load_workbook

from app.core.config import settings
from app.db.session import SessionLocal
from app.crud.document_chunk import create_document_chunk, delete_document_chunks
from app.crud.document import update_document_status
from app.models.document import Document
from app.rag.embeddings import get_embedding_service

def get_embedding_model():
    """Return the shared configured Sentence Transformers model."""
    return get_embedding_service().get_model()


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    text_parts = []
    doc = fitz.open(file_path)
    try:
        for page in doc:
            text_parts.append(page.get_text())
    finally:
        doc.close()
    return "\n".join(text_parts)


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a DOCX file using python-docx."""
    doc = DocxDocument(file_path)
    text_parts = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text_parts.append(paragraph.text)
    for table in doc.tables:
        for row in table.rows:
            row_text = []
            for cell in row.cells:
                if cell.text.strip():
                    row_text.append(cell.text)
            if row_text:
                text_parts.append(" | ".join(row_text))
    return "\n".join(text_parts)


def extract_text_from_txt(file_path: str) -> str:
    """Extract text from a TXT file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_text_from_csv(file_path: str) -> str:
    """Extract text from a CSV file."""
    with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as file:
        rows = csv.reader(file)
        return "\n".join(" | ".join(row) for row in rows)


def extract_text_from_xlsx(file_path: str) -> str:
    """Extract text from an XLSX file."""
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    try:
        lines = []
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows(values_only=True):
                values = [str(value) for value in row if value is not None]
                if values:
                    lines.append(" | ".join(values))
        return "\n".join(lines)
    finally:
        workbook.close()


def extract_text(file_path: str, file_type: str) -> str:
    """Extract text from a document based on its file type."""
    file_type = file_type.lower().lstrip(".")

    extractors = {
        "pdf": extract_text_from_pdf,
        "docx": extract_text_from_docx,
        "txt": extract_text_from_txt,
        "csv": extract_text_from_csv,
        "xlsx": extract_text_from_xlsx,
    }

    if file_type not in extractors:
        raise ValueError(f"Unsupported file type: {file_type}")

    return extractors[file_type](file_path)


def clean_text(text: str) -> str:
    """Clean and normalize extracted text."""
    text = text.replace("\x00", "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = text.strip()
    return text


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[str]:
    """Split text into overlapping chunks."""
    if not text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size.")

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end]
        chunks.append(chunk)

        if end >= text_len:
            break

        start = end - chunk_overlap
        if start < 0:
            start = 0

    return chunks


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a list of texts."""
    return get_embedding_service().embed(texts)


def process_document(
    document_id: UUID,
    file_path: str,
    file_type: str,
    user_id: UUID,
    cancel_check: Callable[[], bool] | None = None,
) -> dict:
    """Process a document: extract text, clean, chunk, embed, and store."""
    db = SessionLocal()
    try:
        def check_cancelled() -> None:
            if cancel_check and cancel_check():
                raise DocumentProcessingCancelled()

        # Update status to processing
        update_document_status(db, document_id, user_id, "processing")

        # Extract text
        check_cancelled()
        raw_text = extract_text(file_path, file_type)
        check_cancelled()

        if not raw_text.strip():
            update_document_status(db, document_id, user_id, "failed")
            return {"status": "failed", "error": "No text extracted from document."}

        # Clean text
        cleaned_text = clean_text(raw_text)

        if not cleaned_text.strip():
            update_document_status(db, document_id, user_id, "failed")
            return {"status": "failed", "error": "No text after cleaning."}

        # Chunk text
        chunks = chunk_text(
            cleaned_text,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

        if not chunks:
            update_document_status(db, document_id, user_id, "failed")
            return {"status": "failed", "error": "No chunks generated."}

        # Generate embeddings
        embeddings = generate_embeddings(chunks)
        check_cancelled()

        # Delete existing chunks if any (re-processing)
        delete_document_chunks(db, document_id)

        # Store chunks with embeddings
        for i, (chunk_text_content, embedding) in enumerate(zip(chunks, embeddings)):
            check_cancelled()
            chunk_metadata = {
                "chunk_index": i,
                "total_chunks": len(chunks),
                "document_id": str(document_id),
                "file_type": file_type,
            }
            create_document_chunk(
                db=db,
                document_id=document_id,
                chunk_index=i,
                content=chunk_text_content,
                chunk_metadata=chunk_metadata,
                embedding=embedding,
            )

        # Update status to completed
        update_document_status(db, document_id, user_id, "completed")

        return {
            "status": "completed",
            "chunks_created": len(chunks),
            "embeddings_generated": len(embeddings),
        }

    except DocumentProcessingCancelled:
        try:
            delete_document_chunks(db, document_id)
            update_document_status(db, document_id, user_id, "cancelled")
        except Exception:
            db.rollback()
        return {"status": "cancelled"}
    except Exception as exc:
        try:
            update_document_status(db, document_id, user_id, "failed")
        except Exception:
            db.rollback()
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


class DocumentProcessingCancelled(Exception):
    """Raised at safe boundaries when an operator cancels document processing."""
