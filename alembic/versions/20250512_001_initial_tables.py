"""initial tables for Cryptozayka

Revision ID: 20250512_001
Revises:
Create Date: 2025-05-12 19:00 UTC
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20250512_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "batches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("status", sa.Text, nullable=False,
                  server_default="pending"),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("error", sa.Text),
    )

    op.create_table(
        "gpt_judgements",
        sa.Column("project", sa.Text, primary_key=True),
        sa.Column("verdict", sa.Text, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
    )

    op.create_table(
        "stats",
        sa.Column("metric", sa.Text, primary_key=True),
        sa.Column("value", sa.BigInteger, nullable=False,
                  server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("stats")
    op.drop_table("gpt_judgements")
    op.drop_table("batches")
