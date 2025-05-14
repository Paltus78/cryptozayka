"""next change

Revision ID: 1e67f1c84c14
Revises: 20250512_001
Create Date: 2025-05-13 12:45:10.201315

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e67f1c84c14'
down_revision: Union[str, None] = '20250512_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
