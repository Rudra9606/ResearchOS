"""Constrain document chunk embeddings to the configured model dimension.

Revision ID: 4a8f3c1d2e90
Revises: 1c2a2c96111c
"""

from alembic import op


revision = "4a8f3c1d2e90"
down_revision = "1c2a2c96111c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE vector(384)
        USING CASE
            WHEN embedding IS NULL THEN NULL
            WHEN vector_dims(embedding) = 384 THEN embedding
            ELSE NULL
        END
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_cosine
        ON document_chunks USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_cosine")
    op.execute(
        "ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector USING embedding"
    )
