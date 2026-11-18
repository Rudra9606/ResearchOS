"""Tavily-backed web research service."""

import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urldefrag

import httpx

from app.core.config import settings
from app.providers.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from app.providers.http import raise_for_provider_response, request_error
from app.schemas.research_search import WebSearchResult


class WebResearchService:
    """Search and normalize web sources through the Tavily API."""

    endpoint = "https://api.tavily.com/search"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        max_results: int | None = None,
        search_depth: str | None = None,
        min_relevance_score: float | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.TAVILY_API_KEY
        self.max_results = max_results or settings.TAVILY_MAX_RESULTS
        self.search_depth = search_depth or settings.TAVILY_SEARCH_DEPTH
        self.min_relevance_score = (
            settings.TAVILY_MIN_RELEVANCE_SCORE
            if min_relevance_score is None
            else min_relevance_score
        )
        self.timeout_seconds = timeout_seconds or settings.TAVILY_TIMEOUT_SECONDS
        self.max_retries = (
            settings.TAVILY_MAX_RETRIES if max_retries is None else max_retries
        )
        self._transport = transport
        if self.search_depth not in {"basic", "advanced"}:
            raise ProviderConfigurationError(
                "TAVILY_SEARCH_DEPTH must be 'basic' or 'advanced'."
            )
        if self.max_results < 1:
            raise ProviderConfigurationError("TAVILY_MAX_RESULTS must be positive.")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self._transport,
        )

    async def _search_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            try:
                async with self._client() as client:
                    response = await client.post(self.endpoint, json=payload)
                raise_for_provider_response(response, "Tavily")
                try:
                    result = response.json()
                except ValueError as exc:
                    raise ProviderResponseError("Tavily returned invalid JSON.") from exc
                if not isinstance(result, dict):
                    raise ProviderResponseError("Tavily returned an invalid response shape.")
                return result
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if attempt >= self.max_retries:
                    raise request_error("Tavily", exc) from exc
                await asyncio.sleep(min(2**attempt, 8))
            except (ProviderRateLimitError, ProviderUnavailableError):
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(min(2**attempt, 8))
        raise ProviderUnavailableError("Tavily request could not be completed.")

    @staticmethod
    def _parse_date(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _canonical_url(url: str) -> str:
        clean_url, _ = urldefrag(url.strip())
        return clean_url.rstrip("/").lower()

    def _normalize_result(
        self,
        item: Any,
        *,
        query: str,
    ) -> WebSearchResult | None:
        if not isinstance(item, dict):
            return None
        title = item.get("title")
        url = item.get("url")
        if not isinstance(title, str) or not title.strip():
            return None
        if not isinstance(url, str) or not url.strip():
            return None
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            return None
        content = item.get("content") or item.get("snippet") or ""
        if not isinstance(content, str):
            content = str(content)
        score = item.get("score")
        if not isinstance(score, (int, float)):
            score = None
        return WebSearchResult(
            title=title.strip(),
            url=url.strip(),
            content=content.strip(),
            source_domain=parsed_url.netloc.lower(),
            published_date=self._parse_date(item.get("published_date")),
            relevance_score=float(score) if score is not None else None,
            search_query=query,
        )

    async def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
        include_domains: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[WebSearchResult]:
        """Execute one Tavily search and normalize valid results."""
        if not self.api_key or not self.api_key.strip():
            raise ProviderConfigurationError(
                "TAVILY_API_KEY is required for web research."
            )
        if not query.strip():
            raise ValueError("Web search query must not be empty.")
        payload: dict[str, Any] = {
            "api_key": self.api_key,
            "query": query.strip(),
            "search_depth": self.search_depth,
            "max_results": max_results or self.max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        if include_domains:
            payload["include_domains"] = include_domains
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        response = await self._search_request(payload)
        raw_results = response.get("results", [])
        if not isinstance(raw_results, list):
            raise ProviderResponseError("Tavily results field must be a list.")
        normalized = []
        seen = set()
        for item in raw_results:
            result = self._normalize_result(item, query=query)
            if result is None:
                continue
            if (
                self.min_relevance_score is not None
                and (
                    result.relevance_score is None
                    or result.relevance_score < self.min_relevance_score
                )
            ):
                continue
            key = self._canonical_url(result.url)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(result)
        return normalized

    async def search_topic(
        self,
        topic: str,
        *,
        queries: list[str] | None = None,
        include_domains: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[WebSearchResult]:
        """Run multiple topic queries and deduplicate URLs across all results."""
        search_queries = queries or [topic]
        results: list[WebSearchResult] = []
        seen = set()
        for query in search_queries:
            for result in await self.search(
                query,
                include_domains=include_domains,
                start_date=start_date,
                end_date=end_date,
            ):
                key = self._canonical_url(result.url)
                if key not in seen:
                    seen.add(key)
                    results.append(result)
        return results
