# Frontend API Integration Guide

**API base:** `{BACKEND_URL}/api/v1` (local default: `http://localhost:8000/api/v1`)  
**Source of truth:** live FastAPI OpenAPI at `{BACKEND_URL}/openapi.json` and Swagger UI at `{BACKEND_URL}/docs`.  
**Audited routes:** 44 OpenAPI paths and 60 operations.

## Authentication and common behavior

Use a bearer token for protected API calls:

```http
Authorization: Bearer <access_token>
```

Registration and login return `AuthResponse`:

```json
{
  "message": "Login successful.",
  "user": {"id": "<uuid>", "name": "Ada", "email": "ada@example.com"},
  "token": {"access_token": "<jwt>", "token_type": "bearer"}
}
```

`POST /auth/login` uses `application/x-www-form-urlencoded` fields `username` (the email) and `password`. `POST /auth/register` uses JSON fields `name`, `email`, and `password` (8–128 characters). There is no refresh-token or password-reset route.

Unless listed as public below, endpoints require authentication. Common errors are `401` for missing/invalid bearer tokens, `404` for missing or inaccessible user-owned records, and `422` for schema/query validation. A `204` response has no body. Validation errors use FastAPI's `detail` error shape; application errors generally use `{"detail":"..."}`.

The API returns an `X-Request-ID` response header for every request. A valid caller-supplied value (ASCII letters, digits, `.`, `_`, `-`, up to 64 characters) is propagated; other values are replaced with a generated ID. Backend application logs are JSON formatted and include the request ID.

Public endpoints are `GET /`, `GET /health`, `GET /api/v1/database/check`, `POST /api/v1/research/validate`, and the auth registration/login endpoints. The database check returns a generic status and does not expose the database server version.

| Method and path | Auth | Request | Response |
|---|---|---|---|
| `GET /` | No | None | `200` service greeting/status |
| `GET /health` | No | None | `200 {status, application}` |
| `GET /api/v1/database/check` | No | None | `200 {status, message}`; message is generic |
| `POST /api/v1/research/validate` | No | JSON `{research_topic, research_depth?}` | `200 {status, message, data?}`; invalid depth returns status `error` in the JSON body |

List endpoints that accept `skip` and `limit` require `skip >= 0` and `1 <= limit <= 100`. Project, document, source, claim, report, and agent-execution response envelopes include a `total` count. Conversation, message, and research-run list responses are arrays and do not include a count envelope.

## Endpoint reference

All paths below are relative to `/api/v1` unless they begin with `/`.

### Authentication, users, and projects

| Method and path | Auth | Request | Response | Main errors |
|---|---|---|---|---|
| `POST /auth/register` | No | JSON `UserCreate` | `201 AuthResponse` | `409` duplicate email, `422` invalid input |
| `POST /auth/login` | No | Form `username`, `password` | `200 AuthResponse` | `401` invalid credentials |
| `POST /research/validate` | No | JSON `{research_topic, research_depth?}` | `200` validation result | `422` malformed input |
| `GET /users/` | Yes | None | `200 UserResponse[]` containing only the caller | `401` |
| `GET /users/{user_id}` | Yes | UUID path | `200 UserResponse` (self only) | `404` other/missing user |
| `PUT /users/{user_id}` | Yes | JSON `UserUpdate` (`name?`) | `200 UserResponse` (self only) | `403` other user, `404` |
| `DELETE /users/{user_id}` | Yes | UUID path (self only) | `204` | `403`, `404` |
| `POST /projects/` | Yes | JSON `ProjectCreate`: `title`, `research_topic`, `description?` | `201 ProjectResponse` | `401`, `422` |
| `GET /projects/?skip=0&limit=100` | Yes | Query pagination | `200 ProjectListResponse {total, projects[]}` | `422` invalid pagination |
| `GET /projects/{project_id}` | Yes | UUID path | `200 ProjectResponse` | `404` |
| `PUT /projects/{project_id}` | Yes | JSON `ProjectUpdate` | `200 ProjectResponse` | `404`, `422` |
| `DELETE /projects/{project_id}` | Yes | UUID path | `204` | `404` |

`ProjectResponse` fields: `id`, `user_id`, `title`, `research_topic`, `description`, `status`, `created_at`, `updated_at`. The list's `total` is the full caller-owned count, not just the page size.

Example project request:

```json
{"title":"Healthcare AI","research_topic":"Impact of AI on healthcare in Germany","description":"Evidence review"}
```

### Conversations and messages

