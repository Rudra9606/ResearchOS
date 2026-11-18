from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent_execution import AgentExecution
from app.models.research_run import ResearchRun
from app.models.project import ResearchProject


def create_agent_execution(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    agent_name: str,
    input_data: dict | None = None
) -> AgentExecution:
    """Create an agent execution record."""

    run = db.scalar(
        select(ResearchRun)
        .join(ResearchProject)
        .where(
            ResearchRun.id == research_run_id,
            ResearchProject.user_id == user_id
        )
    )

    if run is None:
        raise ValueError("Research run not found or access denied.")

    execution = AgentExecution(
        research_run_id=research_run_id,
        agent_name=agent_name,
        status="pending",
        input_data=input_data
    )

    try:
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution
    except Exception:
        db.rollback()
        raise


def get_agent_execution_by_id(
    db: Session,
    execution_id: UUID,
    user_id: UUID
):
    """Retrieve an agent execution."""

    statement = (
        select(AgentExecution)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            AgentExecution.id == execution_id,
            ResearchProject.user_id == user_id
        )
    )

    return db.scalar(statement)


def get_research_run_executions(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    skip: int = 0,
    limit: int | None = None,
):
    """Retrieve all agent executions for a research run."""

    statement = (
        select(AgentExecution)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            AgentExecution.research_run_id == research_run_id,
            ResearchProject.user_id == user_id
        )
        .order_by(AgentExecution.created_at.asc())
        .offset(skip)
    )
    if limit is not None:
        statement = statement.limit(limit)

    return list(db.scalars(statement).all())


def count_research_run_executions(db: Session, research_run_id: UUID, user_id: UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(AgentExecution)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            AgentExecution.research_run_id == research_run_id,
            ResearchProject.user_id == user_id,
        )
    ) or 0


def update_agent_execution(
    db: Session,
    execution_id: UUID,
    user_id: UUID,
    status: str,
    output_data: dict | None = None,
    error_message: str | None = None
):
    """Update agent execution details."""

    allowed_statuses = [
        "pending",
        "running",
        "completed",
        "failed"
    ]

    if status not in allowed_statuses:
        raise ValueError("Invalid agent execution status.")

    execution = get_agent_execution_by_id(
        db, execution_id, user_id
    )

    if execution is None:
        return None

    try:
        execution.status = status

        if output_data is not None:
            execution.output_data = output_data

        execution.error_message = error_message

        if status == "running" and execution.started_at is None:
            execution.started_at = datetime.now(timezone.utc)

        if status in ["completed", "failed"]:
            execution.completed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(execution)
        return execution

    except Exception:
        db.rollback()
        raise


def delete_agent_execution(
    db: Session,
    execution_id: UUID,
    user_id: UUID
) -> bool:
    """Delete an agent execution."""

    execution = get_agent_execution_by_id(
        db, execution_id, user_id
    )

    if execution is None:
        return False

    try:
        db.delete(execution)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
