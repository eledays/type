from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class PracticeProgress(db.Model):
    """Агрегированный прогресс пользователя по одной карточке."""

    __tablename__ = "practice_progress"
    __table_args__ = (
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
        DateTime, nullable=False
    )


class GlobalPracticeStats(db.Model):
    """Глобальные агрегаты ответов по одной карточке."""

    __tablename__ = "global_practice_stats"

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
