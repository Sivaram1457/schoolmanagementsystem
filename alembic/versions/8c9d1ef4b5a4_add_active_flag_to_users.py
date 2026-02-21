"""Add is_active flag to users

Revision ID: 8c9d1ef4b5a4
Revises: d6d1cc34a3b0
Create Date: 2026-02-21 01:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c9d1ef4b5a4'
down_revision: Union[str, Sequence[str], None] = 'd6d1cc34a3b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )
    op.create_index('ix_users_is_active', 'users', ['is_active'], unique=False)
    op.alter_column('users', 'is_active', server_default=None)


def downgrade() -> None:
    op.drop_index('ix_users_is_active', table_name='users')
    op.drop_column('users', 'is_active')
