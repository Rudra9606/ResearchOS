"""Add durable background job records.

Revision ID: 6f2bd4a8c190
Revises: 4a8f3c1d2e90
"""

from alembic import op
import sqlalchemy as sa


revision = "6f2bd4a8c190"
down_revision = "4a8f3c1d2e90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("research_run_id", sa.UUID(), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("job_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(job_type = 'research' AND research_run_id IS NOT NULL AND document_id IS NULL) "
            "OR (job_type = 'document' AND document_id IS NOT NULL AND research_run_id IS NULL)",
            name="ck_research_jobs_target",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("research_run_id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index("ix_research_jobs_available", "research_jobs", ["status", "available_at"])
    op.create_index("ix_research_jobs_user", "research_jobs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_research_jobs_user", table_name="research_jobs")
    op.drop_index("ix_research_jobs_available", table_name="research_jobs")
    op.drop_table("research_jobs")
