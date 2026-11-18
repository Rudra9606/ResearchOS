import asyncio
from pathlib import Path

import pandas as pd
import pytest

from app.agents.data_analyst import DataAnalystAgent
from app.agents.document_analysis import DocumentAnalysisAgent, DocumentInsight
from app.agents.fact_checker import (
    ClaimExtraction,
    ClaimVerification,
    FactCheckerAgent,
)
from app.agents.planner import PlannerAgent, ResearchPlan
from app.schemas.research_search import AcademicSearchResult
from app.workflows.research_workflow import ResearchWorkflow
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.crud.project import create_project
from app.crud.research_run import create_research_run
from app.crud.agent_execution import get_research_run_executions
from app.schemas.project import ProjectCreate
from app.schemas.research_run import ResearchRunCreate


def run(coroutine):
    return asyncio.run(coroutine)


class StructuredProvider:
    def __init__(self, values):
        self.values = values

    async def generate_structured(self, prompt, response_model, **kwargs):
        value = self.values[response_model]
        return value if isinstance(value, response_model) else response_model.model_validate(value)


def test_planner_generates_structured_plan_and_routes_inputs():
    plan = ResearchPlan(
        objectives=["Compare the approaches"],
        subquestions=["Which approach is more reliable?"],
        strategy="Compare primary and secondary evidence.",
        required_sources=["academic"],
        use_documents=True,
        use_datasets=False,
        steps=["search", "compare"],
    )
    state = run(
        PlannerAgent(StructuredProvider({ResearchPlan: plan})).execute(
            {"research_topic": "Reliable systems", "research_depth": "standard", "document_ids": ["doc"]}
        )
    )
    assert state["research_plan"]["subquestions"] == ["Which approach is more reliable?"]
    assert "document_analysis" in state["agents_required"]


def test_planner_rejects_invalid_request():
    with pytest.raises(ValueError, match="five"):
        run(PlannerAgent(StructuredProvider({})).execute({"research_topic": "x"}))


def test_document_analysis_preserves_chunk_citations():
    class Retrieval:
        def retrieve(self, *args, **kwargs):
            return [{
                "chunk_id": "chunk-1", "document_id": "doc-1",
                "document_filename": "source.txt", "chunk_index": 2,
                "content": "The result is reproducible.", "chunk_metadata": {},
                "combined_score": 0.8,
            }]

        def construct_context_records(self, results):
            return [{"citation": "[1]", "chunk_id": "chunk-1", "document_id": "doc-1",
                     "document_filename": "source.txt", "chunk_index": 2,
                     "content": "The result is reproducible.", "metadata": {}}]

        def construct_context(self, results):
            return "[1] The result is reproducible."

    provider = StructuredProvider({
        DocumentInsight: DocumentInsight(
            summary="The result is reproducible.", key_points=["Reproducible"]
        )
    })
    state = run(
        DocumentAnalysisAgent(
            retrieval=Retrieval(), llm=provider, user_id="user-1"
        ).execute({"research_topic": "reproducibility", "document_ids": ["doc-1"]})
    )
    assert state["document_findings"][0]["relevant_passages"][0]["citation"] == "[1]"


def test_data_analyst_handles_csv_missing_duplicates_and_outliers(tmp_path: Path):
    path = tmp_path / "data.csv"
    pd.DataFrame({
        "value": [1, 2, 2, 100],
        "label": ["a", "b", "b", "c"],
        "group": [None, "x", "x", "y"],
    }).to_csv(path, index=False)
    state = run(
        DataAnalystAgent().execute(
            {"dataset_ids": ["dataset-1"], "dataset_paths": {"dataset-1": str(path)}}
        )
    )
    result = state["data_analysis_results"][0]
    assert result["status"] == "completed"
    assert result["duplicate_rows"] == 1
    assert result["missing_values"]["group"] == 1
    assert result["outliers"]["value"] == 1
    histogram = result["chart_specs"][0]
    assert histogram["column"] == "value"
    assert sum(histogram["counts"]) == 4
    assert len(histogram["bin_edges"]) == len(histogram["counts"]) + 1


def test_data_analyst_handles_xlsx(tmp_path: Path):
    path = tmp_path / "data.xlsx"
    pd.DataFrame({"value": [1, 2, 3]}).to_excel(path, index=False)
    state = run(
        DataAnalystAgent().execute(
            {"dataset_ids": ["dataset-1"], "dataset_paths": {"dataset-1": str(path)}}
        )
    )
    assert state["data_analysis_results"][0]["summary"]["rows"] == 3


def test_fact_checker_requires_and_attributes_evidence():
    provider = StructuredProvider({
        ClaimVerification: ClaimVerification(
            verification_status="supported",
            explanation="The source directly supports the claim.",
            confidence_score=0.9,
            evidence_references=["source-1"],
        )
    })
    state = run(
        FactCheckerAgent(llm=provider).execute({
            "extracted_claims": ["The result is reproducible."],
            "research_sources": [{
                "title": "Study",
                "url": "source-1",
                "summary": "The result is reproducible across repeated trials.",
            }],
        })
    )
    claim = state["verified_claims"][0]
    assert claim["verification_status"] == "supported"
    assert claim["evidence"] == "source-1"


