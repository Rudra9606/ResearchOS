# Report Generation Architecture

## Overview

Phase 6 turns completed research runs into structured, evidence-aware reports.
The report writer consumes the workflow state, preserves only citations supplied
by research results, validates the structured output, and renders the report to
PDF, DOCX, or HTML.

The existing `research_reports` table is reused. Structured report content is
serialized into its `content` field, while the generated export is stored at a
user-scoped path in `file_path`. No database migration is required.

## Report Structure

`StructuredResearchReport` contains these sections:

1. Title
2. Executive summary
3. Research objectives
4. Research questions
5. Methodology
6. Web research findings
7. Academic research findings
8. Document analysis findings
9. Dataset analysis findings
10. Verified claims
11. Limitations
12. Conclusion
13. References

Every research section has an availability flag, content, and evidence IDs.
Sections without evidence are marked unavailable rather than being filled with
unsupported conclusions.

## Report Writer

`ReportWriterAgent` uses the configured Gemini/Ollama provider abstraction for
structured generation. The prompt includes completed workflow evidence,
document and dataset findings, and verified claims. Model-provided references
are not trusted: the writer replaces them with normalized citations derived
from the workflow's research sources.

When no explicit provider is supplied and the configured provider is
unavailable, the writer creates an evidence-only report with unavailable
sections clearly marked. An explicitly injected provider failure is surfaced as
a failed report generation instead of producing fabricated content.

## Citation Handling

`CitationService` validates HTTP(S) URLs, normalizes source metadata, and
deduplicates citations by DOI, arXiv identifier, URL, or normalized title.
Citation metadata includes:

- citation ID and title
- URL
- authors
- publisher or venue
- publication date
- source type
- DOI and arXiv identifier when available

References are formatted in an APA-style form where metadata permits. Citation
validation occurs before export, and report references must originate from
workflow evidence.

## Export Formats

`ReportService` provides:

- **PDF:** ReportLab cover page, table of contents, headings, page breaks,
  headers, footers, page numbers, and references.
- **DOCX:** python-docx title page, heading hierarchy, formatted paragraphs,
  references, and a Word page-number field.
- **HTML:** escaped responsive markup, navigation links, clickable source URLs,
  references, and print-friendly CSS.

Long sections are rendered as flowable paragraphs or document paragraphs so
they can span pages without unsafe string interpolation.

## Storage and Ownership

Exports are stored below:

```text
reports/<authenticated-user-id>/<report-id>.<format>
```

The report's research run must belong to a project owned by the authenticated
user. Download, update, and delete operations verify ownership and reject paths
that resolve outside the user's report directory. Generated files are removed
when their report is deleted.

## API Endpoints

All endpoints require authentication:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/reports/generate` | Generate and export a report for a research run |
| POST | `/api/v1/reports/` | Create a pending report record |
| GET | `/api/v1/reports/` | List the user's reports |
| GET | `/api/v1/reports/{report_id}` | Get report metadata |
| GET | `/api/v1/reports/{report_id}/download` | Download a generated export |
| PATCH | `/api/v1/reports/{report_id}` | Update report metadata |
| DELETE | `/api/v1/reports/{report_id}` | Delete a report and its export |

`POST /reports/generate` accepts a research run ID and `pdf`, `docx`, or `html`
format. A failed export is recorded as a failed report and does not discard
the completed research run.

## Workflow Integration

The research workflow sequence is:

```text
research completion
  -> evidence aggregation
  -> claim verification
  -> report writer
  -> structured report validation
  -> citation validation
  -> export
  -> report persistence
```

The existing research-run execution endpoint defaults to PDF export. The
standalone report generation endpoint can export a completed run in any
supported format.

## Configuration

Report generation uses the existing provider settings and does not add a new
secret or provider. Report files use the configured application storage root
and are constrained to the authenticated user's report directory.
ReportLab and python-docx are already included in `backend/requirements.txt`.

## Testing

Run the focused Phase 6 tests:

```powershell
cd D:\ResearchOS\ResearchOS\backend
.\.venv\Scripts\python.exe -m pytest -q tests/test_report_generation.py
```

Run the complete backend suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The tests cover structured output and fallback behavior, citation
deduplication and validation, actual PDF/DOCX/HTML output, HTML escaping,
source links, authenticated report generation, download behavior, and
ownership-aware API access.
