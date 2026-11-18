import asyncio
from pathlib import Path

import pytest

from app.agents.report_writer import ReportWriterAgent
from app.schemas.report_document import (
    ReportCitation,
    ReportSection,
    StructuredResearchReport,
)
from app.services.citation_service import CitationError, CitationManager
from app.services.report_service import (
    generate_docx_report,
    generate_html_report,
    generate_pdf_report,
)


def section(title, content="Evidence.", available=True, evidence_ids=None):
    return ReportSection(
        title=title,
        content=content,
        available=available,
        evidence_ids=evidence_ids or [],
    )


def sample_report():
    citation = ReportCitation(
        citation_id="source-1",
        title="Evidence source",
        url="https://example.com/source",
        authors=["A. Author"],
        publisher_or_venue="Example Journal",
        publication_date="2024-01-01",
        source_type="academic",
        doi="10.1000/example",
    )
    return StructuredResearchReport(
        title="A professional report",
        executive_summary=section("Executive Summary", evidence_ids=["source-1"]),
        research_objectives=section("Research Objectives", evidence_ids=["source-1"]),
        research_questions=section("Research Questions", evidence_ids=["source-1"]),
        methodology=section("Methodology", evidence_ids=["source-1"]),
        web_research_findings=section("Web", available=False),
        academic_research_findings=section("Academic", evidence_ids=["source-1"]),
        document_analysis_findings=section("Documents", available=False),
        dataset_analysis_findings=section("Datasets", available=False),
        verified_claims=section("Claims", evidence_ids=["source-1"]),
        limitations=section("Limitations", evidence_ids=["source-1"]),
        conclusion=section("Conclusion", evidence_ids=["source-1"]),
        references=[citation],
    )


def test_citation_manager_deduplicates_and_rejects_invalid_urls():
    sources = [
        {"title": "Source", "url": "https://example.com/a", "doi": "10.1/test"},
        {"title": "Duplicate", "url": "https://example.com/b", "doi": "10.1/test"},
    ]
    citations = CitationManager.from_sources(sources)
    assert len(citations) == 1
    assert "Example Journal" not in CitationManager.apa(citations[0])

    with pytest.raises(CitationError):
        CitationManager.from_sources([{"title": "Bad", "url": "javascript:alert(1)"}])


def test_report_exports_produce_real_files(tmp_path: Path):
    report = sample_report()
    pdf = tmp_path / "report.pdf"
    docx = tmp_path / "report.docx"
    html = tmp_path / "report.html"
    generate_pdf_report(report, report.title, str(pdf))
    generate_docx_report(report, report.title, str(docx))
    generate_html_report(
        report.model_copy(update={"title": "<unsafe>"}),
        "<unsafe>",
        str(html),
    )
    assert pdf.read_bytes().startswith(b"%PDF")
    assert docx.read_bytes().startswith(b"PK")
    html_content = html.read_text(encoding="utf-8")
    assert "&lt;unsafe&gt;" in html_content
    assert "https://example.com/source" in html_content


def test_report_writer_fallback_marks_unavailable_sections():
    state = asyncio.run(
        ReportWriterAgent().execute(
            {"research_topic": "Evidence topic", "research_sources": []}
        )
    )
    assert state["report_generation_status"] == "completed"
    assert state["structured_report"]["web_research_findings"]["available"] is False
    assert "Insufficient evidence" in state["report_content"]


def test_report_writer_replaces_untrusted_model_references():
    class Provider:
        async def generate_structured(self, prompt, response_model, **kwargs):
            report = sample_report()
            report.references = [
                ReportCitation(
                    citation_id="invented",
                    title="Invented source",
                    url="https://attacker.example/source",
                )
            ]
            return report

    state = asyncio.run(
        ReportWriterAgent(llm=Provider()).execute(
            {
                "research_topic": "Evidence topic",
                "research_sources": [
                    {"title": "Trusted", "url": "https://example.com/trusted"}
                ],
            }
        )
    )
    assert state["structured_report"]["references"][0]["title"] == "Trusted"


@pytest.mark.parametrize(
    ("report_format", "signature"),
    [("pdf", b"%PDF"), ("docx", b"PK"), ("html", b"<!doctype html>")],
)
def test_report_generation_endpoint_persists_and_downloads(
    client, auth_headers, report_format, signature
):
    project_response = client.post(
        "/api/v1/projects/",
        headers=auth_headers,
        json={"title": "Reports", "research_topic": "Report generation"},
    )
    assert project_response.status_code == 201
    run_response = client.post(
        "/api/v1/research-runs/",
        headers=auth_headers,
        json={
            "project_id": project_response.json()["id"],
            "research_topic": "Report generation",
            "research_depth": "basic",
        },
    )
    assert run_response.status_code == 201
    response = client.post(
        "/api/v1/reports/generate",
        headers=auth_headers,
        json={
            "research_run_id": run_response.json()["id"],
            "report_format": report_format,
        },
    )
    assert response.status_code == 201
    report_id = response.json()["report_id"]
    download = client.get(
        f"/api/v1/reports/{report_id}/download?format={report_format}",
        headers=auth_headers,
    )
    assert download.status_code == 200
    assert download.content.lower().startswith(signature.lower())
    assert client.delete(
        f"/api/v1/reports/{report_id}", headers=auth_headers
    ).status_code == 204
