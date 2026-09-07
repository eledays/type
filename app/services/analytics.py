from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping

from sqlalchemy import case, func, select

from app.extensions import db
from app.models import Action, Category, PracticeItem, User


LEARNING_ACTIONS = (
    Action.RIGHT_ANSWER,
    Action.WRONG_ANSWER,
    Action.SKIP,
)
SESSION_GAP_SECONDS = 30 * 60
ACTIVE_GAP_SECONDS = 10 * 60
ALLOWED_PERIODS = {7, 30, 90, 365}


@dataclass(frozen=True)
class AnalyticsFilters:
    """Validated filters shared by the dashboard, details, and CSV export."""

    start: date
    end: date
    period: str = "30"
    user_type: str = "all"
    exercise_type: str = "all"
    task: int | None = None
    category: int | None = None
    exercise_query: str = ""
    exercise_sort: str = "accuracy"

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.start, time.min)

    @property
    def end_at(self) -> datetime:
        return datetime.combine(self.end + timedelta(days=1), time.min)

    def as_query(self) -> dict[str, str]:
        result = {
            "period": self.period,
            "user_type": self.user_type,
            "exercise_type": self.exercise_type,
        }
        if self.period == "custom":
            result.update({
                "start": self.start.isoformat(),
                "end": self.end.isoformat(),
            })
        if self.task is not None:
            result["task"] = str(self.task)
        if self.category is not None:
            result["category"] = str(self.category)
        if self.exercise_query:
            result["exercise_query"] = self.exercise_query
        if self.exercise_sort != "accuracy":
            result["exercise_sort"] = self.exercise_sort
        return result


def parse_filters(args: Mapping[str, Any]) -> AnalyticsFilters:
    """Build analytics filters from untrusted query parameters."""
    today = date.today()
    raw_period = str(args.get("period", "30"))
    if raw_period == "custom":
        try:
            start = date.fromisoformat(str(args.get("start", "")))
            end = date.fromisoformat(str(args.get("end", "")))
        except ValueError:
            raw_period = "30"
        else:
            end = min(end, today)
            start = max(start, end - timedelta(days=729))
            if start <= end:
                period = "custom"
            else:
                raw_period = "30"
    if raw_period != "custom":
        try:
            days = int(raw_period)
        except ValueError:
            days = 30
        if days not in ALLOWED_PERIODS:
            days = 30
        end = today
        start = today - timedelta(days=days - 1)
        period = str(days)

    user_type = str(args.get("user_type", "all"))
    if user_type not in {"all", "registered", "anonymous"}:
        user_type = "all"
    exercise_type = str(args.get("exercise_type", "all"))
    if exercise_type not in {"all", "spelling", "paronym"}:
        exercise_type = "all"
    exercise_sort = str(args.get("exercise_sort", "accuracy"))
    if exercise_sort not in {"accuracy", "wrong", "skips"}:
        exercise_sort = "accuracy"

    return AnalyticsFilters(
        start=start,
        end=end,
        period=period,
        user_type=user_type,
        exercise_type=exercise_type,
        task=_positive_int(args.get("task")),
        category=_positive_int(args.get("category")),
        exercise_query=str(args.get("exercise_query", "")).strip()[:100],
        exercise_sort=exercise_sort,
    )


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _apply_user_filter(statement, filters: AnalyticsFilters):
    statement = statement.where(User.is_admin.is_(False))
    if filters.user_type == "registered":
        return statement.where(
            (User.yandex_id.is_not(None)) | (User.telegram_id.is_not(None))
        )
    if filters.user_type == "anonymous":
        return statement.where(
            User.yandex_id.is_(None), User.telegram_id.is_(None)
        )
    return statement


def _apply_item_filter(statement, filters: AnalyticsFilters):
    if filters.exercise_type != "all":
        statement = statement.where(PracticeItem.type == filters.exercise_type)
    if filters.task is not None:
        statement = statement.where(PracticeItem.task_number == filters.task)
    if filters.category is not None:
        statement = statement.where(PracticeItem.category_id == filters.category)
    return statement


def _filtered_actions(
    filters: AnalyticsFilters,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    item_id: int | None = None,
):
    statement = (
        select(
            Action.id.label("id"),
            Action.user_id.label("user_id"),
            Action.practice_item_id.label("practice_item_id"),
            Action.action.label("action"),
            Action.datetime.label("datetime"),
        )
        .join(User, User.id == Action.user_id)
        .join(PracticeItem, PracticeItem.id == Action.practice_item_id)
        .where(
            Action.action.in_(LEARNING_ACTIONS),
            Action.datetime >= (start_at or filters.start_at),
            Action.datetime < (end_at or filters.end_at),
        )
    )
    statement = _apply_user_filter(statement, filters)
    statement = _apply_item_filter(statement, filters)
    if item_id is not None:
        statement = statement.where(Action.practice_item_id == item_id)
    return statement


