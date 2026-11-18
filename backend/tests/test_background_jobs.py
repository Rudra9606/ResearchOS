from datetime import datetime, timedelta, timezone
import asyncio
from uuid import UUID

from app.crud.research_job import claim_next_job, enqueue_research_job
from app.models.research_job import ResearchJob
from app.models.research_run import ResearchRun


def _make_run(client, auth_headers):
    project = client.post(
        "/api/v1/projects/",
        json={"title": "Queued work", "research_topic": "Durable research workflow"},
        headers=auth_headers,
    )
    assert project.status_code == 201
    run = client.post(
        "/api/v1/research-runs/",
        json={
            "project_id": project.json()["id"],
            "research_topic": "Durable research workflow",
            "research_depth": "basic",
        },
        headers=auth_headers,
    )
    assert run.status_code == 201
    return run.json()


def test_enqueue_job_poll_cancel_and_retry(client, auth_headers):
    run = _make_run(client, auth_headers)
    response = client.post(
        f"/api/v1/research-runs/{run['id']}/enqueue",
        headers=auth_headers,
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["job_type"] == "research"
    assert job["status"] == "queued"
    assert client.get(f"/api/v1/jobs/{job['id']}", headers=auth_headers).json()["status"] == "queued"
    assert client.get(
        f"/api/v1/research-runs/{run['id']}/status", headers=auth_headers
    ).json()["status"] == "queued"
    assert client.post(
        f"/api/v1/research-runs/{run['id']}/enqueue", headers=auth_headers
    ).status_code == 409

    cancelled = client.post(f"/api/v1/jobs/{job['id']}/cancel", headers=auth_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    retried = client.post(f"/api/v1/jobs/{job['id']}/retry", headers=auth_headers)
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"


def test_document_background_upload_is_queued_without_inline_processing(
    client, auth_headers, monkeypatch, tmp_path, db_session
):
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    from app.api.v1.endpoints import documents
    from app.models.document import Document
    from app.services import document_processing
    from app import worker

    project = client.post(
        "/api/v1/projects/",
        json={"title": "Async upload", "research_topic": "Document queue"},
        headers=auth_headers,
    )
    monkeypatch.setattr(documents, "UPLOAD_DIR", tmp_path / "uploads")

    def inline_processing_is_not_used(**kwargs):
        raise AssertionError("background upload must not run processing inline")

    monkeypatch.setattr(document_processing, "process_document", inline_processing_is_not_used)
    response = client.post(
        f"/api/v1/documents/upload?project_id={project.json()['id']}&background=true",
        headers=auth_headers,
        files={"file": ("queued.txt", b"Document is queued.", "text/plain")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["processing_status"] == "queued"

    document_id = response.json()["id"]
    job = db_session.scalar(select(ResearchJob).where(ResearchJob.document_id == document_id))
    claimed = claim_next_job(db_session)
    assert claimed.id == job.id
    test_sessions = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", test_sessions)
    calls = []

    def process_in_worker(*args, **kwargs):
        calls.append(args[0])
        return {"status": "completed"}

    monkeypatch.setattr(document_processing, "process_document", process_in_worker)
    import asyncio
    asyncio.run(worker._run_one(claimed))
    assert calls == [UUID(document_id)]
    with test_sessions() as session:
        assert session.get(Document, document_id).processing_status == "completed"
        assert session.get(ResearchJob, job.id).status == "completed"


def test_job_claim_increments_attempt_and_expired_lease_is_requeued(db_session, test_user):
    from app.crud.project import create_project
    from app.crud.research_run import create_research_run
    from app.schemas.project import ProjectCreate
    from app.schemas.research_run import ResearchRunCreate

    project = create_project(
        db_session,
        ProjectCreate(title="Lease test", research_topic="Lease recovery"),
        test_user.id,
    )
    run = create_research_run(
        db_session,
        ResearchRunCreate(
            project_id=project.id,
            research_topic="Lease recovery test",
            research_depth="basic",
        ),
        test_user.id,
    )
    job = enqueue_research_job(db_session, run.id, test_user.id, [], [])

    claimed = claim_next_job(db_session, lease_seconds=60)
    assert claimed.id == job.id
    assert claimed.status == "running"
    assert claimed.attempts == 1

    claimed.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert claim_next_job(db_session, lease_seconds=60) is None
    db_session.refresh(claimed)
    assert claimed.status == "queued"


def test_worker_executes_queued_research_and_persists_outputs(
    db_session, test_user, monkeypatch
):
    from sqlalchemy.orm import sessionmaker

    from app.crud.project import create_project
    from app.crud.research_run import create_research_run
    from app.schemas.project import ProjectCreate
    from app.schemas.research_run import ResearchRunCreate
    from app.workflows import research_workflow
    from app import worker

    project = create_project(
        db_session,
        ProjectCreate(title="Worker test", research_topic="Worker integration"),
        test_user.id,
    )
    run = create_research_run(
        db_session,
        ResearchRunCreate(
            project_id=project.id,
            research_topic="Worker integration",
            research_depth="basic",
        ),
        test_user.id,
    )
    job = enqueue_research_job(db_session, run.id, test_user.id, [], [])
    job = claim_next_job(db_session)

    class MockWorkflow:
        def __init__(self, **kwargs):
            pass

        async def run(self, **kwargs):
            return {
                "research_sources": [{
                    "title": "Verified worker source",
                    "url": "https://example.org/worker",
                    "source_type": "web",
                }],
                "verified_claims": [],
                "research_errors": {},
            }

    test_sessions = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", test_sessions)
    monkeypatch.setattr(research_workflow, "ResearchWorkflow", MockWorkflow)
    asyncio.run(worker._run_one(job))

    with test_sessions() as session:
        completed = session.get(ResearchJob, job.id)
        finished_run = session.get(ResearchRun, run.id)
        assert completed.status == "completed"
        assert finished_run.status == "completed"
        assert len(finished_run.sources) == 1


def test_worker_retry_cleans_partial_evidence_before_reexecution(db_session, test_user, monkeypatch):
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    from app.crud.project import create_project
    from app.crud.research_run import create_research_run
    from app.models.research_source import ResearchSource
    from app.schemas.project import ProjectCreate
    from app.schemas.research_run import ResearchRunCreate
    from app.workflows import research_workflow
    from app import worker

    project = create_project(
        db_session,
        ProjectCreate(title="Retry test", research_topic="Idempotent retry"),
        test_user.id,
    )
    run = create_research_run(
        db_session,
        ResearchRunCreate(
            project_id=project.id,
            research_topic="Idempotent retry test",
            research_depth="basic",
        ),
        test_user.id,
    )
    job = enqueue_research_job(db_session, run.id, test_user.id, [], [])
    test_sessions = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", test_sessions)
    attempts = 0

    class FlakyWorkflow:
        def __init__(self, **kwargs):
            pass

        async def run(self, **kwargs):
            nonlocal attempts
            attempts += 1
            result = {"research_sources": [{
                "title": "Retry source", "url": "https://example.org/retry", "source_type": "web",
            }], "verified_claims": []}
            if attempts == 1:
                return {**result, "research_errors": {"web": "temporary provider error"}}
            return {**result, "research_errors": {}}

    monkeypatch.setattr(research_workflow, "ResearchWorkflow", FlakyWorkflow)
    first = claim_next_job(db_session)
    asyncio.run(worker._run_one(first))
    with test_sessions() as session:
        queued = session.get(ResearchJob, job.id)
        assert queued.status == "queued"
        queued.available_at = datetime.now(timezone.utc)
        session.commit()

    second = claim_next_job(db_session)
    assert second.attempts == 2
    asyncio.run(worker._run_one(second))
    with test_sessions() as session:
        assert session.get(ResearchJob, job.id).status == "completed"
        assert session.get(ResearchRun, run.id).status == "completed"
        sources = session.scalars(select(ResearchSource).where(ResearchSource.research_run_id == run.id)).all()
        assert len(sources) == 1
        assert attempts == 2
