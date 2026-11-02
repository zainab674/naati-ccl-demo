"""course at a glance, lesson notes and duration

Revision ID: c4e8a1f7d352
Revises: a7d31c9e4b28
Create Date: 2026-11-02 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e8a1f7d352'
down_revision: Union[str, None] = 'a7d31c9e4b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('courses', sa.Column('at_a_glance_html', sa.Text(), server_default='', nullable=False))
    op.add_column('lessons', sa.Column('notes_html', sa.Text(), server_default='', nullable=False))
    op.add_column('lessons', sa.Column('duration_minutes', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('lessons', 'duration_minutes')
    op.drop_column('lessons', 'notes_html')
    op.drop_column('courses', 'at_a_glance_html')
