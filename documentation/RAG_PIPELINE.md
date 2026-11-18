# Advanced RAG pipeline

## Retrieval

Every retrieval query joins `document_chunks` to `documents` and requires the
authenticated user's ID plus completed document status. Optional project and
document filters are applied to both vector and BM25 retrieval, so a chunk
cannot cross an ownership boundary.

Semantic retrieval embeds the query and orders pgvector results by cosine
distance. Keyword retrieval is a genuine in-process BM25 implementation:
document chunks are tokenized, term frequency and document frequency are
calculated for the ownership-filtered corpus, and configurable `BM25_K1` and
`BM25_B` parameters are applied.

Hybrid retrieval combines vector and BM25 rankings using Reciprocal Rank Fusion
with `RAG_RRF_K`, deduplicates chunk IDs, and preserves original scores and
metadata. Optional Cross-Encoder reranking uses
`RERANKER_MODEL`; disabling it leaves the hybrid ranking usable.

## Context and answers

Context records preserve document ID, filename, chunk ID/index, source URL when
present, metadata, retrieval score, and reranker score. Duplicate chunks are
removed before context construction. If no owned evidence is retrieved, the
answer service returns an explicit insufficient-evidence response and does not
call the LLM. Otherwise it calls the configured Gemini/Ollama provider with
citation markers such as `[1]`.

## Endpoints

- `POST /api/v1/rag/index/{document_id}` — extract, chunk, embed, and index a
  user-owned document.
- `GET /api/v1/rag/status/{document_id}` — return processing and chunk status.
- `POST /api/v1/rag/search/semantic` — ownership-scoped vector search.
- `POST /api/v1/rag/search/hybrid` — vector plus BM25 search.
- `POST /api/v1/rag/ask` — retrieve evidence and generate a cited answer.

All request bodies are Pydantic validated and require the existing JWT
authentication dependency.

## Configuration and testing

Relevant settings include `RAG_VECTOR_TOP_K`, `RAG_BM25_TOP_K`, `RAG_RRF_K`,
`BM25_K1`, `BM25_B`, `RERANKER_ENABLED`, `RERANKER_MODEL`, and
`RERANKER_DEVICE`. Tests mock embedding models, rerankers, and LLM providers;
they do not require paid APIs. PostgreSQL/pgvector integration should be run
against the configured test database after applying migrations.
