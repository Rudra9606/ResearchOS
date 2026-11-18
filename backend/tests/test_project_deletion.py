from pathlib import Path

import pytest

from app.core.config import settings
from app.crud.project import create_project, get_project_by_id
from app.crud.research_run import create_research_run
from app.models.document import Document
from app.models.research_job import ResearchJob
from app.models.research_report import ResearchReport
from app.schemas.project import ProjectCreate
from app.schemas.research_run import ResearchRunCreate
from app.services.project_service import delete_user_project


def _project_and_run(db_session, user):
    project = create_project(
        db_session,
        ProjectCreate(title="Cleanup test", research_topic="Project artifact cleanup"),
        user.id,
    )
    run = create_research_run(
        db_session,
        ResearchRunCreate(
            project_id=project.id,
            research_topic="Project artifact cleanup",
            research_depth="standard",
        ),
        user.id,
    )
    return project, run


def test_project_delete_removes_owned_upload_and_report_files(
    db_session, test_user, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_root))
    project, run = _project_and_run(db_session, test_user)

    upload = upload_root / str(test_user.id) / "source.pdf"
    report = tmp_path / "reports" / str(test_user.id) / "report.pdf"
    upload.parent.mkdir(parents=True)
    report.parent.mkdir(parents=True)
    upload.write_bytes(b"source")
    report.write_bytes(b"report")
    db_session.add(Document(
        project_id=project.id,
        user_id=test_user.id,
        filename="source.pdf",
        file_type="pdf",
        file_path=str(upload),
        file_size=6,
        processing_status="completed",
    ))
    db_session.add(ResearchReport(
        research_run_id=run.id,
        title="Report",
        content="Report content",
        report_format="pdf",
        file_path=str(report),
        generation_status="completed",
    ))
    db_session.commit()

    assert delete_user_project(db_session, project.id, test_user.id)
    assert not upload.exists()
    assert not report.exists()
    assert get_project_by_id(db_session, project.id, test_user.id) is None


def test_project_delete_refuses_while_background_job_is_active(db_session, test_user):
    project, run = _project_and_run(db_session, test_user)
    db_session.add(ResearchJob(
        user_id=test_user.id,
        research_run_id=run.id,
        document_id=None,
        job_type="research",
        status="running",
        payload={},
    ))
    db_session.commit()

    with pytest.raises(ValueError, match="background work in progress"):
        delete_user_project(db_session, project.id, test_user.id)
    assert get_project_by_id(db_session, project.id, test_user.id) is not None
