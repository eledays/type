"""Require idempotency keys for practice actions.

Revision ID: b62d4e8f1a30
Revises: 4b8f1a2c6d90
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "b62d4e8f1a30"
down_revision = "4b8f1a2c6d90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE action SET request_id = 'legacy-' || id "
        "WHERE request_id IS NULL"
    ))
    with op.batch_alter_table("action") as batch_op:
        batch_op.alter_column(
            "request_id",
            existing_type=sa.String(length=64),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("action") as batch_op:
        batch_op.alter_column(
            "request_id",
            existing_type=sa.String(length=64),
            nullable=True,
        )
