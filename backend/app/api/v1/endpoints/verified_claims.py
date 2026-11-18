from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.crud.verified_claim import (
    delete_verified_claim,
    get_research_run_claims,
    count_research_run_claims,
    get_verified_claim_by_id,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.verified_claim import (
    VerifiedClaimListResponse,
    VerifiedClaimResponse,
)

router = APIRouter()


@router.get("/", response_model=VerifiedClaimListResponse)
def list_claims(
    research_run_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claims = get_research_run_claims(db, research_run_id, current_user.id, skip, limit)
    return VerifiedClaimListResponse(
        total=count_research_run_claims(db, research_run_id, current_user.id),
        claims=claims,
    )


@router.get("/{claim_id}", response_model=VerifiedClaimResponse)
def get_claim(
    claim_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = get_verified_claim_by_id(db, claim_id, current_user.id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Verified claim not found or access denied.")
    return claim


@router.delete("/{claim_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_claim(
    claim_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not delete_verified_claim(db, claim_id, current_user.id):
        raise HTTPException(status_code=404, detail="Verified claim not found or access denied.")
