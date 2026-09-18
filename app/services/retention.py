"""Retention operations for inactive anonymous profiles."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select

from app.extensions import db
from app.models import (
    Action,
    ErrorReport,
    LegalAcceptance,
    PracticeProgress,
    Settings,
    User,
    UserPracticeStats,
)
from app.services.progress import rebuild_global_practice_stats


def _inactive_anonymous_ids(cutoff: datetime, limit: int) -> list[int]:
    return list(db.session.scalars(
        select(User.id)
        .where(
            User.yandex_id.is_(None),
            User.telegram_id.is_(None),
            User.is_admin.is_(False),
            User.last_seen_at < cutoff,
        )
        .order_by(User.id)
        .limit(limit)
    ))


def count_inactive_anonymous_users(cutoff: datetime) -> int:
    """Count profiles eligible for retention cleanup."""
    return int(db.session.scalar(
        select(func.count(User.id)).where(
            User.yandex_id.is_(None),
            User.telegram_id.is_(None),
            User.is_admin.is_(False),
            User.last_seen_at < cutoff,
        )
    ) or 0)


def cleanup_inactive_anonymous_users(
    cutoff: datetime,
    *,
    batch_size: int = 500,
) -> int:
    """Delete expired anonymous profiles in bounded transactional batches."""
    deleted_count = 0
    while user_ids := _inactive_anonymous_ids(cutoff, batch_size):
        affected_item_ids = set(db.session.scalars(
            select(Action.practice_item_id)
            .where(Action.user_id.in_(user_ids))
            .distinct()
        ))
        for model in (
            Action,
            ErrorReport,
            PracticeProgress,
            UserPracticeStats,
            LegalAcceptance,
            Settings,
        ):
            db.session.execute(delete(model).where(model.user_id.in_(user_ids)))
        db.session.execute(delete(User).where(User.id.in_(user_ids)))
        rebuild_global_practice_stats(affected_item_ids)
        db.session.commit()
        deleted_count += len(user_ids)
    return deleted_count
