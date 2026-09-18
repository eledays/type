"""Track user activity for anonymous profile retention.

Revision ID: c73e5f9a2b40
Revises: b62d4e8f1a30
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "c73e5f9a2b40"
down_revision = "b62d4e8f1a30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ))
    op.execute(sa.text(
        'UPDATE "user" SET last_seen_at = created_at '
        "WHERE last_seen_at IS NULL"
    ))
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column(
            "last_seen_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        batch_op.create_index(
            "ix_user_last_seen_at", ["last_seen_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_last_seen_at")
        batch_op.drop_column("last_seen_at")