| Method and path | Auth | Request | Response | Main errors |
|---|---|---|---|---|
| `POST /conversations/` | Yes | JSON `ConversationCreate`: `project_id`, `title?` | `201 ConversationResponse` | `404` inaccessible project, `422` |
| `GET /conversations/?skip=0&limit=100` | Yes | Query pagination | `200 ConversationResponse[]` | `422` |
| `GET /conversations/{conversation_id}` | Yes | UUID path | `200 ConversationResponse` | `404` |
| `POST /conversations/{conversation_id}/ask` | Yes | JSON `ConversationAskRequest`: `query` (1â€“4,000 chars), `max_tokens?` | `200 ConversationTurnResponse` with persisted user/assistant messages and citations | `404` inaccessible conversation, `422`, `502` configured LLM unavailable |
| `PUT /conversations/{conversation_id}?title=...` | Yes | `title` query parameter | `200 ConversationResponse` | `404`, `422` |
| `DELETE /conversations/{conversation_id}` | Yes | UUID path | `204` | `404` |
| `POST /messages/?conversation_id={uuid}` | Yes | JSON `MessageCreate`: `content` (1–20,000 chars) | `201 MessageResponse` | `404` inaccessible conversation, `422` |
| `GET /messages/{message_id}` | Yes | UUID path | `200 MessageResponse` | `404` |
| `GET /messages/conversation/{conversation_id}?skip=0&limit=100` | Yes | UUID path and query pagination | `200 MessageResponse[]` | `404`/`422` |
| `DELETE /messages/{message_id}` | Yes | UUID path | `204` | `404` |

`POST /conversations/{conversation_id}/ask` answers from the owning project’s indexed documents, passes up to 12 recent messages as bounded untrusted context, and atomically persists both the user question and assistant answer with citation references. It returns structured citations and an evidence-sufficiency flag. If no evidence is retrieved, the saved answer says so. `POST /messages/` remains a user-message storage route and does not generate an answer.

Example conversation turn:

```http
POST /api/v1/conversations/{conversation_id}/ask
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{"query":"What outcome did the study measure?","max_tokens":800}
```

The response contains `user_message`, `assistant_message`, `citations[]`, and `evidence_sufficient`. The assistant message content includes a readable citation list so the answer remains traceable when history is reopened.

### Documents and research runs

| Method and path | Auth | Request | Response | Main errors |
|---|---|---|---|---|
| `POST /documents/upload?project_id={uuid}` | Yes | Multipart `file`; PDF, DOCX, TXT, CSV, XLSX; default maximum 50 MB | `201 DocumentResponse` with processing status | `404` project, `400` unsupported/invalid file, `413` size, `422` |
| `POST /documents/upload?project_id={uuid}&background=true` | Yes | Multipart `file`; durably queues processing | `201 DocumentResponse` initially in `queued` status | `404`, `400`, `413`, `409` |
| `GET /documents/?project_id={uuid}&skip=0&limit=100` | Yes | Project ID and pagination | `200 DocumentListResponse {total, documents[]}` | `422` |
| `GET /documents/{document_id}` | Yes | UUID path | `200 DocumentResponse` | `404` |
| `DELETE /documents/{document_id}` | Yes | UUID path | `204` | `404` |
| `POST /research-runs/` | Yes | JSON `ResearchRunCreate`: `project_id`, `research_topic` (5–500 chars), `research_depth` (`basic`, `standard`, `comprehensive`) | `201 ResearchRunResponse` | `404` project, `422` |
| `GET /research-runs/?project_id={uuid}&skip=0&limit=100` | Yes | Project ID and pagination | `200 ResearchRunResponse[]` | `422` |
| `GET /research-runs/{run_id}` | Yes | UUID path | `200 ResearchRunResponse` | `404` |
| `GET /research-runs/{run_id}/status` | Yes | UUID path | `200 ResearchRunStatusResponse` | `404` |
| `POST /research-runs/{run_id}/execute?document_ids={uuid}&dataset_ids={uuid}` | Yes | Optional repeated UUID query parameters | `200 ResearchRunResponse` after execution finishes | `404` inaccessible run/file, `409` already started, `502` workflow/provider failure |
| `POST /research-runs/{run_id}/enqueue?document_ids={uuid}&dataset_ids={uuid}` | Yes | Optional repeated UUID query parameters | `202 ResearchJobResponse` | `404` inaccessible run/file, `409` already started |
| `DELETE /research-runs/{run_id}` | Yes | UUID path | `204` | `404` |

`ResearchRunStatusResponse` exposes `research_run_id`, `status`, `progress`, `current_step`, `error_message`, `started_at`, and `completed_at`. Status/progress are controlled by the workflow; there is no client write route. The legacy execution request is synchronous. For durable work use `/enqueue`; poll `/jobs/{job_id}` and use the job's `/cancel` or `/retry` routes. Dataset IDs must identify caller-owned CSV/XLSX documents in the same project. The worker writes a PDF report when report generation succeeds. Cancellation takes effect between agent steps; it cannot interrupt a provider request already in progress.

Upload progress is not streamed. With `background=true`, poll `GET /documents/{document_id}` and `GET /rag/status/{document_id}` after upload. Without the flag, processing remains synchronous for compatibility. Run the separate worker with `python -m app.worker`.

### Sources, agents, claims, and reports

