"""LangGraph Research Workflow - multi-agent orchestration for research execution."""

from typing import Any, Dict, List, Optional
from uuid import UUID
from typing import Callable

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agents.planner import PlannerAgent
from app.agents.coordinator import ResearchCoordinatorAgent
from app.agents.web_research import WebResearchAgent
from app.agents.academic import AcademicResearchAgent
from app.agents.document_analysis import DocumentAnalysisAgent
from app.agents.data_analyst import DataAnalystAgent
from app.agents.fact_checker import FactCheckerAgent
from app.agents.report_writer import ReportWriterAgent
from app.crud.agent_execution import (
    create_agent_execution,
    update_agent_execution,
)


class ResearchWorkflow:
    """LangGraph-based multi-agent research workflow."""

    def __init__(
        self,
        db_session=None,
        checkpointer=None,
        user_id=None,
        research_run_id=None,
        web_research_service=None,
        academic_research_service=None,
        planner_llm=None,
        document_retrieval=None,
        document_llm=None,
        fact_checker_llm=None,
        fact_checker_retrieval=None,
        report_llm=None,
        max_agent_retries: int = 0,
        cancel_checker: Callable[[], bool] | None = None,
    ):
        self.db_session = db_session
        self.checkpointer = checkpointer
        self.user_id = user_id
        self.research_run_id = research_run_id
        self.max_agent_retries = max_agent_retries
        self.cancel_checker = cancel_checker

        # Initialize agents
        self.coordinator = ResearchCoordinatorAgent()
        self.planner = PlannerAgent(llm=planner_llm)
        self.web_research = WebResearchAgent(web_research_service)
        self.academic = AcademicResearchAgent(academic_research_service)
        self.document_analysis = DocumentAnalysisAgent(
            retrieval=document_retrieval,
            llm=document_llm,
            db=db_session,
            user_id=user_id,
        )
        self.data_analyst = DataAnalystAgent(db=db_session, user_id=user_id)
        self.fact_checker = FactCheckerAgent(
            llm=fact_checker_llm,
            retrieval=fact_checker_retrieval,
            user_id=user_id,
        )
        self.report_writer = ReportWriterAgent(llm=report_llm)

        # Build the graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph."""
        workflow = StateGraph(Dict[str, Any])

        # Add nodes
        workflow.add_node("coordinator", self._coordinator_node)
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("web_research", self._web_research_node)
        workflow.add_node("academic_research", self._academic_research_node)
        workflow.add_node("document_analysis", self._document_analysis_node)
        workflow.add_node("data_analyst", self._data_analyst_node)
        workflow.add_node("fact_checker", self._fact_checker_node)
        workflow.add_node("report_writer", self._report_writer_node)

        # Set entry point
        workflow.set_entry_point("coordinator")

        # Add edges
        workflow.add_conditional_edges(
            "coordinator",
            self._select_after_coordinator,
            {"planner": "planner", END: END},
        )
        workflow.add_conditional_edges(
            "planner",
            self._select_after_planner,
            {"web_research": "web_research", END: END},
        )
        workflow.add_conditional_edges("academic_research", self._select_post_academic_node, {
            "document_analysis": "document_analysis", "data_analyst": "data_analyst",
            "fact_checker": "fact_checker", END: END,
        })
        workflow.add_conditional_edges(
            "document_analysis",
            self._select_post_document_node,
            {"data_analyst": "data_analyst", "fact_checker": "fact_checker", END: END},
        )
        workflow.add_conditional_edges("web_research", self._select_after_web, {"academic_research": "academic_research", END: END})
        workflow.add_conditional_edges("data_analyst", self._select_after_data, {"fact_checker": "fact_checker", END: END})
        workflow.add_conditional_edges("fact_checker", self._select_after_fact_check, {"report_writer": "report_writer", END: END})
        workflow.add_edge("report_writer", END)

        # Compile with checkpointer if provided
        if self.checkpointer:
            return workflow.compile(checkpointer=self.checkpointer)
        return workflow.compile()

    @staticmethod
    def _select_after_coordinator(state: Dict[str, Any]) -> str:
        return "planner" if state.get("research_request_valid") and not state.get("cancelled") else END

    @staticmethod
    def _select_after_planner(state: Dict[str, Any]) -> str:
        # A failed plan is explicit; raw validated request state may still be
        # searched, but no synthetic plan is inserted into the result.
        return END if state.get("cancelled") else "web_research"

    @staticmethod
    def _select_after_web(state: Dict[str, Any]) -> str:
        return END if state.get("cancelled") else "academic_research"

    @staticmethod
    def _select_after_data(state: Dict[str, Any]) -> str:
        return END if state.get("cancelled") else "fact_checker"

    @staticmethod
    def _select_after_fact_check(state: Dict[str, Any]) -> str:
        return END if state.get("cancelled") else "report_writer"

    @staticmethod
    def _select_post_academic_node(state: Dict[str, Any]) -> str:
        if state.get("cancelled"):
            return END
        if state.get("document_ids"):
            return "document_analysis"
        if state.get("dataset_ids") and state.get("research_depth") == "comprehensive":
            return "data_analyst"
        return "fact_checker"

    @staticmethod
    def _select_post_document_node(state: Dict[str, Any]) -> str:
        if state.get("cancelled"):
            return END
        if state.get("dataset_ids") and state.get("research_depth") == "comprehensive":
            return "data_analyst"
        return "fact_checker"

    async def _planner_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return await self._execute_agent(self.planner, state, "planner")

    async def _coordinator_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return await self._execute_agent(self.coordinator, state, "coordinator")

    async def _web_research_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return await self._execute_agent(self.web_research, state, "web_research")

    async def _academic_research_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return await self._execute_agent(self.academic, state, "academic_research")

    async def _document_analysis_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return await self._execute_agent(self.document_analysis, state, "document_analysis")

    async def _data_analyst_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return await self._execute_agent(self.data_analyst, state, "data_analyst")

    async def _fact_checker_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return await self._execute_agent(self.fact_checker, state, "fact_checker")

    async def _report_writer_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return await self._execute_agent(self.report_writer, state, "report_writer")

    async def _execute_agent(
        self,
        agent,
        state: Dict[str, Any],
        node_name: str,
    ) -> Dict[str, Any]:
        """Run a node and persist a bounded execution record when configured."""
        if self.cancel_checker and self.cancel_checker():
            return {**state, "cancelled": True, "current_step": "cancelled"}
        execution = None
        if self.db_session is not None and self.user_id and self.research_run_id:
            execution = create_agent_execution(
                self.db_session,
                self.research_run_id,
                self.user_id,
                agent.name,
                {
                    "research_topic": state.get("research_topic", ""),
                    "research_depth": state.get("research_depth"),
                    "node": node_name,
                },
            )
            update_agent_execution(
                self.db_session, execution.id, self.user_id, "running"
            )
        attempt = 0
        while True:
            try:
                result = await agent.execute(state)
                if self.cancel_checker and self.cancel_checker():
                    result = {**result, "cancelled": True, "current_step": "cancelled"}
                break
            except Exception as exc:
                if attempt >= self.max_agent_retries:
                    if execution is not None:
                        update_agent_execution(
                            self.db_session,
                            execution.id,
                            self.user_id,
                            "failed",
                            error_message=str(exc),
                        )
                    state.setdefault("agent_failures", {})[node_name] = str(exc)
                    state.setdefault("research_errors", {})[agent.name] = str(exc)
                    state["current_step"] = f"{node_name}_failed"
                    state[
                        "planner_status"
                        if node_name == "planner"
                        else f"{node_name}_status"
                    ] = "failed"
                    result = state
                    break
                attempt += 1
                state.setdefault("agent_retries", {})[node_name] = attempt
                if execution is not None:
                    update_agent_execution(
                        self.db_session,
                        execution.id,
                        self.user_id,
                        "running",
                        error_message=f"Retrying attempt {attempt}.",
                    )
        if execution is not None:
            status_key = {
                "web_research": "web_search_status",
                "academic_research": "academic_search_status",
            }.get(node_name)
            failed = bool(result.get("agent_failures", {}).get(node_name)) or (
                status_key is not None and result.get(status_key) == "failed"
            )
            update_agent_execution(
                self.db_session,
                execution.id,
                self.user_id,
                "failed" if failed else "completed",
                output_data={
                    "node": node_name,
                    "current_step": result.get("current_step"),
                    "status": result.get(status_key) if status_key else (
                        "failed" if failed else "completed"
                    ),
                    "result_count": result.get(
                        {
                            "web_research": "web_search_result_count",
                            "academic_research": "academic_search_result_count",
                        }.get(node_name, ""),
                        0,
                    ),
                    **({
                        "analysis_results": [
                            {
                                "dataset_id": item.get("dataset_id"),
                                "status": item.get("status"),
                                "summary": item.get("summary", {}),
                                "findings": item.get("findings", [])[:10],
                                "chart_specs": item.get("chart_specs", [])[:10],
                            }
                            for item in result.get("data_analysis_results", [])[:20]
                        ]
                    } if node_name == "data_analyst" else {}),
                },
                error_message=(
                    "; ".join(
                        f"{provider}: {message}"
                        for provider, message in result.get(
                            "research_errors", {}
                        ).items()
                    )
                    if result.get("research_errors")
                    else None
                ),
            )
            progress = {
                "coordinator": 5,
                "planner": 15,
                "web_research": 30,
                "academic_research": 45,
                "document_analysis": 60,
                "data_analyst": 75,
                "fact_checker": 90,
            }.get(node_name)
            if progress is not None:
                from app.crud.research_run import update_research_run_progress

                update_research_run_progress(
                    self.db_session,
                    self.research_run_id,
                    self.user_id,
                    progress,
                    result.get("current_step"),
                )
        return result

    async def run(
        self,
        research_topic: str,
        research_depth: str = "standard",
        thread_id: str | None = None,
        document_ids: list[str] | None = None,
        dataset_ids: list[str] | None = None,
    ) -> Dict[str, Any]:
        """Run the research workflow."""
        initial_state = {
            "research_topic": research_topic,
            "research_depth": research_depth,
            "document_ids": document_ids or [],
            "dataset_ids": dataset_ids or [],
            "research_sources": [],
            "verified_claims": [],
            "document_findings": [],
            "data_analysis_results": [],
            "extracted_claims": [],
            "progress": 0,
            "current_step": "starting",
            "agents_completed": [],
            "cancelled": False,
        }

        config = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}

        result = await self.graph.ainvoke(initial_state, config=config)
        return result
