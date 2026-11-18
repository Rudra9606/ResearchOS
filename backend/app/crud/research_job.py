from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.project import ResearchProject
from app.models.research_job import ResearchJob
from app.models.research_run import ResearchRun


def enqueue_research_job(
    db: Session,
    run_id: UUID,
    user_id: UUID,
    document_ids: list[UUID],
    dataset_ids: list[UUID],
) -> ResearchJob:
    run = db.scalar(
        select(ResearchRun).join(ResearchProject).where(
            ResearchRun.id == run_id, ResearchProject.user_id == user_id
        ).with_for_update()
    )
    if run is None:
        raise LookupError("Research run not found or access denied.")
    if run.status != "pending":
        raise RuntimeError("Research run has already started.")
    if db.scalar(select(ResearchJob.id).where(ResearchJob.research_run_id == run_id)):
        raise RuntimeError("A job already exists for this research run.")

    all_ids = set(document_ids) | set(dataset_ids)
    documents = list(db.scalars(select(Document).where(
        Document.id.in_(all_ids), Document.user_id == user_id,
        Document.project_id == run.project_id,
    )).all()) if all_ids else []
    if len(documents) != len(all_ids):
        raise LookupError("One or more documents were not found or access denied.")
    valid_datasets = {doc.id for doc in documents if doc.file_type in {"csv", "xlsx"}}
    if not set(dataset_ids).issubset(valid_datasets):
        raise LookupError("Datasets must be CSV or XLSX files in this project.")

    job = ResearchJob(
        user_id=user_id,
        research_run_id=run_id,
        job_type="research",
        status="queued",
        payload={
            "document_ids": [str(value) for value in document_ids],
            "dataset_ids": [str(value) for value in dataset_ids],
        },
        attempts=0,
        max_attempts=3,
    )
    try:
        run.status = "queued"
        run.error_message = None
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise


def enqueue_document_job(db: Session, document: Document) -> ResearchJob:
    existing = db.scalar(select(ResearchJob).where(ResearchJob.document_id == document.id).with_for_update())
    if existing is not None:
        if existing.status in {"queued", "running", "cancel_requested"}:
            raise RuntimeError("Document processing is already queued or running.")
        existing.status = "queued"
        existing.attempts = 0
        existing.error_message = None
        existing.available_at = datetime.now(timezone.utc)
        existing.completed_at = None
        existing.started_at = None
        job = existing
    else:
        job = ResearchJob(
            user_id=document.user_id,
            document_id=document.id,
            job_type="document",
            status="queued",
            payload={},
            attempts=0,
            max_attempts=3,
        )
        db.add(job)
    try:
        document.processing_status = "queued"
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise


def get_user_job(db: Session, job_id: UUID, user_id: UUID) -> ResearchJob | None:
    return db.scalar(select(ResearchJob).where(
        ResearchJob.id == job_id, ResearchJob.user_id == user_id
    ))


def list_user_jobs(
    db: Session,
    user_id: UUID,
    research_run_id: UUID | None = None,
    document_id: UUID | None = None,
    limit: int = 100,
) -> list[ResearchJob]:
    statement = select(ResearchJob).where(ResearchJob.user_id == user_id)
    if research_run_id:
        statement = statement.where(ResearchJob.research_run_id == research_run_id)
    if document_id:
        statement = statement.where(ResearchJob.document_id == document_id)
    return list(db.scalars(statement.order_by(ResearchJob.created_at.desc()).limit(limit)).all())


def cancel_user_job(db: Session, job_id: UUID, user_id: UUID) -> ResearchJob | None:
    job = db.scalar(select(ResearchJob).where(
        ResearchJob.id == job_id, ResearchJob.user_id == user_id
    ).with_for_update())
    if job is None:
        return None
    if job.status == "queued":
        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
        _set_target_status(db, job, "cancelled")
    elif job.status == "running":
        job.status = "cancel_requested"
    elif job.status != "cancel_requested":
        raise RuntimeError("Only queued or running jobs can be cancelled.")
    db.commit()
    db.refresh(job)
    return job


