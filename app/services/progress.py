from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select, update

from app.extensions import db
from app.models import Action, PracticeProgress, UserPracticeStats
from app.time_utils import ensure_utc


LEARNING_ACTIONS = (
    Action.RIGHT_ANSWER,
    Action.WRONG_ANSWER,
    Action.SKIP,
)
ACTIVE_GAP_SECONDS = 10 * 60


def merge_user_progress(source_user_id: int, target_user_id: int) -> None:
    """Move actions and rebuild the target user's progress projections."""
    db.session.execute(
        update(Action)
        .where(Action.user_id == source_user_id)
        .values(user_id=target_user_id)
    )
    db.session.execute(
        delete(PracticeProgress).where(
            PracticeProgress.user_id == target_user_id
        )
    )

    actions = db.session.execute(
        select(
            Action.practice_item_id,
            Action.action,
            Action.datetime,
        )
        .where(
            Action.user_id == target_user_id,
            Action.action.in_(LEARNING_ACTIONS),
        )
        .order_by(Action.datetime, Action.id)
    ).all()

    per_item: dict[int, dict[str, object]] = defaultdict(
        lambda: {
            "right_count": 0,
            "wrong_count": 0,
            "skip_count": 0,
            "latest_action": None,
            "latest_action_at": None,
        }
    )
    right_count = wrong_count = skip_count = 0
    current_streak = best_streak = 0
    active_seconds = 0.0
    timed_intervals = 0
    previous_at = None

    for row in actions:
        item = per_item[row.practice_item_id]
        if row.action == Action.RIGHT_ANSWER:
            right_count += 1
            current_streak += 1
            best_streak = max(best_streak, current_streak)
            item["right_count"] = int(item["right_count"]) + 1
        elif row.action == Action.WRONG_ANSWER:
            wrong_count += 1
            current_streak = 0
            item["wrong_count"] = int(item["wrong_count"]) + 1
        else:
            skip_count += 1
            current_streak = 0
            item["skip_count"] = int(item["skip_count"]) + 1

        item["latest_action"] = row.action
        item["latest_action_at"] = row.datetime
        if previous_at is not None:
            pause = (
                ensure_utc(row.datetime) - ensure_utc(previous_at)
            ).total_seconds()
            if 0 <= pause <= ACTIVE_GAP_SECONDS:
                active_seconds += pause
                timed_intervals += 1
        previous_at = row.datetime

    for practice_item_id, values in per_item.items():
        db.session.add(PracticeProgress(
            user_id=target_user_id,
            practice_item_id=practice_item_id,
            **values,
        ))

    stats = db.session.get(
        UserPracticeStats,
        target_user_id,
        with_for_update=True,
    )
    if stats is None:
        stats = UserPracticeStats(user_id=target_user_id)
        db.session.add(stats)
    stats.right_count = right_count
    stats.wrong_count = wrong_count
    stats.skip_count = skip_count
    stats.current_streak = current_streak
    stats.best_streak = best_streak
    stats.active_seconds = active_seconds
    stats.timed_intervals = timed_intervals
    stats.latest_action_at = previous_at
