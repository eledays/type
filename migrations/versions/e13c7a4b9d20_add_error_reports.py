"""add error reports

Revision ID: e13c7a4b9d20
Revises: c91e45a8f2d0
Create Date: 2026-08-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e13c7a4b9d20"
down_revision = "c91e45a8f2d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создаёт хранилище сообщений об ошибках."""
    op.create_table(
        "error_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("practice_item_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["practice_item_id"],
            ["practice_item.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_error_report_item_created",
        "error_report",
        ["practice_item_id", "created_at"],
    )
    op.create_index(
        "ix_error_report_user_created",
        "error_report",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Удаляет хранилище сообщений об ошибках."""
    op.drop_index(
        "ix_error_report_user_created", table_name="error_report"
    )
    op.drop_index(
        "ix_error_report_item_created", table_name="error_report"
    )
    op.drop_table("error_report")
