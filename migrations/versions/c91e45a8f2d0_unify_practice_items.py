"""unify practice items

Revision ID: c91e45a8f2d0
Revises: b74c19e2f6a1
Create Date: 2026-08-19 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c91e45a8f2d0"
down_revision = "b74c19e2f6a1"
branch_labels = None
depends_on = None


def _reset_postgresql_sequence(connection, table_name: str) -> None:
    """Синхронизирует sequence после вставки явных идентификаторов.

    :param connection: Активное соединение Alembic с базой данных.
    :param table_name: Имя таблицы с автоинкрементным полем ``id``.
    :return: ``None``.
    :raises ValueError: Если передано имя таблицы вне миграции.
    """
    if connection.dialect.name != "postgresql":
        return
    allowed_tables = {"practice_item", "word", "sentence"}
    if table_name not in allowed_tables:
        raise ValueError("Unexpected sequence table")
    connection.execute(sa.text(
        "SELECT setval("
        "pg_get_serial_sequence(:table_name, 'id'), "
        f"COALESCE((SELECT MAX(id) FROM {table_name}), 1), "
        f"EXISTS(SELECT 1 FROM {table_name})"
        ")"
    ), {"table_name": table_name})


def upgrade() -> None:
    """Объединяет упражнения общим идентификатором и переносит действия.

    :return: ``None``.
    :raises RuntimeError: Если старое упражнение не содержит вариантов ответа.
    """
    connection = op.get_bind()
    old_metadata = sa.MetaData()
    old_word = sa.Table("word", old_metadata, autoload_with=connection)
    old_sentence = sa.Table(
        "sentence", old_metadata, autoload_with=connection
    )
    words = connection.execute(sa.select(old_word)).mappings().all()
    sentences = connection.execute(sa.select(old_sentence)).mappings().all()
    invalid_word_ids = [row["id"] for row in words if not row["answers"]]
    if invalid_word_ids:
        raise RuntimeError(
            "Cannot migrate words without answers: "
            + ", ".join(map(str, invalid_word_ids))
        )
    max_word_id = max((row["id"] for row in words), default=0)
    sentence_item_ids = {
        row["id"]: max_word_id + row["id"] for row in sentences
    }

    op.create_table(
        "practice_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("task_number", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("explanation", sa.String(length=2048), nullable=True),
        sa.CheckConstraint(
            "type IN ('spelling', 'paronym')",
            name="ck_practice_item_type",
        ),
        sa.CheckConstraint(
            "type != 'spelling' OR category_id IS NOT NULL",
            name="ck_spelling_category_required",
        ),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_practice_item_type", "practice_item", ["type"]
    )
    op.create_index(
        "ix_practice_item_task_number", "practice_item", ["task_number"]
    )
    op.create_index(
        "ix_practice_item_category_id", "practice_item", ["category_id"]
    )
    op.create_table(
        "spelling_exercise",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("word", sa.String(length=128), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("correct_answer", sa.String(length=128), nullable=False),
        sa.CheckConstraint(
            "correct_answer != ''",
            name="ck_spelling_correct_answer_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["id"], ["practice_item.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("word"),
    )
    op.create_table(
        "paronym_exercise",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sentence", sa.String(), nullable=False),
        sa.Column("paronym_id", sa.Integer(), nullable=False),
        sa.Column("word_tags", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id"], ["practice_item.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["paronym_id"], ["paronym.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sentence"),
    )
    op.create_index(
        "ix_paronym_exercise_paronym_id",
        "paronym_exercise",
        ["paronym_id"],
    )

    metadata = sa.MetaData()
    practice_item = sa.Table(
        "practice_item", metadata, autoload_with=connection
    )
    spelling = sa.Table(
        "spelling_exercise", metadata, autoload_with=connection
    )
    paronym_exercise = sa.Table(
        "paronym_exercise", metadata, autoload_with=connection
    )

    if words:
        connection.execute(practice_item.insert(), [
            {
                "id": row["id"],
                "type": "spelling",
                "task_number": row["task_number"],
                "category_id": row["category_id"],
                "explanation": row["explanation"],
            }
            for row in words
        ])
        connection.execute(spelling.insert(), [
            {
                "id": row["id"],
                "word": row["word"],
                "answers": row["answers"],
                "correct_answer": row["answers"][0],
            }
            for row in words
        ])
    if sentences:
        connection.execute(practice_item.insert(), [
            {
                "id": sentence_item_ids[row["id"]],
                "type": "paronym",
                "task_number": 5,
                "category_id": None,
                "explanation": None,
            }
            for row in sentences
        ])
        connection.execute(paronym_exercise.insert(), [
            {
                "id": sentence_item_ids[row["id"]],
                "sentence": row["sentence"],
                "paronym_id": row["word_id"],
                "word_tags": row["word_tags"],
            }
            for row in sentences
        ])
    _reset_postgresql_sequence(connection, "practice_item")

    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            "practice_item_id", sa.Integer(), nullable=True
        ))

    action = sa.Table("action", sa.MetaData(), autoload_with=connection)
    actions = connection.execute(sa.select(
        action.c.id, action.c.word_id, action.c.sentence_id
    )).mappings().all()
    for row in actions:
        item_id = row["word_id"]
        if item_id is None and row["sentence_id"] is not None:
            item_id = sentence_item_ids.get(row["sentence_id"])
        if item_id is None:
            connection.execute(action.delete().where(action.c.id == row["id"]))
        else:
            connection.execute(
                action.update()
                .where(action.c.id == row["id"])
                .values(practice_item_id=item_id)
            )

    op.drop_index("ix_action_user_word", table_name="action")
    op.drop_index("ix_action_user_sentence", table_name="action")
    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.drop_constraint("ck_action_single_note", type_="check")
        batch_op.drop_constraint(
            "fk_action_word_id_word", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_action_sentence_id_sentence", type_="foreignkey"
        )
        batch_op.drop_column("word_id")
        batch_op.drop_column("sentence_id")
        batch_op.alter_column(
            "practice_item_id", existing_type=sa.Integer(), nullable=False
        )
        batch_op.create_foreign_key(
            "fk_action_practice_item_id_practice_item",
            "practice_item",
            ["practice_item_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(
        "ix_action_user_item",
        "action",
        ["user_id", "practice_item_id"],
    )
    op.drop_table("sentence")
    op.drop_table("word")


def downgrade() -> None:
    """Восстанавливает прежние таблицы упражнений и ссылки действий.

    :return: ``None``.
    """
    op.create_table(
        "word",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("word", sa.String(length=128), nullable=False),
        sa.Column("explanation", sa.String(length=2048), nullable=True),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("task_number", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("mistake", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("word"),
    )
    op.create_index("ix_word_task_number", "word", ["task_number"])
    op.create_index("ix_word_category_id", "word", ["category_id"])
    op.create_table(
        "sentence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sentence", sa.String(), nullable=False),
        sa.Column("word_id", sa.Integer(), nullable=False),
        sa.Column("word_tags", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["word_id"], ["paronym.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sentence"),
    )

    connection = op.get_bind()
    metadata = sa.MetaData()
    practice_item = sa.Table(
        "practice_item", metadata, autoload_with=connection
    )
    spelling = sa.Table(
        "spelling_exercise", metadata, autoload_with=connection
    )
    paronym_exercise = sa.Table(
        "paronym_exercise", metadata, autoload_with=connection
    )
    old_word = sa.Table("word", metadata, autoload_with=connection)
    old_sentence = sa.Table("sentence", metadata, autoload_with=connection)

    words = connection.execute(
        sa.select(practice_item, spelling).join(
            spelling, practice_item.c.id == spelling.c.id
        )
    ).mappings().all()
    sentences = connection.execute(
        sa.select(practice_item, paronym_exercise).join(
            paronym_exercise,
            practice_item.c.id == paronym_exercise.c.id,
        )
    ).mappings().all()
    if words:
        connection.execute(old_word.insert(), [
            {
                "id": row["id"],
                "word": row["word"],
                "explanation": row["explanation"],
                "answers": row["answers"],
                "task_number": row["task_number"],
                "category_id": row["category_id"],
                "mistake": False,
            }
            for row in words
        ])
    if sentences:
        connection.execute(old_sentence.insert(), [
            {
                "id": row["id"],
                "sentence": row["sentence"],
                "word_id": row["paronym_id"],
                "word_tags": row["word_tags"],
            }
            for row in sentences
        ])
    _reset_postgresql_sequence(connection, "word")
    _reset_postgresql_sequence(connection, "sentence")

    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.add_column(sa.Column("word_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column(
            "sentence_id", sa.Integer(), nullable=True
        ))
    action = sa.Table("action", sa.MetaData(), autoload_with=connection)
    item_types = dict(connection.execute(sa.select(
        practice_item.c.id, practice_item.c.type
    )).all())
    for row in connection.execute(sa.select(
        action.c.id, action.c.practice_item_id
    )).mappings():
        target = (
            "word_id"
            if item_types[row["practice_item_id"]] == "spelling"
            else "sentence_id"
        )
        connection.execute(
            action.update()
            .where(action.c.id == row["id"])
            .values({target: row["practice_item_id"]})
        )

    op.drop_index("ix_action_user_item", table_name="action")
    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_action_practice_item_id_practice_item", type_="foreignkey"
        )
        batch_op.drop_column("practice_item_id")
        batch_op.create_foreign_key(
            "fk_action_word_id_word",
            "word",
            ["word_id"],
            ["id"],
            ondelete="SET NULL",
        )
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
        "ix_action_user_word", "action", ["user_id", "word_id"]
    )
    op.create_index(
        "ix_action_user_sentence", "action", ["user_id", "sentence_id"]
    )
    op.drop_index(
        "ix_paronym_exercise_paronym_id", table_name="paronym_exercise"
    )
    op.drop_table("paronym_exercise")
    op.drop_table("spelling_exercise")
    op.drop_index("ix_practice_item_category_id", table_name="practice_item")
    op.drop_index("ix_practice_item_task_number", table_name="practice_item")
    op.drop_index("ix_practice_item_type", table_name="practice_item")
    op.drop_table("practice_item")
