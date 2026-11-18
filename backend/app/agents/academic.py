"""Academic Research Agent backed by unified academic provider services."""

from typing import Any, Dict

from app.agents.base import BaseAgent
from app.services.academic_research_service import AcademicResearchService


class AcademicResearchAgent(BaseAgent):
    """Search academic providers and add normalized papers to workflow state."""

    def __init__(self, service: AcademicResearchService | None = None):
        super().__init__(name="Academic Research")
        self.service = service or AcademicResearchService()

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        topic = state.get("research_topic", "")
        result = await self.service.search(topic)
        sources = state.get("research_sources", [])
        sources.extend(paper.as_dict() for paper in result.papers)
        state["research_sources"] = sources
        if result.has_results:
            state["academic_search_status"] = "completed"
        elif result.provider_errors:
            state["academic_search_status"] = "failed"
        else:
            state["academic_search_status"] = "no_results"
        state["academic_search_result_count"] = len(result.papers)
        if result.provider_errors:
            errors = state.setdefault("research_errors", {})
            errors.update(result.provider_errors)
        state["current_step"] = "academic_research_completed"
        state["agents_completed"] = state.get("agents_completed", []) + ["academic_research"]
        return state
