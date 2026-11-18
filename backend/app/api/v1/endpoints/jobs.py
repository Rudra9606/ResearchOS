from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.crud.research_job import cancel_user_job, get_user_job, list_user_jobs, retry_user_job
from app.db.session import get_db
from app.models.user import User
from app.schemas.research_job import ResearchJobResponse

router = APIRouter()


@router.get("/", response_model=list[ResearchJobResponse])
def list_jobs(
    research_run_id: UUID | None = Query(default=None),
    document_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if (research_run_id is None) == (document_id is None):
        raise HTTPException(status_code=422, detail="Provide exactly one of research_run_id or document_id.")
    return list_user_jobs(db, current_user.id, research_run_id, document_id, limit)


@router.get("/{job_id}", response_model=ResearchJobResponse)
def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = get_user_job(db, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or access denied.")
    return job


@router.post("/{job_id}/cancel", response_model=ResearchJobResponse)
def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        job = cancel_user_job(db, job_id, current_user.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or access denied.")
    return job


@router.post("/{job_id}/retry", response_model=ResearchJobResponse, status_code=202)
def retry_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        job = retry_user_job(db, job_id, current_user.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or access denied.")
    return job
