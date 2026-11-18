"""LLM-driven research planning."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent


ResearchDepth = Literal["basic", "standard", "comprehensive"]


class ResearchPlan(BaseModel):
    """Structured plan returned by the configured language model."""

    objectives: list[str] = Field(min_length=1, max_length=10)
    subquestions: list[str] = Field(min_length=1, max_length=20)
    strategy: str = Field(min_length=1, max_length=4000)
    required_sources: list[str] = Field(default_factory=list, max_length=10)
    use_documents: bool = False
    use_datasets: bool = False
    steps: list[str] = Field(min_length=1, max_length=20)


class PlannerAgent(BaseAgent):
    """Turn a validated research request into an LLM-generated plan."""

    def __init__(self, llm=None):
        super().__init__(name="Planner")
        self.llm = llm

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        topic = str(state.get("research_topic", "")).strip()
        depth = state.get("research_depth", "standard")
        if len(topic) < 5:
            raise ValueError("Research topic must contain at least five characters.")
        if depth not in {"basic", "standard", "comprehensive"}:
            raise ValueError("Research depth is invalid.")

        provider = self.llm or self._get_llm()
        prompt = (
            "Create a research plan for the topic below. Do not answer the "
            "research question and do not invent evidence. Identify objectives, "
            "subquestions, source types, and workflow steps. Use the requested "
            f"depth: {depth}.\n\nTopic: {topic}\n"
            f"Documents supplied: {bool(state.get('document_ids'))}\n"
            f"Datasets supplied: {bool(state.get('dataset_ids'))}"
        )
        plan = await provider.generate_structured(
            prompt,
            ResearchPlan,
            system_prompt=(
                "You are a research planning specialist. Return only a valid "
                "structured plan grounded in the request."
            ),
        )
        state["research_plan"] = plan.model_dump()
        state["research_questions"] = plan.subquestions
        state["agents_required"] = self._required_agents(state, plan)
        state["planner_status"] = "completed"
        state["current_step"] = "planner_completed"
        state["progress"] = max(state.get("progress", 0), 15)
        state["agents_completed"] = state.get("agents_completed", []) + ["planner"]
        return state

    @staticmethod
    def _required_agents(state: dict[str, Any], plan: ResearchPlan) -> list[str]:
        required = ["web_research", "academic_research"]
        if state.get("document_ids") and plan.use_documents:
            required.append("document_analysis")
        if state.get("dataset_ids") and plan.use_datasets:
            required.append("data_analyst")
        required.extend(["fact_checker", "report_writer"])
        return required
