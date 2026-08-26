"""add practice progress projections

Revision ID: f4b3a21d9c10
Revises: e13c7a4b9d20
"""

from alembic import op
import sqlalchemy as sa


revision = "f4b3a21d9c10"
down_revision = "e13c7a4b9d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "practice_progress",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("practice_item_id", sa.Integer(), nullable=False),
        sa.Column("right_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("wrong_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skip_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latest_action", sa.Integer(), nullable=False),
        sa.Column("latest_action_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["practice_item_id"], ["practice_item.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "practice_item_id"),
    )
    op.create_index(
        "ix_practice_progress_item",
        "practice_progress",
        ["practice_item_id"],
    )
    op.create_table(
        "global_practice_stats",
        sa.Column("practice_item_id", sa.Integer(), nullable=False),
        sa.Column("right_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("wrong_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skip_count", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["practice_item_id"], ["practice_item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("practice_item_id"),
    )

    op.execute(sa.text("""
        INSERT INTO practice_progress (
            user_id, practice_item_id, right_count, wrong_count, skip_count,
            latest_action, latest_action_at
        )
        SELECT
            source.user_id,
            source.practice_item_id,
            SUM(CASE WHEN source.action = 100 THEN 1 ELSE 0 END),
            SUM(CASE WHEN source.action = 101 THEN 1 ELSE 0 END),
            SUM(CASE WHEN source.action = 102 THEN 1 ELSE 0 END),
            (
                SELECT latest.action
                FROM action AS latest
                WHERE latest.user_id = source.user_id
                  AND latest.practice_item_id = source.practice_item_id
                  AND latest.action IN (100, 101, 102)
                ORDER BY latest.datetime DESC, latest.id DESC
                LIMIT 1
            ),
            MAX(source.datetime)
        FROM action AS source
        WHERE source.action IN (100, 101, 102)
        GROUP BY source.user_id, source.practice_item_id
    """))
    op.execute(sa.text("""
        INSERT INTO global_practice_stats (
            practice_item_id, right_count, wrong_count, skip_count
        )
        SELECT
            practice_item_id,
            SUM(CASE WHEN action = 100 THEN 1 ELSE 0 END),
            SUM(CASE WHEN action = 101 THEN 1 ELSE 0 END),
            SUM(CASE WHEN action = 102 THEN 1 ELSE 0 END)
        FROM action
        WHERE action IN (100, 101, 102)
        GROUP BY practice_item_id
    """))


def downgrade() -> None:
    op.drop_table("global_practice_stats")
    op.drop_index("ix_practice_progress_item", table_name="practice_progress")
    op.drop_table("practice_progress")
