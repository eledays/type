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
    op.execute("UPDATE settings SET strike = 1 WHERE strike IS NULL")
    op.execute("UPDATE settings SET notification = 0 WHERE notification IS NULL")
    op.execute("UPDATE word SET mistake = 0 WHERE mistake IS NULL")

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