def retry_user_job(db: Session, job_id: UUID, user_id: UUID) -> ResearchJob | None:
    job = db.scalar(select(ResearchJob).where(
        ResearchJob.id == job_id, ResearchJob.user_id == user_id
    ).with_for_update())
    if job is None:
        return None
    if job.status not in {"failed", "cancelled"}:
        raise RuntimeError("Only failed or cancelled jobs can be retried.")
    job.status = "queued"
    job.attempts = 0
    job.error_message = None
    job.payload = {**(job.payload or {}), "retry": True}
    job.available_at = datetime.now(timezone.utc)
    job.lease_until = None
    job.completed_at = None
    job.started_at = None
    _set_target_status(db, job, "queued")
    db.commit()
    db.refresh(job)
    return job


def _set_target_status(db: Session, job: ResearchJob, status: str) -> None:
    if job.research_run_id:
        run = db.get(ResearchRun, job.research_run_id)
        if run:
            run.status = status
            run.error_message = job.error_message
            if status in {"queued", "cancelled"}:
                run.completed_at = datetime.now(timezone.utc) if status == "cancelled" else None
                if status == "queued":
                    run.progress = 0
                    run.current_step = None
                    run.started_at = None
    elif job.document_id:
        document = db.get(Document, job.document_id)
        if document:
            document.processing_status = "pending" if status == "queued" else status


def claim_next_job(db: Session, lease_seconds: int = 900) -> ResearchJob | None:
    now = datetime.now(timezone.utc)
    # A worker can die after claiming a job. Requeue stale leases at startup/poll.
    stale = db.scalars(select(ResearchJob).where(
        ResearchJob.status.in_(["running", "cancel_requested"]),
        ResearchJob.lease_until < now,
    ).with_for_update(skip_locked=True)).all()
    for job in stale:
        if job.status == "cancel_requested":
            job.status = "cancelled"
            job.completed_at = now
            _set_target_status(db, job, "cancelled")
        elif job.attempts >= job.max_attempts:
            job.status = "failed"
            job.completed_at = now
            job.error_message = "Worker lease expired after the maximum number of attempts."
            _set_target_status(db, job, "failed")
        else:
            job.status = "queued"
            job.available_at = now + timedelta(seconds=min(300, 2 ** job.attempts))
            job.lease_until = None
            _set_target_status(db, job, "queued")
    candidate = db.scalar(select(ResearchJob).where(
        ResearchJob.status == "queued", ResearchJob.available_at <= now,
    ).order_by(ResearchJob.available_at, ResearchJob.created_at).with_for_update(skip_locked=True).limit(1))
    if candidate is None:
        db.commit()
        return None
    candidate.status = "running"
    candidate.attempts += 1
    candidate.started_at = now
    candidate.lease_until = now + timedelta(seconds=lease_seconds)
    if candidate.document_id:
        _set_target_status(db, candidate, "processing")
    db.commit()
    db.refresh(candidate)
    return candidate


def update_job_lease(db: Session, job_id: UUID, lease_seconds: int = 900) -> None:
    job = db.get(ResearchJob, job_id)
    if job and job.status in {"running", "cancel_requested"}:
        job.lease_until = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        db.commit()


def job_cancel_requested(db: Session, job_id: UUID) -> bool:
    job = db.get(ResearchJob, job_id)
    return job is None or job.status in {"cancel_requested", "cancelled"}


def finish_job(db: Session, job_id: UUID, status: str, error_message: str | None = None) -> ResearchJob | None:
    job = db.get(ResearchJob, job_id)
    if job is None:
        return None
    if job.status == "cancel_requested":
        status = "cancelled"
    job.status = status
    job.error_message = error_message
    job.lease_until = None
    job.completed_at = datetime.now(timezone.utc) if status in {"completed", "failed", "cancelled"} else None
    _set_target_status(db, job, status)
    db.commit()
    db.refresh(job)
    return job
