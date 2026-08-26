from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import DateTime, ForeignKey, Index, Integer, case, event
from sqlalchemy.engine import Connection
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

    from app.models.practice_progress import UserPracticeStats

    user_cache: dict[int, UserPracticeStats] = {}
    for action in sorted(
        new_actions,
        key=lambda item: (item.user_id, item.datetime or datetime.now()),
    ):
        if action.datetime is None:
            action.datetime = datetime.now()
        user_stats = user_cache.get(action.user_id)
        if user_stats is None:
            user_stats = session.get(
                UserPracticeStats,
                action.user_id,
                with_for_update=True,
            )
            if user_stats is None:
                user_stats = UserPracticeStats(user_id=action.user_id)
                session.add(user_stats)
            user_cache[action.user_id] = user_stats

        if action.action == Action.RIGHT_ANSWER:
            user_stats.right_count = (user_stats.right_count or 0) + 1
            user_stats.current_streak = (user_stats.current_streak or 0) + 1
            user_stats.best_streak = max(
                user_stats.best_streak or 0,
                user_stats.current_streak,
            )
        elif action.action == Action.WRONG_ANSWER:
            user_stats.wrong_count = (user_stats.wrong_count or 0) + 1
            user_stats.current_streak = 0
        elif action.action == Action.SKIP:
            user_stats.skip_count = (user_stats.skip_count or 0) + 1
            user_stats.current_streak = 0
        else:
            continue

        if (
            user_stats.latest_action_at is None
            or action.datetime >= user_stats.latest_action_at
        ):
            if user_stats.latest_action_at is not None:
                pause = (action.datetime - user_stats.latest_action_at).total_seconds()
                if 0 <= pause <= 600:
                    user_stats.active_seconds = (
                        user_stats.active_seconds or 0.0
                    ) + pause
                    user_stats.timed_intervals = (
                        user_stats.timed_intervals or 0
                    ) + 1
            user_stats.latest_action_at = action.datetime


def _dialect_insert(connection: Connection, table):
    """Возвращает INSERT с поддержкой ON CONFLICT для рабочей СУБД."""
    if connection.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    elif connection.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        return None
    return insert(table)


@event.listens_for(Action, "after_insert")
def upsert_item_progress(
    _mapper: object,
    connection: Connection,
    action: Action,
) -> None:
    """Атомарно обновляет агрегаты карточки после вставки действия."""
    if action.action not in {
        Action.RIGHT_ANSWER,
        Action.WRONG_ANSWER,
        Action.SKIP,
    }:
        return

    from app.models.practice_progress import (
        GlobalPracticeStats,
        PracticeProgress,
    )

    increments = {
        "right_count": int(action.action == Action.RIGHT_ANSWER),
        "wrong_count": int(action.action == Action.WRONG_ANSWER),
        "skip_count": int(action.action == Action.SKIP),
    }
    progress_table = PracticeProgress.__table__
    global_table = GlobalPracticeStats.__table__
    progress_insert = _dialect_insert(connection, progress_table)
    global_insert = _dialect_insert(connection, global_table)

    if progress_insert is None or global_insert is None:
        _fallback_update_item_progress(
            connection, action, progress_table, global_table, increments
        )
        return

    progress_values = {
        "user_id": action.user_id,
        "practice_item_id": action.practice_item_id,
        "latest_action": action.action,
        "latest_action_at": action.datetime,
        **increments,
    }
    progress_statement = progress_insert.values(**progress_values)
    excluded = progress_statement.excluded
    newer_action = excluded.latest_action_at >= progress_table.c.latest_action_at
    connection.execute(progress_statement.on_conflict_do_update(
        index_elements=["user_id", "practice_item_id"],
        set_={
            name: progress_table.c[name] + increment
            for name, increment in increments.items()
        } | {
            "latest_action": case(
                (newer_action, excluded.latest_action),
                else_=progress_table.c.latest_action,
            ),
            "latest_action_at": case(
                (newer_action, excluded.latest_action_at),
                else_=progress_table.c.latest_action_at,
            ),
        },
    ))

    global_statement = global_insert.values(
        practice_item_id=action.practice_item_id,
        **increments,
    )
    connection.execute(global_statement.on_conflict_do_update(
        index_elements=["practice_item_id"],
        set_={
            name: global_table.c[name] + increment
            for name, increment in increments.items()
        },
    ))


def _fallback_update_item_progress(
    connection: Connection,
    action: Action,
    progress_table,
    global_table,
    increments: dict[str, int],
) -> None:
    """Обновляет агрегаты для СУБД без диалектного UPSERT."""
    progress_result = connection.execute(
        progress_table.update()
        .where(
            progress_table.c.user_id == action.user_id,
            progress_table.c.practice_item_id == action.practice_item_id,
        )
        .values(**({
            name: progress_table.c[name] + increment
            for name, increment in increments.items()
        } | {
            "latest_action": case(
                (
                    progress_table.c.latest_action_at <= action.datetime,
                    action.action,
                ),
                else_=progress_table.c.latest_action,
            ),
            "latest_action_at": case(
                (
                    progress_table.c.latest_action_at <= action.datetime,
                    action.datetime,
                ),
                else_=progress_table.c.latest_action_at,
            ),
        }))
    )
    if not progress_result.rowcount:
        connection.execute(progress_table.insert().values(
            user_id=action.user_id,
            practice_item_id=action.practice_item_id,
            latest_action=action.action,
            latest_action_at=action.datetime,
            **increments,
        ))

    global_result = connection.execute(
        global_table.update()
        .where(global_table.c.practice_item_id == action.practice_item_id)
        .values(**{
            name: global_table.c[name] + increment
            for name, increment in increments.items()
        })
    )
    if not global_result.rowcount:
        connection.execute(global_table.insert().values(
            practice_item_id=action.practice_item_id,
            **increments,
        ))
