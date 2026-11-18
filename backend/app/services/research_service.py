"""Research Service - handles research execution, progress tracking, and LangGraph coordination."""

from uuid import UUID
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.crud.research_run import (
    create_research_run,
    get_research_run_by_id,
    update_research_run_progress,
    update_research_run_status,
    delete_research_run,
)
from app.crud.agent_execution import (
    create_agent_execution,
    update_agent_execution,
)
from app.crud.research_source import create_research_source
from app.crud.verified_claim import create_verified_claim
from app.schemas.research_run import ResearchRunCreate


def create_research_execution(
    db: Session,
    run_data: ResearchRunCreate,
    user_id: UUID,
):
    """Create a new research run."""
    return create_research_run(
        db=db,
        run_data=run_data,
        user_id=user_id,
    )


def get_research_execution(
    db: Session,
    run_id: UUID,
    user_id: UUID,
):
    """Get a research run by ID with ownership check."""
    return get_research_run_by_id(
        db=db,
        run_id=run_id,
        user_id=user_id,
    )


def update_progress(
    db: Session,
    run_id: UUID,
    user_id: UUID,
    progress: int,
    current_step: str | None = None,
):
    """Update research run progress."""
    return update_research_run_progress(
        db=db,
        run_id=run_id,
        user_id=user_id,
        progress=progress,
        current_step=current_step,
    )


def update_status(
    db: Session,
    run_id: UUID,
    user_id: UUID,
    status: str,
    error_message: str | None = None,
):
    """Update research run status."""
    return update_research_run_status(
        db=db,
        run_id=run_id,
        user_id=user_id,
        status=status,
        error_message=error_message,
    )


def delete_research_execution(
    db: Session,
    run_id: UUID,
    user_id: UUID,
) -> bool:
    """Delete a research run."""
    return delete_research_run(
        db=db,
        run_id=run_id,
        user_id=user_id,
    )


def record_agent_execution(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    agent_name: str,
    input_data: dict | None = None,
):
    """Record an agent execution."""
    return create_agent_execution(
        db=db,
        research_run_id=research_run_id,
        user_id=user_id,
        agent_name=agent_name,
        input_data=input_data,
    )


def complete_agent_execution(
    db: Session,
    execution_id: UUID,
    user_id: UUID,
    status: str,
    output_data: dict | None = None,
    error_message: str | None = None,
):
    """Complete an agent execution."""
    return update_agent_execution(
        db=db,
        execution_id=execution_id,
        user_id=user_id,
        status=status,
        output_data=output_data,
        error_message=error_message,
    )


def add_research_source(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    source_data,
):
    """Add a research source."""
    return create_research_source(
        db=db,
        research_run_id=research_run_id,
        user_id=user_id,
        source_data=source_data,
    )


def add_verified_claim(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    claim_data,
):
    """Add a verified claim."""
    return create_verified_claim(
        db=db,
        research_run_id=research_run_id,
        user_id=user_id,
        claim_data=claim_data,
    )