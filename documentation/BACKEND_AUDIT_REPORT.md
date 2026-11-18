# ResearchOS Backend Audit Report

## Audit scope and verification

This audit covers the backend under `backend/app`, its migrations, dependencies,
API registration, and automated tests. The audit was performed against the
current working tree on 2026-11-18.

Verification performed:

- `python -m pytest -q`: **31 passed**, one existing PyMuPDF deprecation warning.
- FastAPI OpenAPI inspection: **32 API paths registered**.
- `alembic heads`: one head, `1c2a2c96111c`.
- Python module compilation: passed.
- LangGraph smoke execution: completed the configured graph with progress 100.

The test suite is primarily API/authentication and unit-level coverage. It does
not prove connectivity to Gemini, Ollama, Tavily, academic APIs, PostgreSQL
pgvector retrieval, or Sentence Transformers model downloads.

## Architecture summary

The backend is organized into:

- FastAPI routes under `backend/app/api/v1/endpoints`.
- SQLAlchemy models and CRUD functions under `models` and `crud`.
- Pydantic request/response schemas under `schemas`.
- Service wrappers under `services`.
- Agent classes under `agents`.
- LangGraph orchestration under `workflows`.
- Document embedding and retrieval code under `services/document_processing.py`
  and `rag`.
- Alembic migrations under `backend/migrations`.

The separation is recognizable, but several routes call CRUD functions
directly, and several service modules are thin pass-through wrappers rather
than enforcing business rules.

## Component checklist

