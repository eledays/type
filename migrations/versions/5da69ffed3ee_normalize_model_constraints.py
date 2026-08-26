"""normalize model constraints

Revision ID: 5da69ffed3ee
Revises: 5f01b47acedc
Create Date: 2026-08-16 22:37:21.383684

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5da69ffed3ee'
down_revision = '5f01b47acedc'
branch_labels = None
depends_on = None


def upgrade():
    """Нормализует старые данные и усиливает ограничения моделей.

    :return: ``None``.
    """
    # Normalize legacy rows before applying stricter constraints.
    op.execute(
        "UPDATE action SET datetime = CURRENT_TIMESTAMP WHERE datetime IS NULL"
    )
    op.execute(
        "UPDATE action SET word_id = NULL "
        "WHERE word_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM word WHERE word.id = action.word_id)"
    )
    op.execute("UPDATE sentence SET word_tags = '' WHERE word_tags IS NULL")
    settings = sa.table(
        "settings",
        sa.column("strike", sa.Boolean()),
        sa.column("notification", sa.Boolean()),
    )
    word = sa.table("word", sa.column("mistake", sa.Boolean()))
    op.execute(
        settings.update()
        .where(settings.c.strike.is_(None))
        .values(strike=True)
    )
    op.execute(
        settings.update()
        .where(settings.c.notification.is_(None))
        .values(notification=False)
    )
    op.execute(
        word.update()
        .where(word.c.mistake.is_(None))
        .values(mistake=False)
    )

    with op.batch_alter_table('action', schema=None) as batch_op:
        batch_op.alter_column('datetime',
               existing_type=sa.DATETIME(),
               nullable=False)
        batch_op.create_foreign_key(
            'fk_action_word_id_word',
            'word',
            ['word_id'],
            ['id'],
            ondelete='SET NULL',
        )

    with op.batch_alter_table('sentence', schema=None) as batch_op:
        batch_op.alter_column('word_tags',
               existing_type=sa.VARCHAR(),
               nullable=False)

    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.alter_column('strike',
               existing_type=sa.BOOLEAN(),
               nullable=False)
        batch_op.alter_column('notification',
               existing_type=sa.BOOLEAN(),
               nullable=False)

    with op.batch_alter_table('word', schema=None) as batch_op:
        batch_op.alter_column('mistake',
               existing_type=sa.BOOLEAN(),
               nullable=False)


def downgrade():
    """Возвращает прежнюю обязательность полей и внешних ключей.

    :return: ``None``.
    """
    with op.batch_alter_table('word', schema=None) as batch_op:
        batch_op.alter_column('mistake',
               existing_type=sa.BOOLEAN(),
               nullable=True)

    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.alter_column('notification',
               existing_type=sa.BOOLEAN(),
               nullable=True)
        batch_op.alter_column('strike',
               existing_type=sa.BOOLEAN(),
               nullable=True)

    with op.batch_alter_table('sentence', schema=None) as batch_op:
        batch_op.alter_column('word_tags',
               existing_type=sa.VARCHAR(),
               nullable=True)

    with op.batch_alter_table('action', schema=None) as batch_op:
        batch_op.drop_constraint('fk_action_word_id_word', type_='foreignkey')
        batch_op.alter_column('datetime',
               existing_type=sa.DATETIME(),
               nullable=True)
