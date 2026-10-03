"""household settings (correggi_orientamento) + persistenza foto titolo

Revision ID: 9648796d9e44
Revises: a405db851e79
Create Date: 2026-09-22 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9648796d9e44'
down_revision: Union[str, None] = 'a405db851e79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'households',
        sa.Column('correggi_orientamento', sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column('batch_items', sa.Column('foto_titolo_key', sa.String(length=255), nullable=True))
    op.add_column('products', sa.Column('foto_titolo_key', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'foto_titolo_key')
    op.drop_column('batch_items', 'foto_titolo_key')
    op.drop_column('households', 'correggi_orientamento')
