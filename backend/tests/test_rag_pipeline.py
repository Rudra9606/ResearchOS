import asyncio
from uuid import uuid4

import pytest

from app.rag.embeddings import EmbeddingError, EmbeddingService
from app.rag.qa import RAGQuestionAnsweringService
from app.rag.reranker import CrossEncoderReranker
from app.rag.retrieval import RAGRetrievalService, tokenize


class FakeEmbeddingModel:
    def encode(self, texts, **kwargs):
        return [[float(len(text)), 0.0, 0.0] for text in texts]


class FakeEmbeddingService:
    def embed_query(self, query):
        return [1.0, 0.0, 0.0]


def test_embedding_service_batches_and_validates_dimension():
    service = EmbeddingService(model=FakeEmbeddingModel(), dimension=3)
    assert service.embed(["one", "two"]) == [[3.0, 0.0, 0.0], [3.0, 0.0, 0.0]]

    invalid = EmbeddingService(model=FakeEmbeddingModel(), dimension=2)
    with pytest.raises(EmbeddingError, match="expected 2"):
        invalid.embed(["one"])


def test_embedding_service_reports_model_loading_failure(monkeypatch):
    class BrokenModel:
        def encode(self, *args, **kwargs):
            raise AssertionError("not reached")

    service = EmbeddingService(model_name="missing", dimension=3)
    monkeypatch.setattr(
        "sentence_transformers.SentenceTransformer",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("load failed")),
    )
    with pytest.raises(EmbeddingError, match="Unable to load"):
        service.embed(["text"])


def test_bm25_tokenizer_and_fusion_are_deterministic():
    assert tokenize("Science-based Research 2") == ["science", "based", "research", "2"]
    first = {"chunk_id": "a", "content": "a", "vector_score": 0.9}
    second = {"chunk_id": "b", "content": "b", "bm25_score": 2.0}
    results = RAGRetrievalService._combine_results([first], [second])
    assert {item["chunk_id"] for item in results} == {"a", "b"}
    assert all(item["combined_score"] > 0 for item in results)


def test_reranker_can_be_disabled_without_loading_model():
    reranker = CrossEncoderReranker(enabled=False)
    results = [{"chunk_id": "1", "content": "evidence"}]
    assert reranker.rerank("question", results) == results


def test_rag_answer_uses_context_and_preserves_citations():
    class FakeRetrieval:
        def retrieve(self, *args, **kwargs):
            return [{
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "document_filename": "paper.txt",
                "chunk_index": 0,
                "content": "Evidence.",
                "chunk_metadata": {},
                "combined_score": 0.5,
            }]

        def construct_context_records(self, results):
            return [{"citation": "[1]", "chunk_id": "chunk-1", "document_id": "doc-1",
                     "document_filename": "paper.txt", "chunk_index": 0,
                     "content": "Evidence.", "metadata": {}}]

        def construct_context(self, results):
            return "[1] Evidence."

    class FakeProvider:
        async def generate_with_context(self, prompt, context, **kwargs):
            assert "[1]" in context
            return "Supported answer [1]."

    result = asyncio.run(
        RAGQuestionAnsweringService(FakeRetrieval(), provider=FakeProvider()).answer(
            "What?", user_id=uuid4()
        )
    )
    assert result["evidence_sufficient"] is True
    assert result["citations"][0]["citation"] == "[1]"


def test_rag_answer_reports_insufficient_evidence():
    class EmptyRetrieval:
        def retrieve(self, *args, **kwargs):
            return []

        def construct_context_records(self, results):
            return []

    class FailingProvider:
        async def generate_with_context(self, *args, **kwargs):
            raise AssertionError("provider must not be called")

    result = asyncio.run(
        RAGQuestionAnsweringService(EmptyRetrieval(), provider=FailingProvider()).answer(
            "Unknown?", user_id=uuid4()
        )
    )
    assert result["evidence_sufficient"] is False
    assert result["citations"] == []
