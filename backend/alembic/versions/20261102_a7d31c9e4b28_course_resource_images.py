"""course and resource images

Revision ID: a7d31c9e4b28
Revises: 9b4e2d7c1f05
Create Date: 2026-11-02 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d31c9e4b28'
down_revision: Union[str, None] = '9b4e2d7c1f05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('courses', sa.Column('image_key', sa.String(length=400), server_default='', nullable=False))
    op.add_column('resources', sa.Column('image_key', sa.String(length=400), server_default='', nullable=False))


def downgrade() -> None:
    op.drop_column('resources', 'image_key')
    op.drop_column('courses', 'image_key')
