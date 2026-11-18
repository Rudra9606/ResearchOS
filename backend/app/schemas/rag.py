from uuid import UUID

from pydantic import BaseModel, Field


class RAGSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    project_id: UUID | None = None
    document_ids: list[UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    rerank: bool = True


class RAGEvidence(BaseModel):
    citation: str
    chunk_id: str
    document_id: str
    document_filename: str | None = None
    chunk_index: int
    source_url: str | None = None
    content: str
    retrieval_score: float | None = None
    rerank_score: float | None = None
    metadata: dict = Field(default_factory=dict)


class RAGSearchResponse(BaseModel):
    query: str
    results: list[RAGEvidence]


class RAGQuestionRequest(RAGSearchRequest):
    max_tokens: int = Field(default=800, ge=1, le=4000)


class RAGAnswerResponse(BaseModel):
    question: str
    answer: str
    citations: list[RAGEvidence]
    evidence_sufficient: bool


class DocumentIndexResponse(BaseModel):
    document_id: UUID
    processing_status: str
    chunks_indexed: int
    message: str
