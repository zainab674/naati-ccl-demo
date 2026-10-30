"""teacher students and courses

Revision ID: 9b4e2d7c1f05
Revises: 5eaa73ae52f3
Create Date: 2026-10-30 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9b4e2d7c1f05'
down_revision: Union[str, None] = '5eaa73ae52f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('teacher_id', sa.Uuid(), nullable=True))
    op.add_column('users', sa.Column('join_code', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_users_teacher_id'), 'users', ['teacher_id'], unique=False)
    op.create_unique_constraint('uq_users_join_code', 'users', ['join_code'])
    op.create_foreign_key('fk_users_teacher_id_users', 'users', 'users', ['teacher_id'], ['id'])
    op.add_column('courses', sa.Column('owner_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_courses_owner_id'), 'courses', ['owner_id'], unique=False)
    op.create_foreign_key('fk_courses_owner_id_users', 'courses', 'users', ['owner_id'], ['id'])
    # Students a teacher already enrolled become that teacher's students.
    op.execute("""
        UPDATE users SET teacher_id = enrolled_by_id
        WHERE role = 'student' AND enrolled_by_id IN (SELECT id FROM users WHERE role = 'teacher')
    """)


def downgrade() -> None:
    op.drop_constraint('fk_courses_owner_id_users', 'courses', type_='foreignkey')
    op.drop_index(op.f('ix_courses_owner_id'), table_name='courses')
    op.drop_column('courses', 'owner_id')
    op.drop_constraint('fk_users_teacher_id_users', 'users', type_='foreignkey')
    op.drop_constraint('uq_users_join_code', 'users', type_='unique')
    op.drop_index(op.f('ix_users_teacher_id'), table_name='users')
    op.drop_column('users', 'join_code')
    op.drop_column('users', 'teacher_id')
