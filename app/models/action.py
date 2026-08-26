from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import DateTime, ForeignKey, Index, Integer
from sqlalchemy import event
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.practice_item import PracticeItem
    from app.models.user import User


class Action(db.Model):
    __tablename__ = "action"
    __table_args__ = (
        Index("ix_action_user_item", "user_id", "practice_item_id"),
        Index("ix_action_user_datetime", "user_id", "datetime"),
        Index("ix_action_user_action", "user_id", "action"),
    )

    RIGHT_ANSWER: ClassVar[int] = 100
    WRONG_ANSWER: ClassVar[int] = 101
    SKIP: ClassVar[int] = 102
    SAVE_WORD: ClassVar[int] = 103

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )
    practice_item_id: Mapped[int] = mapped_column(
        ForeignKey("practice_item.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[int] = mapped_column(Integer, nullable=False)
    datetime: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    user: Mapped[User] = relationship(back_populates="actions")
    practice_item: Mapped[PracticeItem] = relationship(back_populates="actions")


@event.listens_for(Session, "before_flush")
def update_practice_progress(session: Session, *_args: object) -> None:
    """Обновляет проекции прогресса вместе с новыми действиями."""
    learning_actions = {
        Action.RIGHT_ANSWER,
        Action.WRONG_ANSWER,
        Action.SKIP,
    }
    new_actions = [
        item
        for item in session.new
        if isinstance(item, Action) and item.action in learning_actions
    ]
    if not new_actions:
        return

    from app.models.practice_progress import (
        GlobalPracticeStats,
        PracticeProgress,
    )

    progress_cache: dict[tuple[int, int], PracticeProgress] = {}
    global_cache: dict[int, GlobalPracticeStats] = {}
    for action in new_actions:
        if action.datetime is None:
            action.datetime = datetime.now()
        key = (action.user_id, action.practice_item_id)
        progress = progress_cache.get(key)
        if progress is None:
            progress = session.get(PracticeProgress, key)
            if progress is None:
                progress = PracticeProgress(
                    user_id=action.user_id,
                    practice_item_id=action.practice_item_id,
                    latest_action=action.action,
                    latest_action_at=action.datetime,
                )
                session.add(progress)
            progress_cache[key] = progress

        global_stats = global_cache.get(action.practice_item_id)
        if global_stats is None:
            global_stats = session.get(
                GlobalPracticeStats, action.practice_item_id
            )
            if global_stats is None:
                global_stats = GlobalPracticeStats(
                    practice_item_id=action.practice_item_id
                )
                session.add(global_stats)
            global_cache[action.practice_item_id] = global_stats

        if action.action == Action.RIGHT_ANSWER:
            progress.right_count = (progress.right_count or 0) + 1
            global_stats.right_count = (global_stats.right_count or 0) + 1
        elif action.action == Action.WRONG_ANSWER:
            progress.wrong_count = (progress.wrong_count or 0) + 1
            global_stats.wrong_count = (global_stats.wrong_count or 0) + 1
        elif action.action == Action.SKIP:
            progress.skip_count = (progress.skip_count or 0) + 1
            global_stats.skip_count = (global_stats.skip_count or 0) + 1
        else:
            continue

        if action.datetime >= progress.latest_action_at:
            progress.latest_action = action.action
            progress.latest_action_at = action.datetime
