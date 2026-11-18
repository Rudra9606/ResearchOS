# ResearchOS Backend Status — Phase 7+ Follow-on

**Status:** Phase 7 baseline complete; durable worker and frontend follow-on work are implemented.  
**Assessment:** Local application and worker are verified. This does not certify production readiness or live external-provider operation.  
**Audited workspace:** `D:\ResearchOS\ResearchOS`  
**Date:** 2026-11-19

## Architecture

FastAPI exposes versioned routes at `/api/v1`. The backend separates SQLAlchemy models/CRUD, Pydantic schemas, services, providers, LangGraph agents/workflows, document processing, RAG, and report generation. PostgreSQL stores projects, conversations/messages, documents/chunks, research runs, durable jobs, agent executions, sources, verified claims, and report metadata. Uploaded documents and generated reports are stored on the local filesystem.

Workflow stages are request coordination and planning, web search, academic search, optional document and dataset analysis, fact checking, report writing, and persistence. Agents write progress and execution records while the run is in progress. Source/claim/report artifacts are exposed through user-scoped routes.

## Implemented capabilities

- Argon2 password hashing and bearer JWT registration/login.
- User-owned projects, conversations, messages, documents, research runs, sources, claims, reports, and agent-execution reads.
- Gemini and Ollama provider adapters; Tavily and Semantic Scholar/Crossref/arXiv clients.
- PDF, DOCX, TXT, CSV, and XLSX extraction; CSV/XLSX descriptive analysis.
- Sentence Transformers embeddings with dimension validation; PostgreSQL pgvector cosine search, Python BM25, reciprocal-rank hybrid fusion, and optional Cross-Encoder reranking.
- Evidence-grounded document analysis and claim verification with source attribution rules.
- Structured citation-aware report writing and PDF/DOCX/HTML export.
- Protected report downloads and ownership-filtered RAG/search.
- PostgreSQL-backed research and document jobs, a separate worker, lease recovery, retries, and cooperative cancellation checkpoints.

See [FRONTEND_API_INTEGRATION.md](FRONTEND_API_INTEGRATION.md) for all current routes, payload schemas, responses, auth requirements, errors, examples, and frontend limitations.

## Verification

- Phase 7 closeout: **79 passed**. Current full suite after graph, request-correlation, durable-worker, dataset visualization, project deletion, and grounded conversation chat coverage: **92 passed**, one existing PyMuPDF `fitz` deprecation warning.
- Python AST parsing: **112 source and test files passed**.
- Current OpenAPI generation: **44 paths, 60 operations**.
- `alembic heads`: one head, `6f2bd4a8c190`.
- Connected local database migration revision: `6f2bd4a8c190` (head).
- `alembic check`: no new upgrade operations detected.
- PostgreSQL inspection: 13 public tables, 15 foreign-key constraints, pgvector 0.8.7, `document_chunks.embedding` is `vector(384)`, cosine IVFFlat index `ix_document_chunks_embedding_cosine` exists.
- The embedding migration was reviewed and applied after confirming the target table had zero rows/embeddings. No existing chunk data was converted or removed.
- Added automated integration coverage that traverses a real LangGraph run with mocked research/LLM providers, verifies run/source/claim/agent/report persistence, exports and downloads the PDF, and checks duplicate execution is rejected.
- Added PostgreSQL vector-search coverage proving cosine retrieval works and excludes another user's document.
- Added security checks for profile isolation, server-owned evidence/progress fields, upload size/signature handling, and pagination limits/counts.
- Provider HTTP and model calls in the suite are mocked. No live Gemini, Ollama, Tavily, academic API, external model download, or deployment test was performed.

## Database

The local development database is aligned with repository head. The vector migration changed the embedding column to dimension 384 and created the cosine index. Future deployments must independently inspect their current Alembic revision, extension, column type, index, and vector dimensions before applying migrations. Do not assume another environment matches this local database.

