"""Add action indexes used by analytics.

Revision ID: 9b3d1f6a8c20
Revises: 7e2c4a9b1d30
"""

from alembic import op


revision = "9b3d1f6a8c20"
down_revision = "7e2c4a9b1d30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_action_datetime", "action", ["datetime"])
    op.create_index(
        "ix_action_item_datetime",
        "action",
        ["practice_item_id", "datetime"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_item_datetime", table_name="action")
    op.drop_index("ix_action_datetime", table_name="action")
