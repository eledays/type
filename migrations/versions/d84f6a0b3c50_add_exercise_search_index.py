"""Add normalized exercise search text and PostgreSQL trigram index.

Revision ID: d84f6a0b3c50
Revises: c73e5f9a2b40
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "d84f6a0b3c50"
down_revision = "c73e5f9a2b40"
branch_labels = None
depends_on = None


def _normalize(value: str) -> str:
    normalized = value.casefold().replace("ё", "е")
    return "".join(
        character
        for character in normalized
        if character.isalnum() or character == "_"
    )


def upgrade() -> None:
    with op.batch_alter_table("practice_item") as batch_op:
        batch_op.add_column(sa.Column("search_text", sa.Text(), nullable=True))

    connection = op.get_bind()
    item = sa.table(
        "practice_item",
        sa.column("id", sa.Integer()),
        sa.column("search_text", sa.Text()),
    )
    spelling = sa.table(
        "spelling_exercise",
        sa.column("id", sa.Integer()),
        sa.column("word", sa.Text()),
    )
    paronym = sa.table(
        "paronym_exercise",
        sa.column("id", sa.Integer()),
        sa.column("sentence", sa.Text()),
    )
    rows = connection.execute(
        sa.select(
            item.c.id,
            sa.func.coalesce(spelling.c.word, paronym.c.sentence, ""),
        )
        .select_from(
            item
            .outerjoin(spelling, spelling.c.id == item.c.id)
            .outerjoin(paronym, paronym.c.id == item.c.id)
        )
    )
    updates = [
        {
            "item_id": item_id,
            "normalized_search_text": _normalize(prompt),
        }
        for item_id, prompt in rows
    ]
    if updates:
        connection.execute(
            item.update()
            .where(item.c.id == sa.bindparam("item_id"))
            .values(search_text=sa.bindparam("normalized_search_text")),
            updates,
        )
    with op.batch_alter_table("practice_item") as batch_op:
        batch_op.alter_column(
            "search_text",
            existing_type=sa.Text(),
            nullable=False,
            server_default="",
        )

    if connection.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX ix_practice_item_search_trgm "
            "ON practice_item USING gin (search_text gin_trgm_ops)"
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.drop_index("ix_practice_item_search_trgm", table_name="practice_item")
    with op.batch_alter_table("practice_item") as batch_op:
        batch_op.drop_column("search_text")