| Component | Current status | Issues found | Required improvements | Priority |
|---|---|---|---|---|
| Folder structure | Partial | Expected modules exist, but responsibilities overlap between routes and services. | Make routes delegate business operations consistently; keep provider and persistence concerns separate. | Medium |
| API endpoints | Partial | Required endpoint groups are registered, including workflow execution. Pagination validation is inconsistent; several list endpoints calculate totals from the page only. | Add shared bounded pagination and database count queries. Add endpoint tests for every resource and cross-user access. | High |
| Authentication | Working baseline | JWT and Argon2 paths are tested. Registration and user creation duplicate functionality. | Consolidate registration logic in the auth service; handle database races with explicit rollback and consistent error responses. | Medium |
| Authorization | Partial | Most resource CRUD queries filter by user ownership. The document RAG layer accepts document IDs but does not itself enforce the requesting user. | Add user-scoped retrieval joins and tests proving cross-user chunks cannot be retrieved. | Critical |
| Database models | Partial | Relationships and cascade deletes are present. `DocumentChunk.embedding` uses unconstrained `Vector()` with no dimension. | Choose and validate the embedding dimension, then create a safe migration after confirming deployed schema state. | Critical |
| Migrations | Working graph | A single linear head exists. The document migration imports pgvector and creates an unconstrained vector column. | Add only forward migrations after schema review; do not rewrite existing migrations. | High |
| CRUD | Working baseline | CRUD methods commit independently, and invalid state errors are raised as `ValueError`. | Centralize transaction/error policy and expose domain errors without leaking database details. | Medium |
| Services | Partial | Services mostly proxy CRUD. Report generation functions exist, but report orchestration is not connected to all API flows. | Move ownership, state transitions, and orchestration into services; add service-level tests. | Medium |
| Document upload | Partial | Upload validation and extraction exist. Processing is synchronous in the request and embedding/model failures are returned as document failure rather than managed as a job. | Use a background/job boundary, atomic file/database handling, MIME/content validation, and explicit processing events. | High |
| Text extraction | Working baseline | PDF, DOCX, TXT, CSV, and XLSX extraction are implemented. PyMuPDF emits a deprecation warning in the environment. | Validate malformed files and decide on the supported PyMuPDF import/API. Add PDF/DOCX fixture tests. | Medium |
| Embeddings | Incomplete | Sentence Transformers is lazy-loaded and cached in-process, but model name is not passed from settings and vector dimensionality is not validated. | Configure the model from settings, validate output length, and align pgvector schema and indexes. | Critical |
| Vector retrieval | Incomplete | Retrieval uses `l2_distance` while comments describe cosine distance. There is no user ownership join. | Select the intended metric, add the matching pgvector index, enforce user scope, and test against PostgreSQL. | Critical |
| BM25/keyword retrieval | Partial | PostgreSQL full-text search is used as a ts-rank approximation. Query construction joins terms with `|` but uses `plainto_tsquery`, which does not provide a true BM25 implementation. | Define the ranking contract, use a supported PostgreSQL ranking strategy, and test relevance and empty queries. | High |
| Reranking | Partial | CrossEncoder reranking exists and degrades to original order when unavailable. Model loading is not configured or failure-observable. | Add configuration, explicit model failure behavior, and mocked reranker tests. | Medium |
| Context/citations | Partial | Context construction preserves document/chunk identifiers. Research-source citations are not consistently linked to claims or report references. | Define citation records and propagate source IDs through agents, claims, and reports. | High |
| LLM provider integration | Incomplete | `BaseAgent._get_llm()` directly imports Gemini/Ollama clients. There is no reusable provider interface, timeout policy, retry policy, health check, or structured-output adapter. | Implement a provider protocol/service with Gemini and Ollama adapters and mocked tests. | Critical |
| Web research | Incomplete | Tavily is called only inside `WebResearchAgent`; when unavailable it returns an empty list. There is no reusable service, query fan-out, deduplication, relevance filtering, or source persistence in the agent. | Implement a Tavily service with explicit configuration/error states, deduplication, metadata normalization, and persistence. | Critical |
| Academic research | Incomplete | The agent attempts arXiv only. Import/API errors are broadly swallowed and the fallback is an empty result. Semantic Scholar/Crossref support and metadata normalization are absent. | Add a provider service with public API adapters, deduplication, source attribution, and mocked tests. | High |
| Planner agent | Partial | Planner creates deterministic questions and required-agent metadata. It contains a hardcoded false assignment expression for document detection in `planner.py`. | Derive routing from actual workflow state and validate research-depth behavior. | High |
| Document analysis agent | Incomplete | `_analyze_document` returns empty fields with `status="not_available"` and does not query document chunks/RAG. | Connect it to user-scoped retrieval and produce evidence-backed findings only. | Critical |
| Data analyst agent | Incomplete | `_analyze_dataset` returns empty placeholder structures and no dataset model or processing path exists. | Define dataset scope and implement real analysis or explicitly remove the advertised capability. | High |
| Fact checking | Incomplete | Fact checking uses a simple first-three-word overlap heuristic. It does not extract claims from generated research, persist source IDs, or guarantee meaningful confidence scores. | Implement evidence-backed claim extraction/verification with supported, contradicted, and insufficient-evidence outcomes. | Critical |
| Report generation | Partial | PDF, DOCX, and HTML helper functions exist in `report_service.py`. Report content is assembled as Markdown-like text and does not guarantee methodology, references, safe HTML escaping, or citation links. | Build a structured report model/rendering pipeline and test all formats. | High |
| LangGraph workflow | Partial | Graph nodes and conditional routing exist. Agents are not connected to real provider/RAG services, checkpoints are optional, and agent execution records are not automatically persisted per node. | Add state typing, checkpoint configuration, node-level execution persistence, retries, and failure propagation. | Critical |
| Error handling | Partial | Central handlers exist in `main.py`. CRUD uses broad re-raise catches, and workflow execution converts all failures to a generic 502 without a durable diagnostic record. | Use typed domain exceptions, structured error IDs, safe logging, and persisted run/agent failures. | High |
| Logging | Working baseline | Stream logging is initialized and secrets are not intentionally logged. Logging is not structured/correlated by request, run, or agent. | Add request/run correlation and redact provider/database error payloads. | Medium |
| Configuration | Partial | `.env`-backed settings cover database, auth, providers, uploads, and RAG. Provider settings are not validated by provider-specific configuration, and `.env.example` is absent. | Add safe example configuration and startup validation without exposing secrets. | Medium |
| Dependencies | Partial | Requirements include the declared AI/RAG stack and checkpoint SQLite dependency. Some large optional providers/models are imported lazily but there is no optional-dependency policy. | Separate core and optional integrations or document installation/runtime prerequisites. | Medium |
| Automated tests | Partial | 31 tests cover auth, core APIs, chunk validation, TXT extraction, and context formatting. External providers, PostgreSQL vector search, upload processing, report formats, and full workflow persistence are not tested. | Add mocked provider tests and a separate opt-in integration suite. | Critical |
| Frontend readiness | Partial | API paths and response schemas exist for the main resources. Long-running research and document processing are synchronous, and pagination/error contracts are inconsistent. | Stabilize async job semantics, response envelopes, pagination, and OpenAPI examples. | High |

## Confirmed high-risk gaps

1. **No real AI provider abstraction**: agents can instantiate provider clients
   directly, but there is no reusable, testable provider boundary.
2. **No real web/academic result path when configured**: the current web agent
   only calls Tavily inline; the academic agent only attempts arXiv.
3. **Placeholder analysis agents**: document and dataset analysis do not perform
   analysis.
4. **Embedding schema mismatch risk**: `Vector()` has no fixed dimension while
   `all-MiniLM-L6-v2` produces a specific dimension.
5. **RAG authorization gap**: `RAGRetrievalService` filters by document IDs but
   has no user/project ownership parameter.
6. **Fact verification is heuristic**: lexical overlap is not sufficient to
   support or contradict claims.
7. **Workflow persistence is incomplete**: the graph result is returned, but
   agent node execution records and checkpoint lifecycle are not automatically
   persisted by the research run endpoint.
8. **Missing integration evidence**: the passing suite does not establish that
   PostgreSQL pgvector, Gemini, Ollama, Tavily, academic APIs, or model
   downloads work in the target deployment environment.

## Phase 1 conclusion

The backend is a functional scaffold with a passing baseline test suite and
registered CRUD-style APIs, but it is not yet a genuinely integrated AI
research platform. The next implementation phase should begin with the
provider architecture and configuration boundary, followed by real web and
academic services, embedding dimension/schema alignment, and user-scoped RAG.
No destructive database operation is required by this audit.
