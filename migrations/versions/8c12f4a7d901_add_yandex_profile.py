"""add Yandex OAuth profile fields

Revision ID: 8c12f4a7d901
Revises: d2d556aef413
Create Date: 2026-08-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "8c12f4a7d901"
down_revision = "d2d556aef413"
branch_labels = None
depends_on = None


def upgrade():
    """Добавляет поля профиля и авторизации Яндекса.

    :return: ``None``.
    """
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("yandex_id", sa.String(64)))
        batch_op.add_column(sa.Column("yandex_login", sa.String(255)))
        batch_op.add_column(sa.Column("first_name", sa.String(255)))
        batch_op.add_column(sa.Column("last_name", sa.String(255)))
        batch_op.add_column(sa.Column("avatar_url", sa.String(2048)))
        batch_op.create_index(
            "ix_user_yandex_id", ["yandex_id"], unique=True
        )


def downgrade():
    """Удаляет поля профиля и авторизации Яндекса.

    :return: ``None``.
    """
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_index("ix_user_yandex_id")
        batch_op.drop_column("avatar_url")
        batch_op.drop_column("last_name")
        batch_op.drop_column("first_name")
        batch_op.drop_column("yandex_login")
        batch_op.drop_column("yandex_id")
