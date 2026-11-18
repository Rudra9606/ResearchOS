from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.crud.agent_execution import (
    get_agent_execution_by_id,
    get_research_run_executions,
    count_research_run_executions,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent import (
    AgentExecutionListResponse,
    AgentExecutionResponse,
)

router = APIRouter()


@router.get("/", response_model=AgentExecutionListResponse)
def list_executions(
    research_run_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    executions = get_research_run_executions(
        db, research_run_id, current_user.id, skip=skip, limit=limit
    )
    return AgentExecutionListResponse(
        total=count_research_run_executions(db, research_run_id, current_user.id),
        executions=executions,
    )


@router.get("/{execution_id}", response_model=AgentExecutionResponse)
def get_execution(
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    execution = get_agent_execution_by_id(db, execution_id, current_user.id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Agent execution not found or access denied.")
    return execution


