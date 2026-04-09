"""add vahta duration type

Revision ID: c3f1a2b4d5e6
Revises: a6f7b07f2c70
Create Date: 2026-06-16 03:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3f1a2b4d5e6'
down_revision: Union[str, Sequence[str], None] = 'a6f7b07f2c70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет значение VAHTA в enum-тип durationtype (длительность)."""
    op.execute("ALTER TYPE durationtype ADD VALUE IF NOT EXISTS 'VAHTA'")


def downgrade() -> None:
    """PostgreSQL не поддерживает удаление значения enum — откат не делаем."""
    pass
