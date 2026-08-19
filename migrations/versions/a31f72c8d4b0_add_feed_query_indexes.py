"""add feed query indexes

Revision ID: a31f72c8d4b0
Revises: 8c12f4a7d901
Create Date: 2026-08-19 00:00:00.000000

"""
from alembic import op


revision = "a31f72c8d4b0"
down_revision = "8c12f4a7d901"
branch_labels = None
depends_on = None


def upgrade():
    """Добавляет индексы, используемые выборкой персональной ленты.

    :return: ``None``.
    """
    op.create_index("ix_action_user_word", "action", ["user_id", "word_id"])
    op.create_index(
        "ix_action_user_datetime", "action", ["user_id", "datetime"]
    )
    op.create_index(
        "ix_action_user_action", "action", ["user_id", "action"]
    )
    op.create_index("ix_word_task_number", "word", ["task_number"])
    op.create_index("ix_word_category_id", "word", ["category_id"])


def downgrade():
    """Удаляет индексы выборки персональной ленты.

    :return: ``None``.
    """
    op.drop_index("ix_word_category_id", table_name="word")
    op.drop_index("ix_word_task_number", table_name="word")
    op.drop_index("ix_action_user_action", table_name="action")
    op.drop_index("ix_action_user_datetime", table_name="action")
    op.drop_index("ix_action_user_word", table_name="action")
