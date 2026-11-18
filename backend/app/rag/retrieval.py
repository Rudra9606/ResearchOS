"""Ownership-scoped vector, BM25, and hybrid retrieval."""

import math
import re
from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.embeddings import get_embedding_service
from app.rag.reranker import CrossEncoderReranker


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Tokenize text consistently for BM25 documents and queries."""
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


class RAGRetrievalService:
    """Retrieve only completed, user-owned document chunks."""

    def __init__(
        self,
        db: Session,
        *,
        embedding_service=None,
        reranker=None,
        bm25_k1: float | None = None,
        bm25_b: float | None = None,
    ):
        self.db = db
        self.embedding_service = embedding_service or get_embedding_service()
        self.reranker = reranker or CrossEncoderReranker()
        self.bm25_k1 = settings.BM25_K1 if bm25_k1 is None else bm25_k1
        self.bm25_b = settings.BM25_B if bm25_b is None else bm25_b

    def hybrid_search(
        self,
        query: str,
        *,
        user_id: UUID,
        project_id: UUID | None = None,
        document_ids: list[UUID] | None = None,
        top_k: int = 10,
        vector_top_k: int | None = None,
        bm25_top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        vector_results = self._vector_search(
            query,
            user_id=user_id,
            project_id=project_id,
            document_ids=document_ids,
            top_k=vector_top_k or settings.RAG_VECTOR_TOP_K,
        )
        keyword_results = self._bm25_search(
            query,
            user_id=user_id,
            project_id=project_id,
            document_ids=document_ids,
            top_k=bm25_top_k or settings.RAG_BM25_TOP_K,
        )
        return self._combine_results(vector_results, keyword_results)[:top_k]

    def semantic_search(
        self,
        query: str,
        *,
        user_id: UUID,
        project_id: UUID | None = None,
        document_ids: list[UUID] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        return self._vector_search(
            query,
            user_id=user_id,
            project_id=project_id,
            document_ids=document_ids,
            top_k=top_k,
        )

    def retrieve(
        self,
        query: str,
        *,
        user_id: UUID,
        project_id: UUID | None = None,
        document_ids: list[UUID] | None = None,
        top_k: int = 5,
        rerank: bool | None = None,
    ) -> list[dict[str, Any]]:
        results = self.hybrid_search(
            query,
            user_id=user_id,
            project_id=project_id,
            document_ids=document_ids,
            top_k=max(top_k * 2, top_k),
        )
        use_reranker = settings.RERANKER_ENABLED if rerank is None else rerank
        if not use_reranker:
            return results[:top_k]
        return self.reranker.rerank(query, results, top_k=top_k)

    @staticmethod
    def construct_context_records(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return citation-ready evidence without duplicate chunk IDs."""
        records = []
        seen: set[str] = set()
        for result in results:
            chunk_id = str(
                result.get("chunk_id")
                or f"{result['document_id']}:{result['chunk_index']}"
            )
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            records.append(
                {
                    "citation": f"[{len(records) + 1}]",
                    "chunk_id": chunk_id,
                    "document_id": str(result["document_id"]),
                    "document_filename": result.get("document_filename"),
                    "chunk_index": result["chunk_index"],
                    "source_url": result.get("source_url"),
                    "content": result["content"],
                    "retrieval_score": result.get("combined_score"),
                    "rerank_score": result.get("rerank_score"),
                    "metadata": result.get("chunk_metadata", {}),
                }
            )
        return records

    @classmethod
    def construct_context(cls, results: list[dict[str, Any]]) -> str:
        """Build a bounded citation-preserving context block."""
        blocks = []
        for record in cls.construct_context_records(results):
            source = (
                f" filename={record['document_filename']}"
                if record.get("document_filename")
                else ""
            )
            blocks.append(
                f"{record['citation']} document={record['document_id']}"
                f"{source} chunk={record['chunk_index']}\n{record['content']}"
            )
        return "\n\n".join(blocks)

    def _base_statement(
        self,
        *,
        user_id: UUID,
        project_id: UUID | None,
        document_ids: list[UUID] | None,
    ):
        stmt = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.user_id == user_id,
                Document.processing_status == "completed",
            )
        )
        if project_id:
            stmt = stmt.where(Document.project_id == project_id)
        if document_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))
        return stmt

    @staticmethod
    def _result(chunk: DocumentChunk, document: Document, **scores) -> dict[str, Any]:
        metadata = chunk.chunk_metadata or {}
        return {
            "chunk_id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "document_filename": document.filename,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "chunk_metadata": metadata,
            "source_url": metadata.get("source_url"),
            **scores,
        }

    def _vector_search(
        self,
        query: str,
        *,
        user_id: UUID,
        project_id: UUID | None = None,
        document_ids: list[UUID] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        query_embedding = self.embedding_service.embed_query(query)
        stmt = self._base_statement(
            user_id=user_id, project_id=project_id, document_ids=document_ids
        ).where(DocumentChunk.embedding.is_not(None))
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        rows = self.db.execute(
            stmt.add_columns(distance.label("vector_distance"))
            .order_by(distance)
            .limit(top_k)
        ).all()
        return [
            self._result(
                chunk,
                document,
                vector_distance=float(vector_distance),
                vector_score=1.0 / (1.0 + float(vector_distance)),
                source="vector",
            )
            for chunk, document, vector_distance in rows
        ]

    def _bm25_search(
        self,
        query: str,
        *,
        user_id: UUID,
        project_id: UUID | None = None,
        document_ids: list[UUID] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        query_terms = tokenize(query)
        if not query_terms:
            return []
        rows = self.db.execute(
            self._base_statement(
                user_id=user_id, project_id=project_id, document_ids=document_ids
            ).where(DocumentChunk.content.is_not(None))
        ).all()
        corpus = [tokenize(chunk.content) for chunk, _ in rows]
        if not corpus:
            return []
        document_count = len(corpus)
        average_length = sum(map(len, corpus)) / document_count or 1.0
        document_frequency = Counter(
            term for tokens in corpus for term in set(tokens)
        )
        scores: list[tuple[float, DocumentChunk, Document]] = []
        for (chunk, document), tokens in zip(rows, corpus):
            frequencies = Counter(tokens)
            score = 0.0
            for term in query_terms:
                if not frequencies[term]:
                    continue
                idf = math.log(
                    1 + (document_count - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
                length_factor = 1 - self.bm25_b + self.bm25_b * len(tokens) / average_length
                score += idf * (
                    frequencies[term] * (self.bm25_k1 + 1)
                    / (frequencies[term] + self.bm25_k1 * length_factor)
                )
            if score > 0:
                scores.append((score, chunk, document))
        scores.sort(key=lambda item: item[0], reverse=True)
        return [
            self._result(
                chunk,
                document,
                bm25_score=score,
                source="bm25",
            )
            for score, chunk, document in scores[:top_k]
        ]

    @staticmethod
    def _combine_results(
        vector_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fuse rankings with Reciprocal Rank Fusion."""
        combined: dict[str, dict[str, Any]] = {}
        rrf_k = settings.RAG_RRF_K
        for source_results in (vector_results, keyword_results):
            for rank, result in enumerate(source_results, start=1):
                chunk_id = result["chunk_id"]
                entry = combined.setdefault(chunk_id, result.copy())
                entry["vector_score"] = entry.get("vector_score", result.get("vector_score", 0))
                entry["bm25_score"] = entry.get("bm25_score", result.get("bm25_score", 0))
                entry["combined_score"] = entry.get("combined_score", 0.0) + 1 / (
                    rrf_k + rank
                )
        return sorted(
            combined.values(), key=lambda item: item["combined_score"], reverse=True
        )
