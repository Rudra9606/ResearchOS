"""Phase 7 security-contract and end-to-end workflow coverage."""

from uuid import uuid4

from app.agents.fact_checker import ClaimExtraction, ClaimVerification
from app.agents.planner import ResearchPlan
from app.schemas.report_document import ReportCitation, ReportSection, StructuredResearchReport
from app.schemas.research_search import (
    AcademicPaper,
    AcademicSearchResult,
    WebSearchResult,
)


class StructuredProvider:
    def __init__(self, values):
        self.values = values

    async def generate_structured(self, prompt, response_model, **kwargs):
        return self.values[response_model]


def _report():
    section_names = (
        "executive_summary research_objectives research_questions methodology "
        "web_research_findings academic_research_findings document_analysis_findings "
        "dataset_analysis_findings verified_claims limitations conclusion"
    ).split()
    sections = {
        name: ReportSection(title=name.replace("_", " ").title(), content="Evidence reviewed.")
        for name in section_names
    }
    return StructuredResearchReport(
        title="Integration test report",
        **sections,
        references=[
            ReportCitation(
                citation_id="[1]",
                title="Test evidence",
                url="https://example.org/source",
            )
        ],
    )


def test_research_run_executes_and_persists_evidence_report_and_download(
    client, auth_headers, monkeypatch
):
    from app.workflows.research_workflow import ResearchWorkflow

    plan = ResearchPlan(
        objectives=["Review supplied test evidence"],
        subquestions=["What does the evidence report?"],
        strategy="Search mocked providers and compare evidence.",
        required_sources=["web", "academic"],
        steps=["search", "synthesize"],
    )
    provider = StructuredProvider(
        {
            ResearchPlan: plan,
            ClaimExtraction: ClaimExtraction(
                claims=["A deterministic finding is documented."]
            ),
            ClaimVerification: ClaimVerification(
                verification_status="supported",
                explanation="The mocked web source directly states the finding.",
                confidence_score=0.9,
                evidence_references=["https://example.org/source"],
            ),
            StructuredResearchReport: _report(),
        }
    )

    class WebService:
        async def search_topic(self, topic, *, queries=None):
            return [
                WebSearchResult(
                    title="Test web evidence",
                    url="https://example.org/source",
                    content="A deterministic web finding.",
                )
            ]

    class AcademicService:
        async def search(self, topic):
            return AcademicSearchResult(
                papers=(
                    AcademicPaper(
                        title="Test academic evidence",
                        abstract="A deterministic academic finding.",
                        paper_url="https://example.org/paper",
                        provider="test",
                    ),
                )
            )

    class MockedResearchWorkflow(ResearchWorkflow):
        def __init__(self, **kwargs):
            super().__init__(
                **kwargs,
                planner_llm=provider,
                web_research_service=WebService(),
                academic_research_service=AcademicService(),
                fact_checker_llm=provider,
                report_llm=provider,
            )

    monkeypatch.setattr(
        "app.workflows.research_workflow.ResearchWorkflow", MockedResearchWorkflow
    )

    project_response = client.post(
        "/api/v1/projects/",
        json={"title": "Phase 7", "research_topic": "Workflow integration"},
        headers=auth_headers,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    run_response = client.post(
        "/api/v1/research-runs/",
        json={
            "project_id": project_id,
            "research_topic": "Workflow integration evidence",
            "research_depth": "standard",
        },
        headers=auth_headers,
    )
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]

    execution = client.post(
        f"/api/v1/research-runs/{run_id}/execute", headers=auth_headers
    )
    assert execution.status_code == 200, execution.text
    assert execution.json()["status"] == "completed"
    assert execution.json()["progress"] == 100
    assert client.post(
        f"/api/v1/research-runs/{run_id}/execute", headers=auth_headers
    ).status_code == 409

    status_response = client.get(
        f"/api/v1/research-runs/{run_id}/status", headers=auth_headers
    )
    assert status_response.json()["status"] == "completed"

    sources = client.get(
        f"/api/v1/research-sources/?research_run_id={run_id}",
        headers=auth_headers,
    )
    assert sources.status_code == 200
    assert sources.json()["total"] == 2

    claims = client.get(
        f"/api/v1/verified-claims/?research_run_id={run_id}",
        headers=auth_headers,
    )
    assert claims.status_code == 200
    assert claims.json()["total"] == 1
    assert claims.json()["claims"][0]["verification_status"] == "supported"

    executions = client.get(
        f"/api/v1/agent-executions/?research_run_id={run_id}",
        headers=auth_headers,
    )
    assert executions.status_code == 200
    assert executions.json()["total"] >= 5
    assert all(item["status"] == "completed" for item in executions.json()["executions"])

    reports = client.get(
        f"/api/v1/reports/?research_run_id={run_id}", headers=auth_headers
    )
    assert reports.status_code == 200
    assert reports.json()["total"] == 1
    report_id = reports.json()["reports"][0]["id"]
    assert reports.json()["reports"][0]["generation_status"] == "completed"

    download = client.get(
        f"/api/v1/reports/{report_id}/download?format=pdf",
        headers=auth_headers,
    )
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")

    # Remove the report artifact created by this test.
    assert client.delete(
        f"/api/v1/reports/{report_id}", headers=auth_headers
    ).status_code == 204


