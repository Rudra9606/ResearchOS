from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.verified_claim import VerifiedClaim
from app.models.research_run import ResearchRun
from app.models.project import ResearchProject
from app.schemas.verified_claim import (
    VerifiedClaimCreate,
    VerificationStatus
)


def create_verified_claim(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    claim_data: VerifiedClaimCreate
) -> VerifiedClaim:
    """Create a verified claim."""

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

    new_claim = VerifiedClaim(
        research_run_id=research_run_id,
        claim_text=claim_data.claim_text,
        verification_status=claim_data.verification_status,
        explanation=claim_data.explanation,
        confidence_score=claim_data.confidence_score,
        evidence=claim_data.evidence
    )

    try:
        db.add(new_claim)
        db.commit()
        db.refresh(new_claim)
        return new_claim
    except Exception:
        db.rollback()
        raise


def get_verified_claim_by_id(
    db: Session,
    claim_id: UUID,
    user_id: UUID
):
    """Retrieve a verified claim."""

    statement = (
        select(VerifiedClaim)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            VerifiedClaim.id == claim_id,
            ResearchProject.user_id == user_id
        )
    )

    return db.scalar(statement)


def get_research_run_claims(
    db: Session,
    research_run_id: UUID,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
):
    """Retrieve all verified claims for a research run."""

    statement = (
        select(VerifiedClaim)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            VerifiedClaim.research_run_id == research_run_id,
            ResearchProject.user_id == user_id
        )
        .order_by(VerifiedClaim.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def count_research_run_claims(db: Session, research_run_id: UUID, user_id: UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(VerifiedClaim)
        .join(ResearchRun)
        .join(ResearchProject)
        .where(
            VerifiedClaim.research_run_id == research_run_id,
            ResearchProject.user_id == user_id,
        )
    ) or 0


def update_verified_claim(
    db: Session,
    claim_id: UUID,
    user_id: UUID,
    verification_status: VerificationStatus,
    explanation: str | None = None,
    confidence_score: float | None = None,
    evidence: str | None = None
):
    """Update a claim verification result."""

    if confidence_score is not None and not 0 <= confidence_score <= 1:
        raise ValueError("Confidence score must be between 0 and 1.")

    claim = get_verified_claim_by_id(db, claim_id, user_id)

    if claim is None:
        return None

    try:
        claim.verification_status = verification_status
        claim.explanation = explanation
        claim.confidence_score = confidence_score
        claim.evidence = evidence

        db.commit()
        db.refresh(claim)
        return claim

    except Exception:
        db.rollback()
        raise


def delete_verified_claim(
    db: Session,
    claim_id: UUID,
    user_id: UUID
) -> bool:
    """Delete a verified claim."""

    claim = get_verified_claim_by_id(db, claim_id, user_id)

    if claim is None:
        return False

    try:
        db.delete(claim)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
