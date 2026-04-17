"""add bot users tables

Revision ID: e5f6a7b8c9d0
Revises: c3f1a2b4d5e6
Create Date: 2026-06-16 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'c3f1a2b4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns():
    return [
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('external_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('payment_required', sa.Boolean(), nullable=False),
        sa.Column('address_required', sa.Boolean(), nullable=False),
        sa.Column('wt_loader', sa.Boolean(), nullable=False),
        sa.Column('wt_handyman', sa.Boolean(), nullable=False),
        sa.Column('wt_specialist', sa.Boolean(), nullable=False),
        sa.Column('wt_unknown', sa.Boolean(), nullable=False),
        sa.Column('dur_short_task', sa.Boolean(), nullable=False),
        sa.Column('dur_full_shift', sa.Boolean(), nullable=False),
        sa.Column('dur_permanent', sa.Boolean(), nullable=False),
        sa.Column('dur_vahta', sa.Boolean(), nullable=False),
        sa.Column('dur_unknown', sa.Boolean(), nullable=False),
        sa.Column('wizard_step', sa.Integer(), nullable=True),
        sa.Column('wizard_draft', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
    ]


def upgrade() -> None:
    op.create_table('tg_bot_users', *_columns())
    op.create_table('vk_bot_users', *_columns())


def downgrade() -> None:
    op.drop_table('vk_bot_users')
    op.drop_table('tg_bot_users')