No models/tables were recreated in the development database. The migration advanced only the pending revision after confirming there were no document chunks to convert.

## Security and reliability changes in this phase

- User profile list and detail APIs are self-only; account creation remains at registration.
- Client APIs can no longer forge research sources, verified claims, agent statuses, document statuses, run progress/status, or report status/content/file paths. Those values are written by server workflow paths.
- Research execution uses a row lock to claim a pending run exactly once; repeat execution returns `409`.
- Uploads stream in bounded chunks, use randomized per-user paths, enforce configured size, validate PDF/Office container signatures/structure, limit Office archive expansion, and clean up files if validation or database registration fails.
- List pages are bounded to 100. Endpoints with total envelopes now query the full caller-scoped total.
- Database health output no longer discloses the server version.
- Requests return a validated `X-Request-ID`; application logs are JSON formatted and redact common bearer/secret-field patterns.
- Durable jobs are user-scoped. PostgreSQL row locks and leases allow recovery after worker interruption; delivery is at-least-once. Research retries clear prior outputs to avoid duplicate evidence. Cancellation is cooperative between agents/chunks.

## Setup and operation

Use Python 3.12 and install dependencies from `backend/requirements.txt`. Configure `backend/.env` from `.env.example` without overwriting an existing local environment file. Required settings include `DATABASE_URL` and `SECRET_KEY`; provider credentials are needed for live research.

PowerShell startup from the backend directory:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API root is `http://localhost:8000`, API prefix is `/api/v1`, OpenAPI is `/openapi.json`, and Swagger UI is `/docs`.

Run the background worker from `backend` with `.\.venv\Scripts\python.exe -m app.worker`. `/research-runs/{id}/enqueue` and document upload with `background=true` use the worker; synchronous compatibility routes remain available.

Safe full-suite command from `backend` (uses a unique workspace-local temp directory and an isolated temporary local database):

```powershell
$testTemp = "pytest-temp-$([guid]::NewGuid().ToString('N'))"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=$testTemp
```

The test fixture only creates a uniquely named database on loopback PostgreSQL, sourced from `TEST_DATABASE_URL` or the expected local `researchos` configuration, and drops only that generated database. It rejects remote hosts and unexpected database names.

## Frontend readiness

The API supports registration/login, project CRUD and safe artifact cleanup on deletion, synchronous and queued research runs, project-scoped evidence-grounded conversation answers with persisted citations, document upload/background indexing, source and claim exploration, agent progress reads, RAG search/ask, report generation/previews, protected downloads, and per-user job polling/cancel/retry.

There is no dashboard aggregate endpoint, general-purpose unconstrained chat route, or refresh-token/password-reset flow. Conversation answers are bounded to evidence retrieved from the owning project’s indexed documents. The frontend and project-scoped source/claim graph exist; the graph does not perform general entity extraction. Synchronous compatibility routes remain alongside durable jobs.

## Remaining limitations

- **Not production-ready:** no live deployment, load test, monitoring/alerting, backup/restore exercise, or rate-limit system was verified.
- The worker is at-least-once. Provider requests already in progress cannot be interrupted; cancellation takes effect at the next agent/chunk checkpoint.
- Provider integrations and embedding/reranker model download were not live-tested; external API availability and credentials are environment-dependent.
- The test suite verifies mocked provider paths and real local PostgreSQL vector operations, not live internet services.
- Dataset histogram aggregates are rendered as SVG in the frontend. Report exports do not yet embed dataset chart images.
- Deployment remains a local Compose baseline; there is no live deployment, external provider validation, rate limiting, monitoring, or backup/restore exercise.

**Phase 7 conclusion:** the backend was integrated and verified sufficiently for frontend development against the documented API. Phase 8 and the initial Phase 9/10 implementations are recorded in [PROJECT_STATUS.md](PROJECT_STATUS.md). Production deployment still requires the outstanding reliability and live-environment work.
