from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.crud.research_source import (
    get_research_source_by_id,
    get_research_run_sources,
    count_research_run_sources,
    delete_research_source,
)
from app.schemas.research_source import (
    ResearchSourceResponse,
    ResearchSourceListResponse,
)
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=ResearchSourceListResponse)
def list_research_sources(
    research_run_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve all research sources for a research run."""
    sources = get_research_run_sources(
        db=db,
        research_run_id=research_run_id,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return ResearchSourceListResponse(
        total=count_research_run_sources(db, research_run_id, current_user.id),
        sources=sources,
    )


@router.get("/{source_id}", response_model=ResearchSourceResponse)
def get_research_source(
    source_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve a research source by ID."""
    source = get_research_source_by_id(
        db=db,
        source_id=source_id,
        user_id=current_user.id,
    )
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research source not found or access denied.",
        )
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_research_source_endpoint(
    source_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a research source."""
    success = delete_research_source(
        db=db,
        source_id=source_id,
        user_id=current_user.id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research source not found or access denied.",
        )
