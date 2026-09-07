"""Add user lifecycle dates for analytics.

Revision ID: 7e2c4a9b1d30
Revises: 1a7d5e9c2b40
"""

from alembic import op
import sqlalchemy as sa


revision = "7e2c4a9b1d30"
down_revision = "1a7d5e9c2b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("identified_at", sa.DateTime(), nullable=True))

    op.execute(sa.text(
        'UPDATE "user" SET created_at = COALESCE('
        '(SELECT MIN(action.datetime) FROM action WHERE action.user_id = "user".id), '
        'CURRENT_TIMESTAMP)'
    ))
    op.execute(sa.text(
        'UPDATE "user" SET identified_at = created_at '
        'WHERE yandex_id IS NOT NULL OR telegram_id IS NOT NULL'
    ))

    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        )
        batch_op.create_index("ix_user_created_at", ["created_at"], unique=False)
        batch_op.create_index(
            "ix_user_identified_at", ["identified_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_identified_at")
        batch_op.drop_index("ix_user_created_at")
        batch_op.drop_column("identified_at")
        batch_op.drop_column("created_at")
