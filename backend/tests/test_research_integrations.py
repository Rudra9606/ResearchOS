import asyncio

import httpx
import pytest

from app.agents.academic import AcademicResearchAgent
from app.agents.web_research import WebResearchAgent
from app.providers.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from app.schemas.research_search import AcademicPaper, AcademicSearchResult
from app.services.academic_research_service import (
    AcademicResearchService,
    ArxivClient,
    CrossrefClient,
    SemanticScholarClient,
)
from app.services.web_research_service import WebResearchService
from app.workflows.research_workflow import ResearchWorkflow


def run(coroutine):
    return asyncio.run(coroutine)


def test_tavily_requires_api_key():
    service = WebResearchService(api_key="")
    with pytest.raises(ProviderConfigurationError, match="TAVILY_API_KEY"):
        run(service.search("quantum computing"))


def test_tavily_normalizes_and_deduplicates_results():
    async def handler(request):
        body = await request.aread()
        assert b'"search_depth":"advanced"' in body
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "First",
                        "url": "https://example.com/article#section",
                        "content": "Evidence",
                        "score": 0.9,
                    },
                    {
                        "title": "Duplicate",
                        "url": "https://example.com/article",
                        "content": "Duplicate evidence",
                    },
                    {"url": "https://example.com/missing-title"},
                ]
            },
        )

    service = WebResearchService(
        api_key="test-key",
        search_depth="advanced",
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )
    results = run(service.search("quantum computing"))
    assert len(results) == 1
    assert results[0].source_domain == "example.com"
    assert results[0].search_query == "quantum computing"


def test_tavily_topic_search_deduplicates_across_queries():
    calls = []

    async def handler(request):
        calls.append(request.url)
        return httpx.Response(
            200,
            json={
                "results": [{
                    "title": "Source",
                    "url": "https://example.com/source",
                    "content": "Evidence",
                }]
            },
        )

    service = WebResearchService(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )
    results = run(service.search_topic("topic", queries=["one", "two"]))
    assert len(calls) == 2
    assert len(results) == 1


def test_tavily_rate_limit_and_timeout_are_explicit():
    async def rate_limited(request):
        return httpx.Response(429, json={"error": "rate limited"})

    service = WebResearchService(
        api_key="test-key",
        transport=httpx.MockTransport(rate_limited),
        max_retries=0,
    )
    with pytest.raises(ProviderRateLimitError):
        run(service.search("topic"))

    async def timed_out(request):
        raise httpx.ReadTimeout("timed out", request=request)

    service = WebResearchService(
        api_key="test-key",
        transport=httpx.MockTransport(timed_out),
        max_retries=0,
    )
    with pytest.raises(ProviderUnavailableError):
        run(service.search("topic"))


def test_semantic_scholar_normalizes_missing_metadata():
    async def handler(request):
        return httpx.Response(
            200,
            json={
                "data": [{
                    "paperId": "paper-1",
                    "title": "Paper",
                    "authors": [{"name": "Author"}],
                    "externalIds": {"DOI": "10.1/test"},
                    "abstract": None,
                }]
            },
        )

    client = SemanticScholarClient(
        api_key=None,
        timeout_seconds=5,
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )
    papers = run(client.search("topic", 5))
    assert papers[0].title == "Paper"
    assert papers[0].authors == ("Author",)
    assert papers[0].abstract is None
    assert papers[0].doi == "10.1/test"


def test_crossref_normalizes_missing_doi_and_authors():
    async def handler(request):
        return httpx.Response(
            200,
            json={"message": {"items": [{
                "title": ["Crossref paper"],
                "publisher": "Publisher",
                "URL": "https://doi.org/example",
            }]}},
        )

    client = CrossrefClient(
        mailto="research@example.com",
        timeout_seconds=5,
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )
    papers = run(client.search("topic", 5))
    assert papers[0].title == "Crossref paper"
    assert papers[0].doi is None
    assert papers[0].authors == ()


def test_arxiv_parses_xml_and_rejects_invalid_xml():
    xml = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/1234.5678</id>
        <title>Arxiv paper</title>
        <summary>Abstract</summary>
        <published>2024-01-02T00:00:00Z</published>
        <author><name>Researcher</name></author>
        <link title="pdf" href="http://arxiv.org/pdf/1234.5678"/>
        <category term="cs.AI"/>
      </entry>
    </feed>"""

    async def valid_handler(request):
        return httpx.Response(200, text=xml)

    client = ArxivClient(
        timeout_seconds=5,
        max_retries=0,
        transport=httpx.MockTransport(valid_handler),
    )
    papers = run(client.search("topic", 5))
    assert papers[0].provider_id == "1234.5678"
    assert papers[0].pdf_url.endswith("1234.5678")
    assert papers[0].categories == ("cs.AI",)

    async def invalid_handler(request):
        return httpx.Response(200, text="<invalid")

    client = ArxivClient(
        timeout_seconds=5,
        max_retries=0,
        transport=httpx.MockTransport(invalid_handler),
    )
    with pytest.raises(ProviderResponseError, match="invalid XML"):
        run(client.search("topic", 5))


def test_unified_academic_search_deduplicates_papers():
    class FakeClient:
        def __init__(self, name, paper):
            self.name = name
            self.paper = paper

        async def search(self, query, limit):
            return [self.paper]

    duplicate_one = AcademicPaper(
        title="Same paper",
        doi="10.1/same",
        provider="Semantic Scholar",
        provider_id="one",
    )
    duplicate_two = AcademicPaper(
        title="Same paper",
        doi="10.1/same",
        provider="Crossref",
        provider_id="two",
    )
    service = AcademicResearchService(
        semantic_scholar=FakeClient("Semantic Scholar", duplicate_one),
        crossref=FakeClient("Crossref", duplicate_two),
        arxiv=FakeClient("arXiv", AcademicPaper(title="Other", provider="arXiv")),
    )
    result = run(service.search("topic"))
    assert [paper.title for paper in result.papers] == ["Same paper", "Other"]


def test_agents_report_explicit_no_results():
    class EmptyWebService:
        async def search_topic(self, topic, *, queries=None):
            return []

    class EmptyAcademicService:
        async def search(self, topic):
            return AcademicSearchResult(papers=())

    state = {"research_topic": "topic", "research_sources": []}
    state = run(WebResearchAgent(EmptyWebService()).execute(state))
    state = run(AcademicResearchAgent(EmptyAcademicService()).execute(state))
    assert state["web_search_status"] == "no_results"
    assert state["academic_search_status"] == "no_results"
    assert state["research_sources"] == []


def test_langgraph_uses_real_agent_services_without_fabricated_sources():
    class EmptyWebService:
        async def search_topic(self, topic, *, queries=None):
            return []

    class EmptyAcademicService:
        async def search(self, topic):
            return AcademicSearchResult(papers=())

    workflow = ResearchWorkflow(
        web_research_service=EmptyWebService(),
        academic_research_service=EmptyAcademicService(),
    )
    result = run(workflow.run("topic"))
    assert result["web_search_status"] == "no_results"
    assert result["academic_search_status"] == "no_results"
    assert result["research_sources"] == []
    assert result["progress"] == 100
