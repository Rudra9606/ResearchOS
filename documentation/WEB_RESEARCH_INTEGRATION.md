# Web Research Integration

## Architecture

Web research is implemented in
`backend/app/services/web_research_service.py`. The service calls the Tavily
Search API directly over async `httpx`, so the Web Research Agent does not
depend on a provider-specific LangChain tool.

The service:

1. Accepts one query or multiple topic queries.
2. Sends configured search depth, result count, domain, and date filters.
3. Normalizes title, URL, content, domain, publication date, score, and query.
4. Rejects malformed results.
5. Deduplicates URLs across all queries.
6. Maps timeouts, rate limits, and provider failures to shared provider errors.

No fallback or fabricated result is returned when Tavily is unavailable.

## Configuration

Copy the safe template and set values in `backend/.env`:

```env
TAVILY_API_KEY=...
TAVILY_MAX_RESULTS=5
TAVILY_SEARCH_DEPTH=basic
TAVILY_TIMEOUT_SECONDS=30
TAVILY_MAX_RETRIES=2
```

`TAVILY_API_KEY` is required when a web search is executed. The application can
still start without it; the agent records a failed web-search status instead of
inventing sources.

## Workflow and persistence

`WebResearchAgent` calls `WebResearchService.search_topic()` and writes
normalized dictionaries to `research_sources` in the LangGraph state. The
research-run execution endpoint converts those results to
`ResearchSourceCreate` records. Source creation verifies ownership through the
research run and project, and avoids an identical URL being inserted twice for
the same run.

The existing API endpoint remains:

```text
POST /api/v1/research-runs/{run_id}/execute
```

## Error handling

- Empty queries raise validation errors.
- Invalid result rows are skipped.
- HTTP 429 responses become rate-limit errors and are retried according to
  `TAVILY_MAX_RETRIES`.
- Timeouts and transient 5xx responses are retried.
- Missing credentials produce an explicit provider configuration error.
- Provider failures are recorded in workflow state under `research_errors`.

Secrets are sent only in the Tavily request body and are not included in error
messages or logs.

## Testing

The automated tests use `httpx.MockTransport`; no Tavily key or network access
is required. Coverage includes missing keys, normalization, duplicate URLs,
multiple queries, empty results, rate limits, timeouts, and agent no-results
behavior.

## Known limitations

- Live Tavily connectivity is not tested in CI.
- Relevance filtering currently relies on Tavily's score and valid-result
  normalization; domain-specific ranking is not applied.
- Search results are stored in the existing source schema, so query and score
  remain in workflow output but are not separate database columns.
