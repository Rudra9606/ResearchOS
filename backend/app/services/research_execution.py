"""Shared execution path for synchronous requests and durable workers."""

from pathlib import Path
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.crud.document import get_document_by_id
from app.crud.research_report import create_research_report, update_research_report
from app.crud.research_run import (
    get_research_run_by_id,
    start_research_run,
    update_research_run_status,
)
from app.crud.research_source import create_research_source
from app.crud.verified_claim import create_verified_claim
from app.models.agent_execution import AgentExecution
from app.models.research_report import ResearchReport
from app.models.research_source import ResearchSource
from app.models.verified_claim import VerifiedClaim
from app.schemas.report_document import StructuredResearchReport
from app.schemas.research_report import ResearchReportCreate
from app.schemas.research_source import ResearchSourceCreate
from app.schemas.verified_claim import VerifiedClaimCreate
from app.services.report_service import export_report_document


class ResearchExecutionError(RuntimeError):
    pass


class ResearchCancelled(ResearchExecutionError):
    pass


def _clear_previous_attempt(db: Session, run) -> None:
    """Make retries idempotent by removing the prior attempt's outputs first."""
    for report in list(run.reports):
        if report.file_path:
            try:
                Path(report.file_path).unlink(missing_ok=True)
            except OSError:
                pass
        db.delete(report)
    for record in [*run.agent_executions, *run.sources, *run.verified_claims]:
        db.delete(record)
    db.flush()
    db.commit()


async def execute_research_run(
    db: Session,
    run_id: UUID,
    user_id: UUID,
    document_ids: list[UUID] | None = None,
    dataset_ids: list[UUID] | None = None,
    *,
    job_id: UUID | None = None,
    cancel_check: Callable[[], bool] | None = None,
    retry_attempt: bool = False,
):
    run = get_research_run_by_id(db, run_id, user_id)
    if run is None:
        raise LookupError("Research run not found or access denied.")
    for document_id in document_ids or []:
        document = get_document_by_id(db, document_id, user_id)
        if document is None or document.project_id != run.project_id:
            raise LookupError("One or more documents were not found or access denied.")
    for dataset_id in dataset_ids or []:
        dataset = get_document_by_id(db, dataset_id, user_id)
        if dataset is None or dataset.project_id != run.project_id or dataset.file_type not in {"csv", "xlsx"}:
            raise LookupError("One or more datasets were not found or access denied.")
    if cancel_check and cancel_check():
        raise ResearchCancelled("Research was cancelled before execution started.")
    if retry_attempt:
        _clear_previous_attempt(db, run)
        run = get_research_run_by_id(db, run_id, user_id)
        run.progress = 0
        run.current_step = None
        run.started_at = None
        run.completed_at = None
        run.error_message = None
        run.status = "queued"
        db.commit()
    started = start_research_run(db, run_id, user_id, allow_queued=job_id is not None)
    if not started:
        if started is False:
            raise RuntimeError("Research run has already started.")
        raise LookupError("Research run not found or access denied.")
    try:
        from app.workflows.research_workflow import ResearchWorkflow

        result = await ResearchWorkflow(
            db_session=db,
            user_id=user_id,
            research_run_id=run.id,
            cancel_checker=cancel_check,
        ).run(
            research_topic=run.research_topic,
            research_depth=run.research_depth,
            thread_id=str(run.id),
            document_ids=[str(value) for value in document_ids or []],
            dataset_ids=[str(value) for value in dataset_ids or []],
        )
        if result.get("cancelled") or (cancel_check and cancel_check()):
            update_research_run_status(db, run_id, user_id, "cancelled")
            raise ResearchCancelled("Research was cancelled.")

        for source in result.get("research_sources", []):
            if source.get("title"):
                create_research_source(db, run.id, user_id, ResearchSourceCreate(
                    title=source["title"], url=source.get("url") or None,
                    source_type=source.get("source_type", "unknown"),
                    authors=source.get("authors") or None, summary=source.get("summary") or None,
                ))
        if result.get("research_errors"):
            error_message = "; ".join(
                f"{provider}: {message}" for provider, message in result["research_errors"].items()
            )
            raise ResearchExecutionError(error_message)
        for claim in result.get("verified_claims", []):
            create_verified_claim(db, run.id, user_id, VerifiedClaimCreate(**claim))
        report_content = result.get("report_content")
        if report_content:
            from app.services.report_service import safe_report_path

            report = create_research_report(db, run.id, user_id, ResearchReportCreate(
                title=f"Research report: {run.research_topic}", content=report_content,
            ))
            try:
                structured = StructuredResearchReport.model_validate(result.get("structured_report", {}))
                output_path = safe_report_path(user_id, report.id, "pdf")
                export_report_document(structured, structured.title, "pdf", str(output_path))
                update_research_report(
                    db, report.id, user_id, generation_status="completed",
                    content=report_content, file_path=str(output_path),
                )
            except Exception:
                update_research_report(
                    db, report.id, user_id, generation_status="failed", content=report_content,
                )
                raise
        return update_research_run_status(db, run_id, user_id, "completed")
    except ResearchCancelled:
        raise
    except Exception as exc:
        update_research_run_status(db, run_id, user_id, "failed", error_message=str(exc))
        raise ResearchExecutionError("Research workflow execution failed.") from exc
