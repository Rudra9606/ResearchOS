"""Structured, citation-preserving research report generation."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.schemas.report_document import ReportSection, StructuredResearchReport
from app.services.citation_service import CitationManager
from app.services.report_service import render_report_markdown


class ReportWriterAgent(BaseAgent):
    """Generate an evidence-bounded structured report."""

    def __init__(self, llm=None):
        super().__init__(name="Report Writer")
        self.llm = llm

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        sources = state.get("research_sources", [])
        citations = CitationManager.from_sources(sources)
        try:
            if self.llm is None:
                provider = self._get_llm()
            else:
                provider = self.llm
            report = await provider.generate_structured(
                self._prompt(state, citations),
                StructuredResearchReport,
                system_prompt=(
                    "Write only an evidence-grounded research report. Do not "
                    "invent facts, references, URLs, or unavailable sections."
                ),
            )
            # References are authoritative only when they came from workflow
            # sources; model-supplied URLs and metadata are never accepted.
            report.references = citations
            report = CitationManager.validate_section_references(report)
        except Exception as exc:
            if self.llm is not None:
                state["report_generation_status"] = "failed"
                state.setdefault("research_errors", {})["Report Writer"] = str(exc)
                state["current_step"] = "report_generation_failed"
                return state
            # The fallback is a transparent evidence inventory, not fabricated
            # research, and keeps workflows usable when no LLM is configured.
            report = self._evidence_only_report(state, citations)

        state["structured_report"] = report.model_dump(mode="json")
        state["report_content"] = render_report_markdown(report)
        state["report_generation_status"] = "completed"
        state["current_step"] = "report_generation_completed"
        state["agents_completed"] = state.get("agents_completed", []) + ["report_writer"]
        state["progress"] = 100
        return state

    @staticmethod
    def _prompt(state: dict[str, Any], citations) -> str:
        evidence = {
            "topic": state.get("research_topic"),
            "plan": state.get("research_plan", {}),
            "sources": state.get("research_sources", []),
            "documents": state.get("document_findings", []),
            "datasets": state.get("data_analysis_results", []),
            "claims": state.get("verified_claims", []),
            "citation_ids": [citation.citation_id for citation in citations],
        }
        return (
            "Create all requested report sections. For sections without evidence, "
            "set available=false and explain that evidence is unavailable. Use "
            "only citation IDs supplied in the evidence.\n\n"
            + json.dumps(evidence, ensure_ascii=True, default=str)[:50000]
        )

    @classmethod
    def _evidence_only_report(cls, state, citations) -> StructuredResearchReport:
        sources = state.get("research_sources", [])
        plan = state.get("research_plan", {})
        source_text = "\n".join(
            f"{citation.citation_id}: {citation.title}"
            for citation in citations
        )
        return StructuredResearchReport(
            title=f"Research Report: {state.get('research_topic', 'Untitled')}",
            executive_summary=cls._section(
                "Executive Summary",
                f"Evidence inventory for {state.get('research_topic', '')}.",
                citations,
            ),
            research_objectives=cls._section(
                "Research Objectives",
                "\n".join(plan.get("objectives", [])),
                citations,
                available=bool(plan.get("objectives")),
            ),
            research_questions=cls._section(
                "Research Questions",
                "\n".join(plan.get("subquestions", [])),
                citations,
                available=bool(plan.get("subquestions")),
            ),
            methodology=cls._section(
                "Research Methodology",
                "Sources and findings are reported as returned by the configured research workflow.",
                citations,
            ),
            web_research_findings=cls._section(
                "Web Research Findings",
                source_text,
                citations,
                available=any(item.get("source_type") == "web" for item in sources),
            ),
            academic_research_findings=cls._section(
                "Academic Research Findings",
                source_text,
                citations,
                available=any(item.get("source_type") == "academic" for item in sources),
            ),
            document_analysis_findings=cls._section_from_data(
                "Document Analysis Findings", state.get("document_findings", []), citations
            ),
            dataset_analysis_findings=cls._section_from_data(
                "Dataset Analysis Findings", state.get("data_analysis_results", []), citations
            ),
            verified_claims=cls._section_from_data(
                "Verified Claims", state.get("verified_claims", []), citations
            ),
            limitations=cls._section(
                "Limitations",
                "This evidence-only report does not infer conclusions beyond the supplied findings.",
                citations,
            ),
            conclusion=cls._section(
                "Conclusion",
                "Insufficient evidence for an independently supported conclusion."
                if not sources
                else "See the cited findings; no unsupported conclusion was generated.",
                citations,
            ),
            references=citations,
        )

    @staticmethod
    def _section(title, content, citations, available=True):
        return ReportSection(
            title=title,
            available=available,
            content=content or "Evidence unavailable.",
            evidence_ids=[citation.citation_id for citation in citations] if available else [],
        )

    @classmethod
    def _section_from_data(cls, title, data, citations):
        return cls._section(
            title,
            json.dumps(data, ensure_ascii=True, default=str) if data else "Evidence unavailable.",
            citations,
            available=bool(data),
        )
