from typing import Any
from uuid import UUID

from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.crud.research_run import (
    create_research_run,
    get_research_run_by_id,
    get_project_research_runs,
    start_research_run,
    update_research_run_status,
    delete_research_run,
)
from app.schemas.research_run import (
    ResearchRunCreate,
    ResearchRunResponse,
    ResearchRunStatusResponse,
)
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.research_job import ResearchJob
from app.schemas.research_source import ResearchSourceCreate
from app.schemas.verified_claim import VerifiedClaimCreate
from app.schemas.research_report import ResearchReportCreate
from app.crud.research_source import create_research_source
from app.crud.verified_claim import create_verified_claim
from app.crud.research_report import create_research_report, update_research_report
from app.schemas.report_document import StructuredResearchReport
from app.services.report_service import export_report_document, safe_report_path
from app.crud.research_job import enqueue_research_job
from app.schemas.research_job import ResearchJobResponse
from app.services.research_execution import (
    ResearchCancelled,
    execute_research_run as execute_research_run_service,
)

router = APIRouter()


@router.post("/", response_model=ResearchRunResponse, status_code=status.HTTP_201_CREATED)
def create_research_run_endpoint(
    run_data: ResearchRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new research run."""
    try:
        run = create_research_run(db, run_data, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return run


@router.get("/", response_model=list[ResearchRunResponse])
def list_research_runs(
    project_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve all research runs for a project."""
    runs = get_project_research_runs(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return runs


@router.get("/{run_id}", response_model=ResearchRunResponse)
def get_research_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve a research run by ID."""
    run = get_research_run_by_id(
        db=db,
        run_id=run_id,
        user_id=current_user.id,
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research run not found or access denied.",
        )
    return run


@router.get("/{run_id}/status", response_model=ResearchRunStatusResponse)
def get_research_run_status(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve research run status."""
    run = get_research_run_by_id(
        db=db,
        run_id=run_id,
        user_id=current_user.id,
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research run not found or access denied.",
        )
    return ResearchRunStatusResponse(
        research_run_id=run.id,
        status=run.status,
        progress=run.progress,
        current_step=run.current_step,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.post("/{run_id}/execute", response_model=ResearchRunResponse)
async def execute_research_run(
    run_id: UUID,
    document_ids: list[UUID] | None = Query(default=None),
    dataset_ids: list[UUID] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResearchRunResponse:
    """Compatibility endpoint: execute inline; use /enqueue for durable work."""
    if db.scalar(select(ResearchJob.id).where(
        ResearchJob.research_run_id == run_id,
        ResearchJob.status.in_(["queued", "running", "cancel_requested"]),
    )):
        raise HTTPException(status_code=409, detail="Research run already has a queued job.")
    try:
        return await execute_research_run_service(
            db, run_id, current_user.id, document_ids, dataset_ids
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ResearchCancelled as exc:
        raise HTTPException(status_code=409, detail="Research run was cancelled.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Research workflow execution failed.") from exc


@router.post("/{run_id}/enqueue", response_model=ResearchJobResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_research_run(
    run_id: UUID,
    document_ids: list[UUID] | None = Query(default=None),
    dataset_ids: list[UUID] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist a research job for the background worker."""
    try:
        return enqueue_research_job(
            db, run_id, current_user.id, document_ids or [], dataset_ids or []
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_research_run_endpoint(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a research run."""
    success = delete_research_run(
        db=db,
        run_id=run_id,
        user_id=current_user.id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research run not found or access denied.",
        )