def _count_expressions(actions):
    return (
        func.sum(case((actions.c.action == Action.RIGHT_ANSWER, 1), else_=0)),
        func.sum(case((actions.c.action == Action.WRONG_ANSWER, 1), else_=0)),
        func.sum(case((actions.c.action == Action.SKIP, 1), else_=0)),
    )


def _counts(right: int | None, wrong: int | None, skips: int | None):
    right = int(right or 0)
    wrong = int(wrong or 0)
    skips = int(skips or 0)
    answered = right + wrong
    return {
        "right": right,
        "wrong": wrong,
        "skips": skips,
        "cards": answered + skips,
        "answered": answered,
        "accuracy": round(right * 100 / answered, 1) if answered else 0.0,
    }


def _summary_counts(filters: AnalyticsFilters) -> dict[str, int | float]:
    actions = _filtered_actions(filters).subquery()
    right, wrong, skips = _count_expressions(actions)
    row = db.session.execute(select(right, wrong, skips)).one()
    return _counts(*row)


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _daily_series(
    filters: AnalyticsFilters,
    *,
    item_id: int | None = None,
) -> list[dict[str, Any]]:
    actions = _filtered_actions(filters, item_id=item_id).subquery()
    day = func.date(actions.c.datetime).label("day")
    right, wrong, skips = _count_expressions(actions)
    rows = db.session.execute(
        select(
            day,
            func.count(func.distinct(actions.c.user_id)),
            right,
            wrong,
            skips,
        ).group_by(day).order_by(day)
    ).all()
    grouped = {
        _as_date(row[0]): {
            "active_users": int(row[1]),
            **_counts(row[2], row[3], row[4]),
        }
        for row in rows
    }
    result = []
    current = filters.start
    while current <= filters.end:
        result.append({
            "date": current.isoformat(),
            "label": current.strftime("%d.%m"),
            **grouped.get(current, {
                "active_users": 0,
                **_counts(0, 0, 0),
            }),
        })
        current += timedelta(days=1)
    return result


def _session_metrics(filters: AnalyticsFilters) -> dict[str, int | float]:
    actions = _filtered_actions(filters).subquery()
    previous = func.lag(actions.c.datetime).over(
        partition_by=actions.c.user_id,
        order_by=(actions.c.datetime, actions.c.id),
    ).label("previous")
    timed = select(
        actions.c.user_id,
        actions.c.datetime,
        previous,
    ).subquery()
    if db.session.get_bind().dialect.name == "sqlite":
        gap = (
            func.julianday(timed.c.datetime)
            - func.julianday(timed.c.previous)
        ) * 86400.0
    else:
        gap = func.extract("epoch", timed.c.datetime - timed.c.previous)
    new_session = case(
        (
            timed.c.previous.is_(None) | (gap < 0)
            | (gap > SESSION_GAP_SECONDS),
            1,
        ),
        else_=0,
    )
    active_gap = case(
        ((gap >= 0) & (gap <= ACTIVE_GAP_SECONDS), gap),
        else_=0,
    )
    totals = db.session.execute(select(
        func.count(func.distinct(timed.c.user_id)),
        func.sum(new_session),
        func.sum(active_gap),
    )).one()
    active_users = int(totals[0] or 0)
    sessions = int(totals[1] or 0)
    active_seconds = round(float(totals[2] or 0))

    user_days = select(
        actions.c.user_id,
        func.date(actions.c.datetime).label("day"),
    ).group_by(actions.c.user_id, func.date(actions.c.datetime)).subquery()
    days_per_user = select(
        user_days.c.user_id,
        func.count().label("days"),
    ).group_by(user_days.c.user_id).subquery()
    avg_active_days = db.session.scalar(select(func.avg(days_per_user.c.days)))
    return {
        "sessions": sessions,
        "active_seconds": active_seconds,
        "avg_active_seconds": round(active_seconds / active_users)
        if active_users else 0,
        "avg_session_seconds": round(active_seconds / sessions)
        if sessions else 0,
        "avg_active_days": round(float(avg_active_days or 0), 1),
    }


def _users_query(filters: AnalyticsFilters):
    return _apply_user_filter(select(User), filters)


