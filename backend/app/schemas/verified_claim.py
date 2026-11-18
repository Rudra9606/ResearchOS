from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


VerificationStatus = Literal[
    "supported",
    "contradicted",
    "insufficient_evidence"
]


# Verified claim response
class VerifiedClaimResponse(BaseModel):
    id: UUID
    research_run_id: UUID
    claim_text: str
    verification_status: VerificationStatus
    explanation: str | None = None
    confidence_score: float | None = Field(
        default=None,
        ge=0,
        le=1
    )
    evidence: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Create verified claim
class VerifiedClaimCreate(BaseModel):
    claim_text: str = Field(..., min_length=5)
    verification_status: VerificationStatus = "insufficient_evidence"
    explanation: str | None = None
    confidence_score: float | None = Field(
        default=None,
        ge=0,
        le=1
    )
    evidence: str | None = None


class VerifiedClaimUpdate(BaseModel):
    verification_status: VerificationStatus
    explanation: str | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    evidence: str | None = None


# Verified claims list
class VerifiedClaimListResponse(BaseModel):
    total: int
    claims: list[VerifiedClaimResponse]