from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.crud.project import (
    create_project,
    get_project_by_id,
    get_user_projects,
    count_user_projects,
    update_project,
)
from app.services.project_service import delete_user_project
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
)
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new research project."""
    project = create_project(
        db=db,
        project_data=project_data,
        user_id=current_user.id,
    )
    return project


@router.get("/", response_model=ProjectListResponse)
def list_projects(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve all projects for the current user."""
    projects = get_user_projects(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    total = count_user_projects(db, current_user.id)
    return ProjectListResponse(total=total, projects=projects)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve a project by ID."""
    project = get_project_by_id(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied.",
        )
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project_endpoint(
    project_id: UUID,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update a research project."""
    project = update_project(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
        project_data=project_data,
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied.",
        )
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_endpoint(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a research project."""
    try:
        success = delete_user_project(db, project_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied.",
        )
