"""comment

Revision ID: cdbbe8148cee
Revises: 1e67f1c84c14
Create Date: 2025-05-13 12:51:04.920186

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cdbbe8148cee'
down_revision: Union[str, None] = '1e67f1c84c14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
