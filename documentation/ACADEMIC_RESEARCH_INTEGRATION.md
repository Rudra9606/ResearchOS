# Academic Research Integration

## Architecture

Academic search is implemented in
`backend/app/services/academic_research_service.py` using three async clients:

- `SemanticScholarClient`
- `CrossrefClient`
- `ArxivClient`

`AcademicResearchService` invokes all enabled public providers, normalizes
metadata into `AcademicPaper`, deduplicates by DOI/provider identifiers/title,
and returns `AcademicSearchResult` with both papers and provider errors.

Missing metadata is preserved as `None` or an empty collection. No paper or
citation is synthesized.

## Providers

### Semantic Scholar

Uses the Academic Graph paper search endpoint. It retrieves titles, authors,
abstracts, publication dates, DOI/external IDs, URLs, venues, open-access PDF
URLs, and citation counts when available.

### Crossref

Uses the Crossref Works endpoint. It retrieves titles, authors, abstracts,
publication dates, DOI, publisher, venue, and URL. If `CROSSREF_MAILTO` is set,
it is included in the User-Agent contact value.

### arXiv

Uses the arXiv Atom API. XML is parsed with the standard library, including
titles, authors, abstracts, dates, arXiv IDs, abstract/PDF URLs, and categories.
Malformed XML is reported as a provider response error.

## Configuration

```env
ACADEMIC_SEARCH_ENABLED=true
ACADEMIC_MAX_RESULTS=5
ACADEMIC_TIMEOUT_SECONDS=30
SEMANTIC_SCHOLAR_API_KEY=
CROSSREF_MAILTO=
```

Semantic Scholar accepts unauthenticated requests, so its key is optional.
Crossref and arXiv are also usable without credentials. A provider failure is
reported in `AcademicSearchResult.provider_errors`; successful providers can
still contribute results.

## Workflow and persistence

`AcademicResearchAgent` calls the unified academic service and adds normalized
paper dictionaries to the existing LangGraph `research_sources` state. The
research-run execution endpoint persists valid sources through the existing
`ResearchSource` CRUD path, which validates the authenticated user's ownership
of the run's project.

Academic sources use `source_type="academic"` and preserve provider, DOI,
external IDs, venue, publisher, authors, abstract, and URLs in workflow data.
The current database schema stores the compatible title, URL, source type,
authors, publication date, publisher, and summary fields.

## Error handling

- Empty topics are rejected.
- Invalid JSON or XML responses are explicit provider response errors.
- Rate limits, timeouts, and transient HTTP failures use bounded retries.
- Missing optional metadata does not fail an otherwise valid paper.
- Duplicate papers are removed using DOI, provider identifiers, external IDs,
  URLs, and normalized titles.
- If all providers return no papers without errors, the agent reports
  `academic_search_status="no_results"`.
- Provider failures produce `academic_search_status="failed"` and populate
  `research_errors`.

## Testing

Tests use `httpx.MockTransport` and local XML/JSON fixtures. They cover
successful and malformed responses, missing DOI/authors/abstracts, duplicate
papers, rate limits, XML parsing, invalid XML, unified deduplication, and agent
no-results state. No academic API keys or network access are required.

## Known limitations

- Live provider connectivity and current provider quotas are not verified by
  the automated suite.
- Academic relevance ranking currently follows provider result ordering after
  deduplication; a cross-provider reranker is not yet included.
- Citation count and richer provider metadata are retained in workflow objects
  but are not separate columns in the existing `research_sources` table.
