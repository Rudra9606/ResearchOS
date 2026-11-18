"""Evidence-grounded document analysis using the user-scoped RAG service."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.rag.retrieval import RAGRetrievalService


class DocumentInsight(BaseModel):
    summary: str = Field(min_length=1, max_length=8000)
    key_points: list[str] = Field(default_factory=list, max_length=20)
    entities: list[str] = Field(default_factory=list, max_length=50)
    contradictions: list[str] = Field(default_factory=list, max_length=20)


class DocumentAnalysisAgent(BaseAgent):
    """Retrieve, summarize, and cite document evidence without guessing."""

    def __init__(self, retrieval=None, llm=None, *, db=None, user_id=None):
        super().__init__(name="Document Analysis")
        self.retrieval = retrieval or (
            RAGRetrievalService(db) if db is not None else None
        )
        self.llm = llm
        self.user_id = user_id

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        findings = []
        for document_id in state.get("document_ids", []):
            findings.append(await self._analyze_document(document_id, state))
        state["document_findings"] = findings
        state["current_step"] = "document_analysis_completed"
        state["agents_completed"] = state.get("agents_completed", []) + [
            "document_analysis"
        ]
        if any(finding["status"] == "failed" for finding in findings):
            state["document_analysis_status"] = "failed"
        elif findings:
            state["document_analysis_status"] = "completed"
        else:
            state["document_analysis_status"] = "no_results"
        return state

    async def _analyze_document(
        self, document_id: str | UUID, state: dict[str, Any]
    ) -> dict[str, Any]:
        base = {
            "document_id": str(document_id),
            "summary": "",
            "key_points": [],
            "entities": [],
            "contradictions": [],
            "relevant_passages": [],
        }
        if self.retrieval is None or self.user_id is None:
            return {**base, "status": "failed", "error": "Document retrieval is not configured."}
        try:
            results = self.retrieval.retrieve(
                state.get("research_topic", ""),
                user_id=self.user_id,
                document_ids=[document_id],
                top_k=state.get("document_top_k", 8),
            )
        except Exception as exc:
            return {**base, "status": "failed", "error": str(exc)}
        if not results:
            return {**base, "status": "no_results"}

        records = self.retrieval.construct_context_records(results)
        context = self.retrieval.construct_context(results)
        provider = self.llm or self._get_llm()
        try:
            insight = await provider.generate_structured(
                (
                    "Analyze only the supplied document evidence. Summarize it, "
                    "list key points and entities, and mention contradictions only "
                    "when they are visible in the evidence.\n\n"
                    f"Research question: {state.get('research_topic', '')}\n"
                    f"Evidence:\n{context}"
                ),
                DocumentInsight,
            )
        except Exception as exc:
            return {**base, "status": "failed", "error": str(exc)}
        return {
            **base,
            **insight.model_dump(),
            "relevant_passages": records,
            "status": "completed",
        }
