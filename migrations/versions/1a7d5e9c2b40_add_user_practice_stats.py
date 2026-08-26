"""add user practice stats

Revision ID: 1a7d5e9c2b40
Revises: f4b3a21d9c10
"""

from datetime import timedelta

from alembic import op
import sqlalchemy as sa


revision = "1a7d5e9c2b40"
down_revision = "f4b3a21d9c10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_practice_stats",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("right_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("wrong_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skip_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("current_streak", sa.Integer(), server_default="0", nullable=False),
        sa.Column("best_streak", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active_seconds", sa.Float(), server_default="0", nullable=False),
        sa.Column("timed_intervals", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latest_action_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    connection = op.get_bind()
    metadata = sa.MetaData()
    action = sa.Table("action", metadata, autoload_with=connection)
    user = sa.Table("user", metadata, autoload_with=connection)
    stats = sa.Table("user_practice_stats", metadata, autoload_with=connection)
    actions = connection.execute(
        sa.select(action.c.user_id, action.c.action, action.c.datetime)
        .where(action.c.action.in_((100, 101, 102)))
        .order_by(action.c.user_id, action.c.datetime, action.c.id)
    )

    rows: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    previous_at = None
    for user_id, action_code, action_at in actions:
        if current is None or current["user_id"] != user_id:
            if current is not None:
                rows.append(current)
            current = {
                "user_id": user_id,
                "right_count": 0,
                "wrong_count": 0,
                "skip_count": 0,
                "current_streak": 0,
                "best_streak": 0,
                "active_seconds": 0.0,
                "timed_intervals": 0,
                "latest_action_at": action_at,
            }
            previous_at = None

        if previous_at is not None:
            pause = action_at - previous_at
            if timedelta() <= pause <= timedelta(minutes=10):
                current["active_seconds"] += pause.total_seconds()
                current["timed_intervals"] += 1
        previous_at = action_at
        current["latest_action_at"] = action_at

        if action_code == 100:
            current["right_count"] += 1
            current["current_streak"] += 1
            current["best_streak"] = max(
                current["best_streak"], current["current_streak"]
            )
        elif action_code == 101:
            current["wrong_count"] += 1
            current["current_streak"] = 0
        else:
            current["skip_count"] += 1
            current["current_streak"] = 0

    if current is not None:
        rows.append(current)
    if rows:
        connection.execute(stats.insert(), rows)
    connection.execute(stats.insert().from_select(
        ["user_id"],
        sa.select(user.c.id).where(~sa.exists(
            sa.select(stats.c.user_id).where(stats.c.user_id == user.c.id)
        )),
    ))


def downgrade() -> None:
    op.drop_table("user_practice_stats")