def test_public_api_does_not_allow_forging_evidence_or_progress(
    client, auth_headers
):
    run_id = uuid4()
    claim_id = uuid4()
    document_id = uuid4()
    execution_id = uuid4()
    report_id = uuid4()

    mutating_requests = [
        ("post", f"/api/v1/research-sources/?research_run_id={run_id}", 405),
        ("post", f"/api/v1/verified-claims/?research_run_id={run_id}", 405),
        ("patch", f"/api/v1/verified-claims/{claim_id}", 405),
        ("patch", f"/api/v1/research-runs/{run_id}/status", 405),
        ("patch", f"/api/v1/research-runs/{run_id}/progress", 404),
        ("patch", f"/api/v1/documents/{document_id}/status", 404),
        ("post", "/api/v1/agent-executions/", 405),
        ("patch", f"/api/v1/agent-executions/{execution_id}", 405),
        ("patch", f"/api/v1/reports/{report_id}", 405),
    ]
    for method, url, expected_status in mutating_requests:
        response = getattr(client, method)(url, headers=auth_headers)
        assert response.status_code == expected_status, (method, url, response.text)


def test_upload_size_is_enforced_while_streaming_and_files_are_cleaned(
    client, auth_headers, monkeypatch, tmp_path
):
    from app.api.v1.endpoints import documents
    from app.services import document_processing

    project = client.post(
        "/api/v1/projects/",
        json={"title": "Upload test", "research_topic": "Upload safety"},
        headers=auth_headers,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    monkeypatch.setattr(documents, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(documents, "MAX_FILE_SIZE", 3)
    monkeypatch.setattr(
        document_processing,
        "process_document",
        lambda **kwargs: {"status": "completed", "chunks_created": 1},
    )

    oversized = client.post(
        f"/api/v1/documents/upload?project_id={project_id}",
        headers=auth_headers,
        files={"file": ("too-large.txt", b"1234", "text/plain")},
    )
    assert oversized.status_code == 413
    assert not list((tmp_path / "uploads").rglob("*"))

    monkeypatch.setattr(documents, "MAX_FILE_SIZE", 16)
    invalid_pdf = client.post(
        f"/api/v1/documents/upload?project_id={project_id}",
        headers=auth_headers,
        files={"file": ("fake.pdf", b"not a PDF", "application/pdf")},
    )
    assert invalid_pdf.status_code == 400
    assert not list((tmp_path / "uploads").rglob("*"))

    accepted = client.post(
        f"/api/v1/documents/upload?project_id={project_id}",
        headers=auth_headers,
        files={"file": ("small.txt", b"123", "text/plain")},
    )
    assert accepted.status_code == 201, accepted.text
    stored = list((tmp_path / "uploads").rglob("*.txt"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == b"123"
    assert client.delete(
        f"/api/v1/documents/{accepted.json()['id']}", headers=auth_headers
    ).status_code == 204


def test_postgresql_vector_search_uses_cosine_distance_and_user_scope(
    db_session, test_user
):
    from app.core.security import hash_password
    from app.crud.document import create_document, update_document_status
    from app.crud.document_chunk import create_document_chunk
    from app.crud.project import create_project
    from app.crud.user import create_user
    from app.rag.retrieval import RAGRetrievalService
    from app.schemas.document import DocumentCreate
    from app.schemas.project import ProjectCreate
    from app.schemas.user import UserCreate

    other_user = create_user(
        db_session,
        UserCreate(
            name="Other User",
            email="vector-other@example.com",
            password="OtherPassword123!",
        ),
        hash_password("OtherPassword123!"),
    )

    owner_project = create_project(
        db_session,
        ProjectCreate(title="Owner vectors", research_topic="Vector ownership"),
        test_user.id,
    )
    other_project = create_project(
        db_session,
        ProjectCreate(title="Other vectors", research_topic="Vector ownership"),
        other_user.id,
    )

    def add_document(project, user, filename, content):
        document = create_document(
            db_session,
            DocumentCreate(filename=filename, file_type="txt", file_size=10),
            project.id,
            user.id,
            f"/temporary/{filename}",
        )
        update_document_status(db_session, document.id, user.id, "completed")
        create_document_chunk(
            db_session,
            document.id,
            0,
            content,
            embedding=[1.0] + [0.0] * 383,
        )
        return document

    owned = add_document(
        owner_project, test_user, "owned.txt", "Owner-only evidence."
    )
    add_document(other_project, other_user, "private.txt", "Private evidence.")

    class FixedEmbedding:
        def embed_query(self, query):
            return [1.0] + [0.0] * 383

    results = RAGRetrievalService(
        db_session, embedding_service=FixedEmbedding()
    ).semantic_search("evidence", user_id=test_user.id, top_k=10)

    assert len(results) == 1
    assert results[0]["document_id"] == str(owned.id)
    assert results[0]["document_filename"] == "owned.txt"

