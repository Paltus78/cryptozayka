"""add status & result columns to batches

Revision ID: 1e67f1c84c14
Revises: 20250512_001
Create Date: 2025-05-14 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "1e67f1c84c14"
down_revision = "20250512_001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("batches") as batch:
        batch.add_column(
            sa.Column(
                "status",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'new'"),
            )
        )
        batch.add_column(sa.Column("result", postgresql.JSONB(), nullable=True))

    # убрать server_default, чтобы далее INSERT явно передавал либо default
    op.alter_column("batches", "status", server_default=None)


def downgrade():
    with op.batch_alter_table("batches") as batch:
        batch.drop_column("result")
        batch.drop_column("status")
