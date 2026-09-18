"""Enforce action, progress, and legal acceptance invariants.

Revision ID: f06b8c2d5e70
Revises: e95a7b1c4d60
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "f06b8c2d5e70"
down_revision = "e95a7b1c4d60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        UPDATE legal_acceptance
        SET revoked_at = accepted_at
        WHERE id IN (
            SELECT id FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id, terms_version, privacy_version,
                                     personal_data_consent_version
                        ORDER BY accepted_at DESC, id DESC
                    ) AS duplicate_position
                FROM legal_acceptance
                WHERE revoked_at IS NULL
            ) AS ranked
            WHERE duplicate_position > 1
        )
    """))
    op.create_index(
        "uq_legal_acceptance_active_versions",
        "legal_acceptance",
        [
            "user_id",
            "terms_version",
            "privacy_version",
            "personal_data_consent_version",
        ],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )

    with op.batch_alter_table("action") as batch_op:
        batch_op.create_check_constraint(
            "ck_action_known_type", "action IN (100, 101, 102, 103)"
        )
    with op.batch_alter_table("practice_progress") as batch_op:
        batch_op.create_check_constraint(
            "ck_practice_progress_nonnegative_counts",
            "right_count >= 0 AND wrong_count >= 0 AND skip_count >= 0",
        )
        batch_op.create_check_constraint(
            "ck_practice_progress_latest_action",
            "latest_action IN (100, 101, 102)",
        )
    with op.batch_alter_table("global_practice_stats") as batch_op:
        batch_op.create_check_constraint(
            "ck_global_practice_stats_nonnegative_counts",
            "right_count >= 0 AND wrong_count >= 0 AND skip_count >= 0",
        )
    with op.batch_alter_table("user_practice_stats") as batch_op:
        batch_op.create_check_constraint(
            "ck_user_practice_stats_nonnegative_counts",
            "right_count >= 0 AND wrong_count >= 0 AND skip_count >= 0",
        )
        batch_op.create_check_constraint(
            "ck_user_practice_stats_valid_streaks",
            "current_streak >= 0 AND best_streak >= current_streak",
        )
        batch_op.create_check_constraint(
            "ck_user_practice_stats_nonnegative_timing",
            "active_seconds >= 0 AND timed_intervals >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("user_practice_stats") as batch_op:
        batch_op.drop_constraint(
            "ck_user_practice_stats_nonnegative_timing", type_="check"
        )
        batch_op.drop_constraint(
            "ck_user_practice_stats_valid_streaks", type_="check"
        )
        batch_op.drop_constraint(
            "ck_user_practice_stats_nonnegative_counts", type_="check"
        )
    with op.batch_alter_table("global_practice_stats") as batch_op:
        batch_op.drop_constraint(
            "ck_global_practice_stats_nonnegative_counts", type_="check"
        )
    with op.batch_alter_table("practice_progress") as batch_op:
        batch_op.drop_constraint(
            "ck_practice_progress_latest_action", type_="check"
        )
        batch_op.drop_constraint(
            "ck_practice_progress_nonnegative_counts", type_="check"
        )
    with op.batch_alter_table("action") as batch_op:
        batch_op.drop_constraint("ck_action_known_type", type_="check")
    op.drop_index(
        "uq_legal_acceptance_active_versions",
        table_name="legal_acceptance",
    )