def _lifecycle_metrics(filters: AnalyticsFilters) -> dict[str, Any]:
    users = _users_query(filters).subquery()
    new_users = db.session.scalar(select(func.count()).select_from(users).where(
        users.c.created_at >= filters.start_at,
        users.c.created_at < filters.end_at,
    )) or 0
    conversions = db.session.scalar(select(func.count()).select_from(users).where(
        users.c.created_at >= filters.start_at,
        users.c.created_at < filters.end_at,
        users.c.identified_at.is_not(None),
        users.c.identified_at > users.c.created_at,
        users.c.identified_at < filters.end_at,
    )) or 0

    actions = _filtered_actions(filters).subquery()
    returning_users = db.session.scalar(
        select(func.count(func.distinct(actions.c.user_id)))
        .join(User, User.id == actions.c.user_id)
        .where(User.created_at < filters.start_at)
    ) or 0
    action_days = {
        (row.user_id, _as_date(row.day))
        for row in db.session.execute(select(
            actions.c.user_id,
            func.date(actions.c.datetime).label("day"),
        ).distinct()).all()
    }
    earliest_cohort = datetime.combine(
        filters.start - timedelta(days=30), time.min
    )
    cohorts = db.session.execute(
        _users_query(filters)
        .with_only_columns(User.id, User.created_at)
        .where(
            User.created_at >= earliest_cohort,
            User.created_at < filters.end_at,
        )
    ).all()
    retention = {}
    for offset in (1, 7, 30):
        eligible = [
            row for row in cohorts
            if filters.start
            <= row.created_at.date() + timedelta(days=offset)
            <= filters.end
        ]
        retained = sum(
            (row.id, row.created_at.date() + timedelta(days=offset))
            in action_days
            for row in eligible
        )
        retention[f"d{offset}"] = {
            "percent": round(retained * 100 / len(eligible), 1)
            if eligible else 0.0,
            "retained": retained,
            "cohort": len(eligible),
        }
    return {
        "new_users": int(new_users),
        "returning_users": int(returning_users),
        "conversions": int(conversions),
        "conversion_rate": round(conversions * 100 / new_users, 1)
        if new_users else 0.0,
        "retention": retention,
    }


def _period_active_count(filters: AnalyticsFilters, days: int) -> int:
    end_at = datetime.combine(filters.end + timedelta(days=1), time.min)
    start_at = end_at - timedelta(days=days)
    actions = _filtered_actions(
        filters,
        start_at=start_at,
        end_at=end_at,
    ).subquery()
    return int(db.session.scalar(
        select(func.count(func.distinct(actions.c.user_id)))
    ) or 0)


def _item_title(item: PracticeItem) -> str:
    prompt = item.get_prompt().strip()
    return prompt if len(prompt) <= 90 else f"{prompt[:87]}…"


def _compact_search(value: str, *, keep_placeholder: bool = False) -> str:
    normalized = value.casefold().replace("ё", "е")
    return "".join(
        character
        for character in normalized
        if character.isalnum() or (keep_placeholder and character == "_")
    )


def _template_contains(query: str, value: str) -> bool:
    """Match a partial query while treating an exercise blank as one letter."""
    needle = _compact_search(query)
    candidate = _compact_search(value, keep_placeholder=True)
    if not needle:
        return True
    if needle in candidate.replace("_", ""):
        return True
    if len(needle) > len(candidate):
        return False
    return any(
        all(
            candidate[start + offset] in {"_", character}
            for offset, character in enumerate(needle)
        )
        for start in range(len(candidate) - len(needle) + 1)
    )


def _exercise_matches(
    item: PracticeItem,
    category: str,
    query: str,
) -> bool:
    if _template_contains(query, item.get_prompt()):
        return True
    metadata = " ".join((category, item.type, str(item.task_number or "")))
    return query.casefold().replace("ё", "е") in metadata.casefold().replace(
        "ё", "е"
    )


def _item_aggregate_rows(filters: AnalyticsFilters, item_id: int | None = None):
    actions = _filtered_actions(filters, item_id=item_id).subquery()
    right, wrong, skips = _count_expressions(actions)
    return db.session.execute(select(
        actions.c.practice_item_id,
        func.count(func.distinct(actions.c.user_id)),
        right,
        wrong,
        skips,
    ).group_by(actions.c.practice_item_id)).all()


def _serialized_items(
    filters: AnalyticsFilters,
    *,
    limit: int | None = 10,
) -> tuple[list[dict[str, Any]], int]:
    rows = _item_aggregate_rows(filters)
    if not rows:
        return [], 0
    item_ids = [row[0] for row in rows]
    items = {
        item.id: item
        for item in db.session.execute(
            select(PracticeItem).where(PracticeItem.id.in_(item_ids))
        ).scalars().all()
    }
    categories = {
        category.id: category.name
        for category in db.session.execute(select(Category)).scalars()
    }
    serialized = []
    for row in rows:
        item = items.get(row[0])
        if item is None:
            continue
        category = categories.get(item.category_id, "—")
        if filters.exercise_query and not _exercise_matches(
            item, category, filters.exercise_query
        ):
            continue
        serialized.append({
            "id": item.id,
            "title": _item_title(item),
            "type": item.type,
            "task": item.task_number,
            "category": category,
            "unique_users": int(row[1]),
            **_counts(row[2], row[3], row[4]),
        })
    sort_keys = {
        "accuracy": lambda value: (value["accuracy"], -value["cards"]),
        "wrong": lambda value: (-value["wrong"], value["accuracy"]),
        "skips": lambda value: (-value["skips"], value["accuracy"]),
    }
    serialized.sort(key=sort_keys[filters.exercise_sort])
    total = len(serialized)
    return (serialized if limit is None else serialized[:limit]), total


