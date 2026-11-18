"""Citation normalization, validation, deduplication, and formatting."""

from urllib.parse import urlparse

from app.schemas.report_document import ReportCitation, StructuredResearchReport


class CitationError(ValueError):
    """Raised when a citation contains invalid source metadata."""


class CitationManager:
    @staticmethod
    def _valid_url(value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CitationError("Citation URLs must be absolute HTTP(S) URLs.")
        return value

    @classmethod
    def from_sources(cls, sources: list[dict]) -> list[ReportCitation]:
        citations: list[ReportCitation] = []
        seen: set[str] = set()
        for index, source in enumerate(sources, start=1):
            title = str(source.get("title") or "").strip()
            if not title:
                continue
            url = cls._valid_url(source.get("url"))
            doi = source.get("doi") or source.get("external_ids", {}).get("DOI")
            arxiv_id = source.get("arxiv_id") or source.get("external_ids", {}).get("arXiv")
            identity = str(doi or arxiv_id or url or title.casefold())
            if identity.casefold() in seen:
                continue
            seen.add(identity.casefold())
            citation_id = f"source-{len(citations) + 1}"
            citations.append(
                ReportCitation(
                    citation_id=citation_id,
                    title=title,
                    url=url,
                    authors=list(source.get("authors") or []),
                    publisher_or_venue=source.get("publisher") or source.get("venue"),
                    publication_date=source.get("publication_date") or source.get("published_date"),
                    source_type=source.get("source_type") or source.get("provider") or "unknown",
                    doi=doi,
                    arxiv_id=arxiv_id,
                )
            )
        return citations

    @staticmethod
    def apa(citation: ReportCitation) -> str:
        authors = ", ".join(citation.authors) if citation.authors else "Unknown author"
        year = ""
        if citation.publication_date:
            year = str(citation.publication_date)[:4]
        publisher = citation.publisher_or_venue or citation.source_type
        suffix = str(citation.url) if citation.url else (
            f"https://doi.org/{citation.doi}" if citation.doi else ""
        )
        return f"{authors} ({year}). {citation.title}. {publisher}. {suffix}".strip()

    @classmethod
    def validate_section_references(
        cls, report: StructuredResearchReport
    ) -> StructuredResearchReport:
        valid_ids = {citation.citation_id for citation in report.references}
        for section in (
            report.executive_summary,
            report.research_objectives,
            report.research_questions,
            report.methodology,
            report.web_research_findings,
            report.academic_research_findings,
            report.document_analysis_findings,
            report.dataset_analysis_findings,
            report.verified_claims,
            report.limitations,
            report.conclusion,
        ):
            section.evidence_ids = [
                evidence_id for evidence_id in section.evidence_ids
                if evidence_id in valid_ids
            ]
        return report
