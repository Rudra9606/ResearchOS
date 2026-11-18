"""Web Research Agent backed by the Tavily research service."""

from typing import Any, Dict

from app.agents.base import BaseAgent
from app.providers.exceptions import ProviderError
from app.services.web_research_service import WebResearchService


class WebResearchAgent(BaseAgent):
    """Search the web and add only normalized provider results to workflow state."""

    def __init__(self, service: WebResearchService | None = None):
        super().__init__(name="Web Research")
        self.service = service or WebResearchService()

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        topic = state.get("research_topic", "")
        queries = state.get("web_search_queries")
        try:
            results = await self.service.search_topic(topic, queries=queries)
        except ProviderError as exc:
            state.setdefault("research_errors", {})["Tavily"] = str(exc)
            state["web_search_status"] = "failed"
            state["web_search_result_count"] = 0
            state["current_step"] = "web_research_failed"
            return state
        sources = state.get("research_sources", [])
        sources.extend(result.as_dict() for result in results)
        state["research_sources"] = sources
        state["web_search_status"] = "completed" if results else "no_results"
        state["web_search_result_count"] = len(results)
        state["current_step"] = "web_research_completed"
        state["agents_completed"] = state.get("agents_completed", []) + ["web_research"]
        return state
