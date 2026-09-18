"""add idempotency keys to practice actions

Revision ID: 4b8f1a2c6d90
Revises: 2d7f9a1c5e40
"""

from alembic import op
import sqlalchemy as sa


revision = "4b8f1a2c6d90"
down_revision = "2d7f9a1c5e40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.add_column(sa.Column("request_id", sa.String(64), nullable=True))
        batch_op.create_unique_constraint(
            "uq_action_user_request", ["user_id", "request_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.drop_constraint("uq_action_user_request", type_="unique")
        batch_op.drop_column("request_id")
