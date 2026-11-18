"""Database-backed at-least-once worker for ResearchOS jobs.

Run with ``python -m app.worker``. Use one worker replica initially; PostgreSQL
row locks allow additional replicas when worker capacity is provisioned.
"""

import asyncio
import logging
import os
from uuid import UUID

from app.crud.research_job import (
    claim_next_job,
    finish_job,
    job_cancel_requested,
    update_job_lease,
)
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.research_job import ResearchJob
from app.utils.logging import get_logger
from app.utils.request_context import request_id_context

logger = get_logger(__name__)
POLL_SECONDS = float(os.getenv("JOB_POLL_SECONDS", "2"))
LEASE_SECONDS = int(os.getenv("JOB_LEASE_SECONDS", "900"))


class JobCancelled(Exception):
    pass


async def _heartbeat(job_id: UUID) -> None:
    while True:
        await asyncio.sleep(max(10, LEASE_SECONDS // 3))
        with SessionLocal() as db:
            update_job_lease(db, job_id, LEASE_SECONDS)


def _is_cancelled(job_id: UUID) -> bool:
    with SessionLocal() as db:
        return job_cancel_requested(db, job_id)


async def _process_job(job: ResearchJob) -> None:
    if _is_cancelled(job.id):
        raise JobCancelled()
    if job.job_type == "research":
        from app.services.research_execution import execute_research_run

        with SessionLocal() as db:
            from app.models.research_run import ResearchRun
            run = db.get(ResearchRun, job.research_run_id)
            if run is not None and run.status == "completed":
                return
            await execute_research_run(
                db,
                job.research_run_id,
                job.user_id,
                [UUID(value) for value in job.payload.get("document_ids", [])],
                [UUID(value) for value in job.payload.get("dataset_ids", [])],
                job_id=job.id,
                cancel_check=lambda: _is_cancelled(job.id),
                retry_attempt=job.attempts > 1 or bool(job.payload.get("retry")),
            )
        return
    if job.job_type == "document":
        with SessionLocal() as db:
            document = db.get(Document, job.document_id)
            if document is None or document.user_id != job.user_id:
                raise LookupError("Document no longer exists or access was revoked.")
            if document.processing_status == "completed":
                return
            document_id, user_id = document.id, document.user_id
            file_path, file_type = document.file_path, document.file_type

        from app.services.document_processing import process_document

        result = await asyncio.to_thread(
            process_document,
            document_id,
            file_path,
            file_type,
            user_id,
            lambda: _is_cancelled(job.id),
        )
        if result["status"] == "cancelled":
            raise JobCancelled()
        if result["status"] != "completed":
            raise RuntimeError(result.get("error", "Document processing failed."))
        return
    raise ValueError(f"Unsupported background job type: {job.job_type}")


async def _run_one(job: ResearchJob) -> None:
    request_token = request_id_context.set(f"job-{job.id}")
    heartbeat = asyncio.create_task(_heartbeat(job.id))
    try:
        await _process_job(job)
    except JobCancelled:
        with SessionLocal() as db:
            finish_job(db, job.id, "cancelled")
        logger.info("Background job cancelled", extra={"job_id": str(job.id)})
    except Exception as exc:
        with SessionLocal() as db:
            current = db.get(ResearchJob, job.id)
            if current is None:
                return
            if current.status == "cancel_requested":
                finish_job(db, job.id, "cancelled")
            elif current.attempts < current.max_attempts:
                from datetime import datetime, timedelta, timezone
                from app.crud.research_job import _set_target_status

                current.status = "queued"
                current.error_message = str(exc)[:4000]
                current.available_at = datetime.now(timezone.utc) + timedelta(
                    seconds=min(300, 2 ** current.attempts)
                )
                current.lease_until = None
                _set_target_status(db, current, "queued")
                db.commit()
            else:
                finish_job(db, job.id, "failed", str(exc)[:4000])
        logger.exception("Background job attempt failed", extra={"job_id": str(job.id)})
    else:
        with SessionLocal() as db:
            finish_job(db, job.id, "completed")
        logger.info("Background job completed", extra={"job_id": str(job.id)})
    finally:
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass
        request_id_context.reset(request_token)


async def run_worker() -> None:
    logger.info("ResearchOS job worker started")
    while True:
        with SessionLocal() as db:
            job = claim_next_job(db, LEASE_SECONDS)
        if job is None:
            await asyncio.sleep(POLL_SECONDS)
            continue
        logger.info("Claimed background job", extra={"job_id": str(job.id), "job_type": job.job_type})
        await _run_one(job)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    asyncio.run(run_worker())
