from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class PracticeProgress(db.Model):
    """Агрегированный прогресс пользователя по одной карточке."""

    __tablename__ = "practice_progress"
    __table_args__ = (
        CheckConstraint(
            "right_count >= 0 AND wrong_count >= 0 AND skip_count >= 0",
            name="ck_practice_progress_nonnegative_counts",
        ),
        CheckConstraint(
            "latest_action IN (100, 101, 102)",
            name="ck_practice_progress_latest_action",
        ),
        Index("ix_practice_progress_item", "practice_item_id"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    practice_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("practice_item.id", ondelete="CASCADE"),
        primary_key=True,
    )
    right_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    wrong_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    skip_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    latest_action: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_action_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class GlobalPracticeStats(db.Model):
    """Глобальные агрегаты ответов по одной карточке."""

    __tablename__ = "global_practice_stats"
    __table_args__ = (
        CheckConstraint(
            "right_count >= 0 AND wrong_count >= 0 AND skip_count >= 0",
            name="ck_global_practice_stats_nonnegative_counts",
        ),
    )

    practice_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("practice_item.id", ondelete="CASCADE"),
        primary_key=True,
    )
    right_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    wrong_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    skip_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class UserPracticeStats(db.Model):
    """Сводные показатели практики одного пользователя."""

    __tablename__ = "user_practice_stats"
    __table_args__ = (
        CheckConstraint(
            "right_count >= 0 AND wrong_count >= 0 AND skip_count >= 0",
            name="ck_user_practice_stats_nonnegative_counts",
        ),
        CheckConstraint(
            "current_streak >= 0 AND best_streak >= current_streak",
            name="ck_user_practice_stats_valid_streaks",
        ),
        CheckConstraint(
            "active_seconds >= 0 AND timed_intervals >= 0",
            name="ck_user_practice_stats_nonnegative_timing",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    right_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    wrong_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    skip_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    current_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    best_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    active_seconds: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    timed_intervals: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    latest_action_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
