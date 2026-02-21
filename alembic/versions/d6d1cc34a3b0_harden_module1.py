"""Harden Module 1: add reset and verification tokens

Revision ID: d6d1cc34a3b0
Revises: 7126fbb8a9d5
Create Date: 2026-02-21 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6d1cc34a3b0'
down_revision: Union[str, Sequence[str], None] = '7126fbb8a9d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_email_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )

    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_password_reset_hash'),
    )
    op.create_index('ix_password_reset_user_id', 'password_reset_tokens', ['user_id'], unique=False)
    op.create_index('ix_password_reset_expires', 'password_reset_tokens', ['expires_at'], unique=False)

    op.create_table(
        'email_verification_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_email_verification_hash'),
    )
    op.create_index('ix_email_verification_user_id', 'email_verification_tokens', ['user_id'], unique=False)
    op.create_index('ix_email_verification_expires', 'email_verification_tokens', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_email_verification_expires', table_name='email_verification_tokens')
    op.drop_index('ix_email_verification_user_id', table_name='email_verification_tokens')
    op.drop_table('email_verification_tokens')

    op.drop_index('ix_password_reset_expires', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_user_id', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')

    op.drop_column('users', 'is_email_verified')
