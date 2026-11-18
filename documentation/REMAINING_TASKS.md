# ResearchOS task ledger

Updated 2026-11-19 after implementing the frontend, project knowledge graph, and durable background worker path.

## Implemented in this workspace

- [x] Phase 7: backend integration and frontend-readiness audit (details in `FINAL_BACKEND_STATUS.md` and `FINAL_BACKEND_AUDIT.md`).
- [x] Phase 8 foundation: Next.js/React/TypeScript/Tailwind app, registration/sign-in, HttpOnly cookie proxy, project workspaces, research runs with project document/dataset analysis, document upload, RAG questions, sources/claims, report previews plus PDF/DOCX/HTML exports, responsive layouts, user guide, and Playwright browser-flow coverage.
- [x] Project creation, selection, editing, and confirmed deletion are available in the UI. Deletion removes owned upload/report files and refuses while project jobs are active.
- [x] Project scoped knowledge graph API and frontend view. It displays stored claim/source nodes and only links an edge when saved evidence text explicitly references a source URL or distinctive title.
- [x] PostgreSQL-backed research/document jobs with a separate worker, polling, cancellation, retries, and expired-lease recovery. Existing synchronous routes remain available.
- [x] Single-host Docker Compose baseline for PostgreSQL with pgvector, FastAPI, and Next.js, with persistent local database, files, reports, and model cache volumes.
- [x] Deployment, upgrade/rollback, secret-handling, and user guides.

## Remaining before a production release

These items need an architectural implementation or an external staging/operations environment; they are not claimed as complete.

- [x] Add request correlation IDs and JSON logs with basic secret redaction.
- [ ] Add abuse controls/rate limits, run-level correlation across worker executions, metrics, alerting, and error reporting.
- [ ] Provision staging secrets/provider accounts and execute live tests for Gemini or Ollama, Tavily, Semantic Scholar, Crossref, arXiv, and embedding/reranker model loading.
- [ ] Run staging load/timeout tests, review transaction boundaries, exercise database backup/restore, and exercise migration rollback.
- [ ] Select and configure production host, TLS ingress, managed database, object/file storage, secret manager, backups, monitoring, and operational ownership. The Compose file is a baseline, not a production certification.
- [x] Add project-scoped conversation UI with create, review, delete, and evidence-grounded ask actions. Conversation turns persist both messages and citations; unsupported answers explicitly report insufficient evidence.
- [x] Add browser coverage for document job cancellation/retry, DOCX generation/download, and project-grounded conversation asks. The low-level `POST /messages/` route only stores a user message; conversation answers use `/conversations/{id}/ask`.
- [ ] Extend graph semantics with validated entity extraction and richer relationship types if desired. The current graph intentionally models evidence-linked sources and verified claims only.
- [ ] Decide whether frontend dataset histograms should also be embedded as images in PDF/DOCX/HTML reports. Interactive SVG histograms are now shown in the research run view; report image generation is not implemented.

## External requirements

- A local Docker daemon is required to execute the Compose deployment.
- Valid provider credentials and network access are required for live integrations.
- A provisioned staging environment and an explicit deployment target are required to perform the release exercises above.
- No provider keys, database passwords, cloud account credentials, or deployment approvals are stored in this repository.

## Latest local verification

- Backend: 92 tests passed (one PyMuPDF deprecation warning).
- Frontend: typecheck, lint, production build, and seven Playwright flows passed.
- OpenAPI: 44 paths and 60 operations. Alembic reports no model/schema differences at head `6f2bd4a8c190`.
- Docker Compose syntax validation passed. A local container boot could not be verified because the Docker engine pipe is unavailable in this environment.
