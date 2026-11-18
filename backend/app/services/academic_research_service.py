"""Semantic Scholar, Crossref, and arXiv academic research integration."""

import asyncio
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.providers.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from app.providers.http import raise_for_provider_response, request_error
from app.schemas.research_search import AcademicPaper, AcademicSearchResult


def _date_from_parts(parts: Any) -> datetime | None:
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return None
    values = parts[0]
    if not values or not isinstance(values[0], int):
        return None
    year = values[0]
    month = values[1] if len(values) > 1 and isinstance(values[1], int) else 1
    day = values[2] if len(values) > 2 and isinstance(values[2], int) else 1
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def _date_from_string(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clean_abstract(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return re.sub(r"<[^>]+>", "", html.unescape(value)).strip() or None


class AcademicProviderClient:
    """Shared retrying HTTP behavior for academic provider clients."""

    name = "academic"

    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self._transport,
        )

    async def _get(
        self,
        url: str,
        *,
        params: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            try:
                async with self._client() as client:
                    response = await client.get(url, params=params, headers=headers)
                raise_for_provider_response(response, self.name)
                return response
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if attempt >= self.max_retries:
                    raise request_error(self.name, exc) from exc
                await asyncio.sleep(min(2**attempt, 8))
            except (ProviderRateLimitError, ProviderUnavailableError):
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(min(2**attempt, 8))
        raise ProviderUnavailableError(f"{self.name} request could not be completed.")


class SemanticScholarClient(AcademicProviderClient):
    name = "Semantic Scholar"
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, *, api_key: str | None, **kwargs: Any):
        super().__init__(**kwargs)
        self.api_key = api_key

    async def search(self, query: str, limit: int) -> list[AcademicPaper]:
        fields = (
            "title,authors,abstract,year,publicationDate,venue,externalIds,"
            "url,openAccessPdf,citationCount"
        )
        headers = {"x-api-key": self.api_key} if self.api_key else None
        response = await self._get(
            self.endpoint,
            params={"query": query, "limit": limit, "fields": fields},
            headers=headers,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Semantic Scholar returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError(
                "Semantic Scholar returned an invalid response shape."
            )
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise ProviderResponseError(
                "Semantic Scholar returned an invalid response shape."
            )
        papers = []
        for item in data:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            authors = tuple(
                author.get("name", "").strip()
                for author in item.get("authors", [])
                if isinstance(author, dict) and author.get("name")
            )
            external_ids = {
                str(key): str(value)
                for key, value in (item.get("externalIds") or {}).items()
                if value
            }
            open_access = item.get("openAccessPdf") or {}
            papers.append(
                AcademicPaper(
                    title=str(item["title"]).strip(),
                    authors=authors,
                    abstract=_clean_abstract(item.get("abstract")),
                    publication_date=(
                        _date_from_string(item.get("publicationDate"))
                        or _date_from_parts([[item["year"]]] if item.get("year") else None)
                    ),
                    doi=external_ids.get("DOI"),
                    paper_url=item.get("url"),
                    pdf_url=open_access.get("url") if isinstance(open_access, dict) else None,
                    citation_count=item.get("citationCount"),
                    venue=item.get("venue") or None,
                    external_ids=external_ids,
                    provider=self.name,
                    provider_id=item.get("paperId"),
                )
            )
        return papers


class CrossrefClient(AcademicProviderClient):
    name = "Crossref"
    endpoint = "https://api.crossref.org/works"

    def __init__(self, *, mailto: str | None, **kwargs: Any):
        super().__init__(**kwargs)
        self.mailto = mailto

    async def search(self, query: str, limit: int) -> list[AcademicPaper]:
        user_agent = "ResearchOS/1.0"
        if self.mailto:
            user_agent += f" (mailto:{self.mailto})"
        headers = {"User-Agent": user_agent}
        response = await self._get(
            self.endpoint,
            params={"query": query, "rows": limit},
            headers=headers,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Crossref returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError("Crossref returned an invalid response shape.")
        message = payload.get("message", {})
        if not isinstance(message, dict) or not isinstance(message.get("items", []), list):
            raise ProviderResponseError("Crossref returned an invalid response shape.")
        papers = []
        for item in message.get("items", []):
            if not isinstance(item, dict):
                continue
            titles = item.get("title") or []
            title = titles[0].strip() if titles and isinstance(titles[0], str) else None
            if not title:
                continue
            authors = tuple(
                " ".join(
                    part for part in (author.get("given"), author.get("family")) if part
                ).strip()
                for author in item.get("author", [])
                if isinstance(author, dict)
            )
            container = item.get("container-title") or []
            venue = container[0] if container else None
            papers.append(
                AcademicPaper(
                    title=title,
                    authors=tuple(author for author in authors if author),
                    abstract=_clean_abstract(item.get("abstract")),
                    publication_date=_date_from_parts(
                        item.get("published-print")
                        or item.get("published-online")
                        or item.get("issued", {}).get("date-parts")
                    ),
                    doi=item.get("DOI"),
                    paper_url=item.get("URL"),
                    venue=venue,
                    publisher=item.get("publisher"),
                    external_ids={"DOI": item["DOI"]} if item.get("DOI") else {},
                    provider=self.name,
                    provider_id=item.get("DOI") or item.get("URL"),
                )
            )
        return papers


class ArxivClient(AcademicProviderClient):
    name = "arXiv"
    endpoint = "https://export.arxiv.org/api/query"
    namespace = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

    async def search(self, query: str, limit: int) -> list[AcademicPaper]:
        response = await self._get(
            self.endpoint,
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": limit,
                "sortBy": "relevance",
            },
        )
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise ProviderResponseError("arXiv returned invalid XML.") from exc
        papers = []
        for entry in root.findall("atom:entry", self.namespace):
            title = entry.findtext("atom:title", default="", namespaces=self.namespace).strip()
            paper_url = entry.findtext("atom:id", default="", namespaces=self.namespace).strip()
            if not title or not paper_url:
                continue
            authors = tuple(
                name.text.strip()
                for name in entry.findall("atom:author/atom:name", self.namespace)
                if name.text and name.text.strip()
            )
            links = entry.findall("atom:link", self.namespace)
            pdf_url = next(
                (
                    link.attrib.get("href")
                    for link in links
                    if link.attrib.get("title") == "pdf"
                ),
                None,
            )
            provider_id = urlparse(paper_url).path.rsplit("/", 1)[-1]
            categories = tuple(
                category.attrib["term"]
                for category in entry.findall("atom:category", self.namespace)
                if category.attrib.get("term")
            )
            papers.append(
                AcademicPaper(
                    title=title,
                    authors=authors,
                    abstract=_clean_abstract(
                        entry.findtext("atom:summary", namespaces=self.namespace)
                    ),
                    publication_date=_date_from_string(
                        entry.findtext("atom:published", namespaces=self.namespace)
                    ),
                    paper_url=paper_url,
                    pdf_url=pdf_url,
                    external_ids={"arXiv": provider_id},
                    provider=self.name,
                    provider_id=provider_id,
                    categories=categories,
                )
            )
        return papers


class AcademicResearchService:
    """Unified academic search with normalization and identifier deduplication."""

    def __init__(
        self,
        *,
        semantic_scholar: SemanticScholarClient | None = None,
        crossref: CrossrefClient | None = None,
        arxiv: ArxivClient | None = None,
        enabled: bool | None = None,
        max_results: int | None = None,
    ):
        timeout = settings.ACADEMIC_TIMEOUT_SECONDS
        self.enabled = settings.ACADEMIC_SEARCH_ENABLED if enabled is None else enabled
        self.max_results = max_results or settings.ACADEMIC_MAX_RESULTS
        self.semantic_scholar = semantic_scholar or SemanticScholarClient(
            api_key=settings.SEMANTIC_SCHOLAR_API_KEY,
            timeout_seconds=timeout,
        )
        self.crossref = crossref or CrossrefClient(
            mailto=settings.CROSSREF_MAILTO,
            timeout_seconds=timeout,
        )
        self.arxiv = arxiv or ArxivClient(timeout_seconds=timeout)

    @staticmethod
    def _deduplicate(papers: list[AcademicPaper]) -> tuple[AcademicPaper, ...]:
        unique: list[AcademicPaper] = []
        seen: set[str] = set()
        for paper in papers:
            keys = paper.dedupe_keys()
            if keys and seen.intersection(keys):
                continue
            seen.update(keys)
            unique.append(paper)
        return tuple(unique)

    @staticmethod
    def _rank(papers: tuple[AcademicPaper, ...], topic: str) -> tuple[AcademicPaper, ...]:
        terms = {term.lower() for term in topic.split() if len(term) > 2}

        def score(paper: AcademicPaper) -> int:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            return sum(term in text for term in terms)

        return tuple(sorted(papers, key=score, reverse=True))

    async def search(self, topic: str) -> AcademicSearchResult:
        if not topic.strip():
            raise ValueError("Academic research topic must not be empty.")
        if not self.enabled:
            return AcademicSearchResult(papers=())
        papers: list[AcademicPaper] = []
        errors: dict[str, str] = {}
        for client in (self.semantic_scholar, self.crossref, self.arxiv):
            try:
                papers.extend(await client.search(topic, self.max_results))
            except ProviderConfigurationError as exc:
                errors[client.name] = str(exc)
            except (ProviderUnavailableError, ProviderRateLimitError, ProviderResponseError) as exc:
                errors[client.name] = str(exc)
        return AcademicSearchResult(
            papers=self._rank(self._deduplicate(papers), topic),
            provider_errors=errors,
        )
