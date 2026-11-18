import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    research_topic: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    research_depth: Mapped[str] = mapped_column(
        String(30),
        default="standard",
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False
    )

    progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    current_step: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    project = relationship(
        "ResearchProject",
        back_populates="research_runs"
    )

    agent_executions = relationship(
    "AgentExecution",
    back_populates="research_run",
    cascade="all, delete-orphan"
)
    sources = relationship(
    "ResearchSource",
    back_populates="research_run",
    cascade="all, delete-orphan"
)
    verified_claims = relationship(
    "VerifiedClaim",
    back_populates="research_run",
    cascade="all, delete-orphan"
)
    reports = relationship(
    "ResearchReport",
    back_populates="research_run",
    cascade="all, delete-orphan"
)