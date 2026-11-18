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
- [x] Updated project/default examples from stale Gemini model names to the official stable `gemini-3.5-flash-lite` model. The actual ignored `.env` was not changed.
- [x] Added provider credential rejection handling that reports HTTP 401/403 responses without exposing secrets or response payloads.
- [x] Documented Tavily HTTP 401 and Semantic Scholar rate-limit/optional-key behavior.

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
- Valid Gemini API access and network access are required for a live Gemini check.
- The Tavily key must be corrected or rotated because an earlier live check returned HTTP 401.
- Semantic Scholar is optional; configure `SEMANTIC_SCHOLAR_API_KEY` if a key is available and higher/owned rate-limit allowance is required. Crossref and arXiv require network access but no project-specific key.
- Docker access on the host is required to build, boot, and verify the Compose baseline.
- A provisioned staging environment and an explicit deployment target are required to perform the release exercises above.
- Staging/production needs: TLS ingress, managed or staging PostgreSQL, persistent upload/report storage, secret manager, backup/restore tooling, monitoring/alerts, operational ownership, and deployment approval.
- The repository owner must review and, if needed, replace values in the ignored local `backend/.env`; this session did not overwrite it and did not expose any secret values.
- No provider keys, database passwords, cloud account credentials, or deployment approvals are stored in this repository.

## Latest local verification

- Backend: 92 tests passed (one PyMuPDF deprecation warning).
- Frontend: typecheck, lint, production build, and seven Playwright flows passed.
- OpenAPI: 44 paths and 60 operations. Alembic reports no model/schema differences at head `6f2bd4a8c190`.
- Docker Compose syntax validation passed. A local container boot could not be verified because the Docker engine pipe is unavailable in this environment.