def _content_breakdown(filters: AnalyticsFilters) -> list[dict[str, Any]]:
    actions = _filtered_actions(filters).subquery()
    right, wrong, skips = _count_expressions(actions)
    rows = db.session.execute(
        select(
            PracticeItem.type,
            PracticeItem.task_number,
            PracticeItem.category_id,
            func.count(func.distinct(actions.c.user_id)),
            right,
            wrong,
            skips,
        )
        .join(PracticeItem, PracticeItem.id == actions.c.practice_item_id)
        .group_by(
            PracticeItem.type,
            PracticeItem.task_number,
            PracticeItem.category_id,
        )
    ).all()
    categories = {
        category.id: category.name
        for category in db.session.execute(select(Category)).scalars()
    }
    result = [{
        "type": row[0],
        "task": row[1],
        "category": categories.get(row[2], "—"),
        "unique_users": int(row[3]),
        **_counts(row[4], row[5], row[6]),
    } for row in rows]
    result.sort(key=lambda value: value["cards"], reverse=True)
    return result


def build_dashboard(filters: AnalyticsFilters) -> dict[str, Any]:
    """Calculate all metrics displayed on the admin dashboard."""
    counts = _summary_counts(filters)
    active_users = _period_active_count(
        filters,
        (filters.end - filters.start).days + 1,
    )
    total_users = db.session.scalar(
        select(func.count(User.id)).where(User.is_admin.is_(False))
    ) or 0
    registered_users = db.session.scalar(
        select(func.count(User.id)).where(
            User.is_admin.is_(False),
            (User.yandex_id.is_not(None)) | (User.telegram_id.is_not(None)),
        )
    ) or 0
    items, item_count = _serialized_items(filters)
    summary = {
        "total_users": int(total_users),
        "registered_users": int(registered_users),
        "anonymous_users": int(total_users - registered_users),
        "active_users": active_users,
        "dau": _period_active_count(filters, 1),
        "wau": _period_active_count(filters, 7),
        "mau": _period_active_count(filters, 30),
        "cards_per_user": round(counts["cards"] / active_users, 1)
        if active_users else 0.0,
        **counts,
        **_session_metrics(filters),
        **_lifecycle_metrics(filters),
    }
    return {
        "filters": filters,
        "summary": summary,
        "daily": _daily_series(filters),
        "content": {
            "breakdown": _content_breakdown(filters),
            "items": items,
            "item_count": item_count,
        },
    }


def build_item_detail(
    item_id: int,
    filters: AnalyticsFilters,
) -> dict[str, Any] | None:
    """Calculate period metrics for one practice item."""
    item = db.session.get(PracticeItem, item_id)
    if item is None:
        return None
    item_filters = replace(
        filters,
        exercise_type="all",
        task=None,
        category=None,
    )
    rows = _item_aggregate_rows(item_filters, item_id=item_id)
    counts = _counts(
        rows[0][2] if rows else 0,
        rows[0][3] if rows else 0,
        rows[0][4] if rows else 0,
    )
    return {
        "id": item.id,
        "title": _item_title(item),
        "type": item.type,
        "task": item.task_number,
        "category": item.category.name if item.category else "—",
        "unique_users": int(rows[0][1]) if rows else 0,
        "repeat_users": _repeat_users(item_filters, item_id),
        **counts,
        "daily": _daily_series(item_filters, item_id=item_id),
    }


def _repeat_users(filters: AnalyticsFilters, item_id: int) -> int:
    actions = _filtered_actions(filters, item_id=item_id).subquery()
    frequencies = select(
        actions.c.user_id,
        func.count().label("frequency"),
    ).group_by(actions.c.user_id).subquery()
    return int(db.session.scalar(
        select(func.count()).select_from(frequencies).where(
            frequencies.c.frequency > 1
        )
    ) or 0)


def build_exercise_results(filters: AnalyticsFilters) -> dict[str, Any]:
    """Return the small exercise result set used by live search."""
    items, item_count = _serialized_items(filters)
    return {"items": items, "item_count": item_count}


def build_item_export(filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """Return every per-item aggregate matching the export filters."""
    items, _ = _serialized_items(filters, limit=None)
    return items
