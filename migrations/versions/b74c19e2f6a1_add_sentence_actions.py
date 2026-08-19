"""add sentence actions

Revision ID: b74c19e2f6a1
Revises: a31f72c8d4b0
Create Date: 2026-08-19 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b74c19e2f6a1"
down_revision = "a31f72c8d4b0"
branch_labels = None
depends_on = None


def upgrade():
    """Добавляет связь действий с предложениями и индекс для истории.

    :return: ``None``.
    """
    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sentence_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_action_sentence_id_sentence",
            "sentence",
            ["sentence_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_action_single_note",
            "word_id IS NULL OR sentence_id IS NULL",
        )
    op.create_index(
        "ix_action_user_sentence",
        "action",
        ["user_id", "sentence_id"],
    )


def downgrade():
    """Удаляет индекс и связь действий с предложениями.

    :return: ``None``.
    """
    op.drop_index("ix_action_user_sentence", table_name="action")
    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_action_single_note",
            type_="check",
        )
        batch_op.drop_constraint(
            "fk_action_sentence_id_sentence",
            type_="foreignkey",
        )
        batch_op.drop_column("sentence_id")
