"""stored objects (files in the database for STORAGE_BACKEND=db)

Revision ID: e7c1a9d24b6f
Revises: b5d032e78873
"""
import sqlalchemy as sa
from alembic import op

revision = "e7c1a9d24b6f"
down_revision = "b5d032e78873"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stored_objects",
        sa.Column("key", sa.String(500), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_stored_objects"),
    )


def downgrade() -> None:
    op.drop_table("stored_objects")
