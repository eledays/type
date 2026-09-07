"""Store timestamps as UTC-aware values.

Revision ID: c4e82a7d913f
Revises: 9b3d1f6a8c20
"""

from alembic import op
import sqlalchemy as sa


revision = "c4e82a7d913f"
down_revision = "9b3d1f6a8c20"
branch_labels = None
depends_on = None


COLUMNS = (
    ("action", "datetime", False),
    ("user", "created_at", False),
    ("user", "identified_at", True),
    ("error_report", "created_at", False),
    ("practice_progress", "latest_action_at", False),
    ("user_practice_stats", "latest_action_at", True),
)


def _alter(timezone: bool) -> None:
    bind = op.get_bind()
    target_type = sa.DateTime(timezone=timezone)
    existing_type = sa.DateTime(timezone=not timezone)
    for table, column, nullable in COLUMNS:
        if bind.dialect.name == "postgresql":
            using = (
                f'"{column}" AT TIME ZONE \'UTC\''
                if timezone
                else f'"{column}" AT TIME ZONE \'UTC\''
            )
            op.alter_column(
                table,
                column,
                existing_type=existing_type,
                type_=target_type,
                existing_nullable=nullable,
                postgresql_using=using,
            )
        else:
            with op.batch_alter_table(table) as batch_op:
                batch_op.alter_column(
                    column,
                    existing_type=existing_type,
                    type_=target_type,
                    existing_nullable=nullable,
                )


def upgrade() -> None:
    _alter(True)


def downgrade() -> None:
    _alter(False)
