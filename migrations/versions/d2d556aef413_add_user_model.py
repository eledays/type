"""add user model

Revision ID: d2d556aef413
Revises: 5da69ffed3ee
Create Date: 2026-08-17 22:32:40.212025

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2d556aef413'
down_revision = '5da69ffed3ee'
branch_labels = None
depends_on = None


def upgrade():
    """Добавляет модель пользователя и связывает с ней данные.

    :return: ``None``.
    """
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=True),
        sa.Column(
            'is_admin',
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id'),
    )

    # Preserve every legacy identity that already has settings or actions.
    op.execute(
        'INSERT INTO "user" (telegram_id) '
        'SELECT user_id FROM settings '
        'UNION SELECT user_id FROM action'
    )
    op.execute(
        'UPDATE action SET user_id = ('
        'SELECT id FROM "user" WHERE "user".telegram_id = action.user_id'
        ')'
    )
    op.execute(
        'UPDATE settings SET user_id = ('
        'SELECT id FROM "user" WHERE "user".telegram_id = settings.user_id'
        ')'
    )
    op.execute(
        "INSERT INTO settings ("
        "user_id, strike, notification, notification_time, "
        "day_results, day_results_time"
        ") "
        "SELECT id, 1, 0, '12:00:00', 1, '20:00:00' "
        'FROM "user" '
        "WHERE NOT EXISTS ("
        "SELECT 1 FROM settings WHERE settings.user_id = \"user\".id"
        ")"
    )

    with op.batch_alter_table('action', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_action_user_id_user',
            'user',
            ['user_id'],
            ['id'],
            ondelete='CASCADE',
        )

    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_settings_user_id_user',
            'user',
            ['user_id'],
            ['id'],
            ondelete='CASCADE',
        )


def downgrade():
    """Возвращает схему к состоянию без отдельной модели пользователя.

    :return: ``None``.
    """
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_settings_user_id_user', type_='foreignkey'
        )

    with op.batch_alter_table('action', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_action_user_id_user', type_='foreignkey'
        )

    # Restore the former external IDs before removing the user table.
    op.execute(
        'UPDATE action SET user_id = ('
        'SELECT COALESCE(telegram_id, id) FROM "user" '
        'WHERE "user".id = action.user_id'
        ')'
    )
    op.execute(
        'UPDATE settings SET user_id = ('
        'SELECT COALESCE(telegram_id, id) FROM "user" '
        'WHERE "user".id = settings.user_id'
        ')'
    )

    op.drop_table('user')
