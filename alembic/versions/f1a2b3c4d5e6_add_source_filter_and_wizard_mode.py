"""add source filter and wizard mode

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-06-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = ("tg_bot_users", "vk_bot_users")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column('src_vk', sa.Boolean(), nullable=False, server_default=sa.true()))
        op.add_column(table, sa.Column('src_tg', sa.Boolean(), nullable=False, server_default=sa.true()))
        op.add_column(table, sa.Column('wizard_mode', sa.Text(), nullable=True))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, 'wizard_mode')
        op.drop_column(table, 'src_tg')
        op.drop_column(table, 'src_vk')
