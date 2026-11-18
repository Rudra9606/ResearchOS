# ResearchOS frontend

The frontend is a Next.js App Router application that uses the existing FastAPI API. It supports registration and sign-in, project workspaces, synchronous research runs, document upload, evidence and claim review, report downloads, and RAG questions over project documents. Conversation storage is not presented as AI chat.

## Local development

1. Start the backend from `../backend` using its documented environment and database setup.
2. Copy `.env.example` to `.env.local` and set `BACKEND_URL` to the backend origin (default `http://localhost:8000`).
3. Run `npm install` once, then `npm run dev`.
4. Open `http://localhost:3000`.

The `/api/*` Next route proxies requests to `/api/v1/*` on the backend. It stores the bearer token in an HttpOnly, SameSite=Lax cookie and does not expose that token to page JavaScript. In production, serve the app over HTTPS so the cookie receives the Secure flag. Configure `BACKEND_URL` as a server-side environment variable; it must not use the `NEXT_PUBLIC_` prefix.

## Supported workflows and limits

- The dashboard reflects the selected project's paginated API data; it does not claim organization-wide totals.
- Research execution and document processing/indexing are synchronous backend operations. Keep the page open while a research run is executing.
- The document question panel calls the authenticated RAG ask route and shows the returned answer and sufficiency flag.
- There is no assistant conversation completion endpoint, so conversation records are not presented as an AI chat feature.
- Research execution creates a PDF report. Other formats can be requested using the backend report-generation route; this interface downloads reports already listed by the API.

Run `npm run typecheck`, `npm run lint`, `npm run test:e2e`, and `npm run build` before packaging a release. Install Playwright's Chromium browser once with `npx playwright install chromium` if the runner has no browser available.