| Method and path | Auth | Request | Response | Main errors |
|---|---|---|---|---|
| `GET /research-sources/?research_run_id={uuid}&skip=0&limit=100` | Yes | Run ID and pagination | `200 ResearchSourceListResponse {total, sources[]}` | `404`/`422` |
| `GET /research-sources/{source_id}` | Yes | UUID path | `200 ResearchSourceResponse` | `404` |
| `DELETE /research-sources/{source_id}` | Yes | UUID path | `204` | `404` |
| `GET /agent-executions/?research_run_id={uuid}&skip=0&limit=100` | Yes | Run ID and pagination | `200 AgentExecutionListResponse {total, executions[]}` | `422` |
| `GET /agent-executions/{execution_id}` | Yes | UUID path | `200 AgentExecutionResponse` | `404` |
| `GET /verified-claims/?research_run_id={uuid}&skip=0&limit=100` | Yes | Run ID and pagination | `200 VerifiedClaimListResponse {total, claims[]}` | `422` |
| `GET /verified-claims/{claim_id}` | Yes | UUID path | `200 VerifiedClaimResponse` | `404` |
| `DELETE /verified-claims/{claim_id}` | Yes | UUID path | `204` | `404` |
| `POST /reports/generate` | Yes | JSON `{research_run_id, report_format?}`; format `pdf`, `docx`, or `html` (default `pdf`) | `201 ReportGenerateResponse` | `404` run, `502` generation/export failure |
| `POST /reports/?research_run_id={uuid}` | Yes | JSON `ResearchReportCreate`: `title`, `content?`, `report_format?` | `201 ResearchReportResponse` | `404`, `422` |
| `GET /reports/?research_run_id={uuid}&skip=0&limit=100` | Yes | Run ID and pagination | `200 ResearchReportListResponse {total, reports[]}` | `422` |
| `GET /reports/{report_id}` | Yes | UUID path | `200 ResearchReportResponse` | `404` |
| `GET /reports/{report_id}/download?format=pdf` | Yes | UUID path; optional `format=pdf\|docx\|html` | File response | `404` unavailable/unauthorized file |
| `DELETE /reports/{report_id}` | Yes | UUID path | `204` | `404` |

Sources, claims, agent executions, document statuses, run progress/status, and generated report status/content cannot be inserted or altered through client routes. They are written by server workflows. Source and claim deletion remains user-scoped. This protects evidence and progress integrity.

`ReportGenerateResponse` fields are `report_id`, `generation_status`, `report_format`, and `file_path`. Treat `file_path` as informational server metadata; download through the protected endpoint.

### RAG

| Method and path | Auth | Request | Response | Main errors |
|---|---|---|---|---|
| `POST /rag/index/{document_id}` | Yes | UUID path | `200 DocumentIndexResponse` | `404`, `422` extraction/embedding failure |
| `GET /rag/status/{document_id}` | Yes | UUID path | `200 DocumentIndexResponse` | `404` |
| `POST /rag/search/semantic` | Yes | JSON `RAGSearchRequest` | `200 RAGSearchResponse` | `404` inaccessible scope, `422` |
| `POST /rag/search/hybrid` | Yes | JSON `RAGSearchRequest` | `200 RAGSearchResponse` | `404`, `422` |
| `POST /rag/ask` | Yes | JSON `RAGQuestionRequest` | `200 RAGAnswerResponse` | `404`, `422`, `502` configured LLM unavailable |
| `GET /knowledge-graph/?project_id={uuid}` | Yes | Project UUID query | `200 {project_id, nodes[], edges[]}` | `404` inaccessible project |
| `GET /jobs/{job_id}` | Yes | Job UUID | `200 ResearchJobResponse` | `404` inaccessible job |
| `POST /jobs/{job_id}/cancel` | Yes | No body | `200 ResearchJobResponse` | `404`, `409` terminal job |
| `POST /jobs/{job_id}/retry` | Yes | No body | `202 ResearchJobResponse` | `404`, `409` non-retryable state |

`RAGSearchRequest`: `query` (1–4,000 chars), `project_id?`, `document_ids?`, `top_k` (1–50, default 5), `rerank` (default true). `RAGQuestionRequest` also accepts `max_tokens` (1–4,000; default 800). Search responses contain evidence records with chunk/document IDs, filenames, content, and scores. Ask responses contain `question`, `answer`, `citations`, and `evidence_sufficient`.

Example:

```json
{
  "query": "What evidence discusses clinical outcomes?",
  "project_id": "<project-uuid>",
  "document_ids": ["<document-uuid>"],
  "top_k": 5,
  "rerank": true
}
```

The project knowledge graph is computed from persisted research runs, sources, and verified claims. Nodes represent stored sources and claims. A claim-to-source edge is emitted only when the saved claim evidence text contains the source's exact URL or a source title of at least 12 characters. Topic similarity does not create graph links.

## Frontend capability boundaries

- Dashboard totals are not exposed by a dedicated endpoint. Derive supported counts from paginated project/run/report lists or add a backend endpoint later.
- Conversation `/ask` invokes project-scoped document RAG and stores grounded assistant turns; general web-research chat outside that evidence scope is not provided.
- Research and document processing support durable worker jobs plus synchronous compatibility routes. Worker delivery is at-least-once; an interrupted attempt can run again.
- Report previews use persisted Markdown-like `content`; report sections are not stored as a separate JSON field.
- The run execution endpoint exports PDF. Use `POST /reports/generate` for the PDF, DOCX, and HTML generation endpoint.
- The knowledge graph includes sources and claims only; entity extraction and broader relationship types are not implemented.
