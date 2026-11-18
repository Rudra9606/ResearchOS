"""Research coordinator for request validation and shared workflow state."""

from typing import Any

from app.agents.base import BaseAgent


class ResearchCoordinatorAgent(BaseAgent):
    """Validate a request and initialize bounded, shared research state."""

    def __init__(self):
        super().__init__(name="Research Coordinator")

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        topic = str(state.get("research_topic", "")).strip()
        depth = state.get("research_depth", "standard")
        if len(topic) < 5:
            raise ValueError("Research topic must contain at least five characters.")
        if depth not in {"basic", "standard", "comprehensive"}:
            raise ValueError("Research depth is invalid.")
        state["research_topic"] = topic
        state["research_depth"] = depth
        state["research_request_valid"] = True
        state["current_step"] = "coordinator_completed"
        state["progress"] = max(state.get("progress", 0), 5)
        state["agents_completed"] = state.get("agents_completed", []) + ["coordinator"]
        return state
