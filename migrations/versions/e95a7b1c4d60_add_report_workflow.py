"""Add report workflow and remove unfinished notification settings.

Revision ID: e95a7b1c4d60
Revises: d84f6a0b3c50
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "e95a7b1c4d60"
down_revision = "d84f6a0b3c50"
branch_labels = None
depends_on = None

REPORT_STATUS_CHECK = (
    "status IN ('open', 'in_progress', 'resolved', 'rejected')"
)


def upgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.drop_column("day_results_time")
        batch_op.drop_column("day_results")
        batch_op.drop_column("notification_time")
        batch_op.drop_column("notification")

    with op.batch_alter_table("error_report") as batch_op:
        batch_op.add_column(sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="open",
        ))
        batch_op.add_column(sa.Column(
            "admin_note", sa.String(length=2000), nullable=True
        ))
        batch_op.add_column(sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ))
    op.execute(sa.text(
        "UPDATE error_report SET updated_at = created_at "
        "WHERE updated_at IS NULL"
    ))
    with op.batch_alter_table("error_report") as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            existing_server_default=sa.func.now(),
        )
        batch_op.create_check_constraint(
            "ck_error_report_status", REPORT_STATUS_CHECK
        )
        batch_op.create_index(
            "ix_error_report_status_created",
            ["status", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("error_report") as batch_op:
        batch_op.drop_index("ix_error_report_status_created")
        batch_op.drop_constraint("ck_error_report_status", type_="check")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("admin_note")
        batch_op.drop_column("status")

    with op.batch_alter_table("settings") as batch_op:
        batch_op.add_column(sa.Column(
            "notification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ))
        batch_op.add_column(sa.Column(
            "notification_time",
            sa.Time(),
            nullable=False,
            server_default="12:00:00",
        ))
        batch_op.add_column(sa.Column(
            "day_results",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ))
        batch_op.add_column(sa.Column(
            "day_results_time",
            sa.Time(),
            nullable=False,
            server_default="20:00:00",
        ))