def test_fact_checker_marks_unattributed_model_support_insufficient():
    provider = StructuredProvider({
        ClaimVerification: ClaimVerification(
            verification_status="supported",
            explanation="Unsupported opinion.",
            confidence_score=0.9,
            evidence_references=[],
        )
    })
    state = run(
        FactCheckerAgent(llm=provider).execute({
            "extracted_claims": ["The result is reproducible."],
            "research_sources": [{
                "title": "Study",
                "url": "source-1",
                "summary": "The result is reproducible across repeated trials.",
            }],
        })
    )
    assert state["verified_claims"][0]["verification_status"] == "insufficient_evidence"


def test_workflow_coordinator_and_planner_share_state():
    class EmptyWeb:
        async def search_topic(self, topic, *, queries=None):
            return []

    class EmptyAcademic:
        async def search(self, topic):
            return AcademicSearchResult(papers=())

    plan = ResearchPlan(
        objectives=["Understand the topic"],
        subquestions=["What is known?"],
        strategy="Review evidence.",
        steps=["search"],
    )
    result = run(
        ResearchWorkflow(
            planner_llm=StructuredProvider({ResearchPlan: plan}),
            web_research_service=EmptyWeb(),
            academic_research_service=EmptyAcademic(),
        ).run("A valid research topic")
    )
    assert result["research_request_valid"] is True
    assert result["planner_status"] == "completed"
    assert result["agents_completed"][:2] == ["coordinator", "planner"]


def test_workflow_persists_agent_execution_status(db_session, test_user):
    project = create_project(
        db_session,
        ProjectCreate(title="Agent test", research_topic="Agent persistence"),
        test_user.id,
    )
    run_record = create_research_run(
        db_session,
        ResearchRunCreate(
            project_id=project.id,
            research_topic="Agent persistence",
            research_depth="basic",
        ),
        test_user.id,
    )

    class SuccessfulAgent:
        name = "Test Agent"

        async def execute(self, state):
            state["current_step"] = "test_completed"
            return state

    workflow = ResearchWorkflow(
        db_session=db_session,
        user_id=test_user.id,
        research_run_id=run_record.id,
    )
    state = run(workflow._execute_agent(SuccessfulAgent(), {}, "test_agent"))
    executions = get_research_run_executions(db_session, run_record.id, test_user.id)
    assert state["current_step"] == "test_completed"
    assert len(executions) == 1
    assert executions[0].status == "completed"
    assert executions[0].started_at is not None
    assert executions[0].completed_at is not None


def test_workflow_persists_bounded_dataset_visualization_data(db_session, test_user):
    project = create_project(
        db_session,
        ProjectCreate(title="Chart test", research_topic="Dataset visualization"),
        test_user.id,
    )
    run_record = create_research_run(
        db_session,
        ResearchRunCreate(project_id=project.id, research_topic="Dataset visualization", research_depth="comprehensive"),
        test_user.id,
    )

    class DataAgent:
        name = "Data Analyst"

        async def execute(self, state):
            state["data_analysis_results"] = [{
                "dataset_id": "dataset-1", "status": "completed",
                "summary": {"filename": "sample.csv", "rows": 4, "columns": 1},
                "findings": ["Four observations."],
                "chart_specs": [{"type": "histogram", "column": "value", "counts": [2, 2], "bin_edges": [0.0, 2.0, 4.0]}],
            }]
            return state

    workflow = ResearchWorkflow(db_session=db_session, user_id=test_user.id, research_run_id=run_record.id)
    run(workflow._execute_agent(DataAgent(), {}, "data_analyst"))
    execution = get_research_run_executions(db_session, run_record.id, test_user.id)[0]
    assert execution.output_data["analysis_results"][0]["chart_specs"][0]["counts"] == [2, 2]
    assert execution.output_data["analysis_results"][0]["summary"]["filename"] == "sample.csv"


def test_workflow_checkpoint_preserves_completed_state():
    class EmptyWeb:
        async def search_topic(self, topic, *, queries=None):
            return []

    class EmptyAcademic:
        async def search(self, topic):
            return AcademicSearchResult(papers=())

    plan = ResearchPlan(
        objectives=["Understand the topic"],
        subquestions=["What is known?"],
        strategy="Review evidence.",
        steps=["search"],
    )
    async def execute_with_checkpoint():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as checkpointer:
            workflow = ResearchWorkflow(
                checkpointer=checkpointer,
                planner_llm=StructuredProvider({ResearchPlan: plan}),
                web_research_service=EmptyWeb(),
                academic_research_service=EmptyAcademic(),
            )
            await workflow.run("Checkpoint research topic", thread_id="checkpoint-1")
            return await workflow.graph.aget_state(
                {"configurable": {"thread_id": "checkpoint-1"}}
            )

    snapshot = run(execute_with_checkpoint())
    assert snapshot.values["current_step"] == "report_generation_completed"
    assert snapshot.values["progress"] == 100
