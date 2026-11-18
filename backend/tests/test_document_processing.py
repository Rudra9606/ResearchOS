import pytest

from app.rag.retrieval import RAGRetrievalService
from app.services.document_processing import chunk_text, extract_text


def test_chunk_text_rejects_invalid_overlap():
    with pytest.raises(ValueError, match="chunk_overlap"):
        chunk_text("some text", chunk_size=10, chunk_overlap=10)


def test_extract_text_from_txt(tmp_path):
    path = tmp_path / "source.txt"
    path.write_text("Research evidence", encoding="utf-8")

    assert extract_text(str(path), "txt") == "Research evidence"


def test_construct_context_preserves_citations():
    context = RAGRetrievalService.construct_context(
        [
            {
                "document_id": "doc-1",
                "chunk_index": 2,
                "content": "Relevant evidence.",
            }
        ]
    )

    assert "[1] document=doc-1 chunk=2" in context
    assert "Relevant evidence." in context
