import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VerifiedClaim(Base):
    __tablename__ = "verified_claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    research_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    claim_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    verification_status: Mapped[str] = mapped_column(
        String(50),
        default="insufficient_evidence",
        nullable=False
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    research_run = relationship(
        "ResearchRun",
        back_populates="verified_claims"
    )