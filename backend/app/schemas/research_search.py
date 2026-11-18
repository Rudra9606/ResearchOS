"""Normalized results returned by web and academic research providers."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    content: str
    source_domain: str | None = None
    published_date: datetime | None = None
    relevance_score: float | None = None
    search_query: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "summary": self.content,
            "source_domain": self.source_domain,
            "published_date": self.published_date,
            "relevance_score": self.relevance_score,
            "search_query": self.search_query,
            "source_type": "web",
        }


@dataclass(frozen=True)
class AcademicPaper:
    title: str
    authors: tuple[str, ...] = ()
    abstract: str | None = None
    publication_date: datetime | None = None
    doi: str | None = None
    paper_url: str | None = None
    pdf_url: str | None = None
    citation_count: int | None = None
    venue: str | None = None
    publisher: str | None = None
    external_ids: dict[str, str] = field(default_factory=dict)
    provider: str = ""
    provider_id: str | None = None
    categories: tuple[str, ...] = ()

    def dedupe_keys(self) -> set[str]:
        keys = {f"title:{' '.join(self.title.lower().split())}"}
        if self.doi:
            keys.add(f"doi:{self.doi.lower().strip()}")
        if self.provider_id:
            keys.add(f"{self.provider}:{self.provider_id.lower().strip()}")
        for key, value in self.external_ids.items():
            if value:
                keys.add(f"{key.lower()}:{value.lower().strip()}")
        if self.paper_url:
            keys.add(f"url:{self.paper_url.lower().split('#', 1)[0]}")
        return keys

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": ", ".join(self.authors) or None,
            "abstract": self.abstract,
            "summary": self.abstract,
            "publication_date": self.publication_date,
            "doi": self.doi,
            "url": self.paper_url or self.pdf_url,
            "pdf_url": self.pdf_url,
            "citation_count": self.citation_count,
            "venue": self.venue,
            "publisher": self.publisher or self.venue,
            "external_ids": self.external_ids,
            "provider": self.provider,
            "provider_id": self.provider_id,
            "categories": list(self.categories),
            "source_type": "academic",
        }


@dataclass(frozen=True)
class AcademicSearchResult:
    papers: tuple[AcademicPaper, ...]
    provider_errors: dict[str, str] = field(default_factory=dict)

    @property
    def has_results(self) -> bool:
        return bool(self.papers)
