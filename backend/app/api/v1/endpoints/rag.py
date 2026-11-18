from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.crud.document import get_document_by_id
from app.db.session import get_db
from app.models.document_chunk import DocumentChunk
from app.models.document import Document
from app.models.user import User
from app.providers.exceptions import ProviderError
from app.rag.qa import RAGQuestionAnsweringService
from app.rag.retrieval import RAGRetrievalService
from app.schemas.rag import (
    DocumentIndexResponse,
    RAGAnswerResponse,
    RAGQuestionRequest,
    RAGSearchRequest,
    RAGSearchResponse,
)

router = APIRouter()


def _validate_document_scope(
    db: Session, current_user: User, project_id: UUID | None, document_ids: list[UUID] | None
) -> None:
    if project_id and document_ids:
        count = db.scalar(
            select(func.count(Document.id))
            .where(
                Document.user_id == current_user.id,
                Document.project_id == project_id,
                Document.id.in_(document_ids),
            )
        )
        if count != len(document_ids):
            raise HTTPException(status_code=404, detail="One or more documents were not found.")


@router.post("/index/{document_id}", response_model=DocumentIndexResponse)
def index_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_by_id(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or access denied.")
    from app.services.document_processing import process_document

    result = process_document(
        document_id=document.id,
        file_path=document.file_path,
        file_type=document.file_type,
        user_id=current_user.id,
    )
    chunks = db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id)
    )
    if result["status"] == "failed":
        raise HTTPException(status_code=422, detail=result["error"])
    return DocumentIndexResponse(
        document_id=document.id,
        processing_status=result["status"],
        chunks_indexed=chunks or 0,
        message="Document indexed successfully.",
    )


@router.get("/status/{document_id}", response_model=DocumentIndexResponse)
def document_index_status(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_by_id(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or access denied.")
    chunks = db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id)
    )
    return DocumentIndexResponse(
        document_id=document.id,
        processing_status=document.processing_status,
        chunks_indexed=chunks or 0,
        message="Index status retrieved.",
    )


@router.post("/search/semantic", response_model=RAGSearchResponse)
def semantic_search(
    request: RAGSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_document_scope(db, current_user, request.project_id, request.document_ids)
    service = RAGRetrievalService(db)
    results = service.semantic_search(
        request.query,
        user_id=current_user.id,
        project_id=request.project_id,
        document_ids=request.document_ids,
        top_k=request.top_k,
    )
    return RAGSearchResponse(
        query=request.query,
        results=service.construct_context_records(results),
    )


@router.post("/search/hybrid", response_model=RAGSearchResponse)
def hybrid_search(
    request: RAGSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_document_scope(db, current_user, request.project_id, request.document_ids)
    service = RAGRetrievalService(db)
    results = service.hybrid_search(
        request.query,
        user_id=current_user.id,
        project_id=request.project_id,
        document_ids=request.document_ids,
        top_k=request.top_k,
    )
    return RAGSearchResponse(query=request.query, results=service.construct_context_records(results))


@router.post("/ask", response_model=RAGAnswerResponse)
async def ask_question(
    request: RAGQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_document_scope(db, current_user, request.project_id, request.document_ids)
    try:
        result = await RAGQuestionAnsweringService(RAGRetrievalService(db)).answer(
            request.query,
            user_id=current_user.id,
            project_id=request.project_id,
            document_ids=request.document_ids,
            top_k=request.top_k,
            max_tokens=request.max_tokens,
            rerank=request.rerank,
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The configured language model provider is unavailable.",
        ) from exc
    return RAGAnswerResponse(question=request.query, **result)
