from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping

from sqlalchemy import func, select

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
            result.update({"start": self.start.isoformat(), "end": self.end.isoformat()})
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


def _action_rows(
    filters: AnalyticsFilters,
    *,
    item_id: int | None = None,
):
    statement = (
        select(
            Action.user_id,
            Action.practice_item_id,
            Action.action,
            Action.datetime,
        )
        .join(User, User.id == Action.user_id)
        .join(PracticeItem, PracticeItem.id == Action.practice_item_id)
        .where(
            Action.action.in_(LEARNING_ACTIONS),
            Action.datetime >= filters.start_at,
            Action.datetime < filters.end_at,
        )
        .order_by(Action.user_id, Action.datetime)
    )
    statement = _apply_user_filter(statement, filters)
    statement = _apply_item_filter(statement, filters)
    if item_id is not None:
        statement = statement.where(Action.practice_item_id == item_id)
    return db.session.execute(statement).all()


def _counts(rows) -> dict[str, int | float]:
    right = sum(row.action == Action.RIGHT_ANSWER for row in rows)
    wrong = sum(row.action == Action.WRONG_ANSWER for row in rows)
    skips = sum(row.action == Action.SKIP for row in rows)
    answered = right + wrong
    return {
        "right": right,
        "wrong": wrong,
        "skips": skips,
        "cards": answered + skips,
        "answered": answered,
        "accuracy": round(right * 100 / answered, 1) if answered else 0.0,
    }


def _daily_series(filters: AnalyticsFilters, rows) -> list[dict[str, Any]]:
    grouped: dict[date, list[Any]] = defaultdict(list)
    active: dict[date, set[int]] = defaultdict(set)
    for row in rows:
        day = row.datetime.date()
        grouped[day].append(row)
        active[day].add(row.user_id)

    result = []
    day = filters.start
    while day <= filters.end:
        values = _counts(grouped[day])
        result.append({
            "date": day.isoformat(),
            "label": day.strftime("%d.%m"),
            "active_users": len(active[day]),
            **values,
        })
        day += timedelta(days=1)
    return result


def _session_metrics(rows) -> dict[str, int | float]:
    by_user: dict[int, list[datetime]] = defaultdict(list)
    for row in rows:
        by_user[row.user_id].append(row.datetime)

    session_count = 0
    active_seconds = 0.0
    active_days: dict[int, set[date]] = defaultdict(set)
    for user_id, timestamps in by_user.items():
        previous = None
        for timestamp in timestamps:
            active_days[user_id].add(timestamp.date())
            if previous is None:
                session_count += 1
            else:
                gap = (timestamp - previous).total_seconds()
                if gap < 0 or gap > SESSION_GAP_SECONDS:
                    session_count += 1
                elif gap <= ACTIVE_GAP_SECONDS:
                    active_seconds += gap
            previous = timestamp

    active_users = len(by_user)
    return {
        "sessions": session_count,
        "active_seconds": round(active_seconds),
        "avg_active_seconds": round(active_seconds / active_users)
        if active_users else 0,
        "avg_session_seconds": round(active_seconds / session_count)
        if session_count else 0,
        "avg_active_days": round(
            sum(map(len, active_days.values())) / active_users, 1
        ) if active_users else 0.0,
    }


def _users_query(filters: AnalyticsFilters):
    return _apply_user_filter(select(User), filters)


def _lifecycle_metrics(filters: AnalyticsFilters, rows) -> dict[str, Any]:
    users = db.session.execute(_users_query(filters)).scalars().all()
    period_users = [
        user for user in users
        if filters.start_at <= user.created_at < filters.end_at
    ]
    active_ids = {row.user_id for row in rows}
    returning = {
        user.id for user in users
        if user.id in active_ids and user.created_at < filters.start_at
    }
    converted = [
        user for user in period_users
        if user.identified_at is not None
        and user.identified_at > user.created_at
        and user.identified_at < filters.end_at
    ]

    action_days: dict[int, set[date]] = defaultdict(set)
    for row in rows:
        action_days[row.user_id].add(row.datetime.date())
    retention = {}
    for offset in (1, 7, 30):
        eligible = [
            user for user in users
            if filters.start
            <= user.created_at.date() + timedelta(days=offset)
            <= filters.end
        ]
        retained = sum(
            user.created_at.date() + timedelta(days=offset)
            in action_days[user.id]
            for user in eligible
        )
        retention[f"d{offset}"] = {
            "percent": round(retained * 100 / len(eligible), 1)
            if eligible else 0.0,
            "retained": retained,
            "cohort": len(eligible),
        }

    return {
        "new_users": len(period_users),
        "returning_users": len(returning),
        "conversions": len(converted),
        "conversion_rate": round(len(converted) * 100 / len(period_users), 1)
        if period_users else 0.0,
        "retention": retention,
    }


def _period_active_count(filters: AnalyticsFilters, days: int) -> int:
    end = filters.end
    window = replace(
        filters,
        start=end - timedelta(days=days - 1),
        end=end,
    )
    return len({row.user_id for row in _action_rows(window)})


def _item_title(item: PracticeItem) -> str:
    prompt = item.get_prompt().strip()
    return prompt if len(prompt) <= 90 else f"{prompt[:87]}…"


def _content_analytics(
    rows,
    *,
    limit: int | None = 10,
    exercise_query: str = "",
    exercise_sort: str = "accuracy",
) -> dict[str, Any]:
    item_rows: dict[int, list[Any]] = defaultdict(list)
    for row in rows:
        item_rows[row.practice_item_id].append(row)
    if not item_rows:
        return {"breakdown": [], "items": [], "item_count": 0}

    items = {
        item.id: item
        for item in db.session.execute(
            select(PracticeItem).where(PracticeItem.id.in_(item_rows))
        ).scalars().all()
    }
    categories = {
        category.id: category.name
        for category in db.session.execute(select(Category)).scalars()
    }

    grouped: dict[tuple[str, int | None, int | None], list[Any]] = defaultdict(list)
    serialized = []
    for item_id, values in item_rows.items():
        item = items.get(item_id)
        if item is None:
            continue
        grouped[(item.type, item.task_number, item.category_id)].extend(values)
        serialized.append({
            "id": item.id,
            "title": _item_title(item),
            "type": item.type,
            "task": item.task_number,
            "category": categories.get(item.category_id, "—"),
            "unique_users": len({row.user_id for row in values}),
            **_counts(values),
        })

    breakdown = []
    for (item_type, task, category_id), values in grouped.items():
        breakdown.append({
            "type": item_type,
            "task": task,
            "category": categories.get(category_id, "—"),
            "unique_users": len({row.user_id for row in values}),
            **_counts(values),
        })
    breakdown.sort(key=lambda value: value["cards"], reverse=True)
    if exercise_query:
        query = exercise_query.casefold()
        serialized = [
            item for item in serialized
            if query in " ".join((
                item["title"],
                item["category"],
                item["type"],
                str(item["task"] or ""),
            )).casefold()
        ]
    sort_keys = {
        "accuracy": lambda value: (value["accuracy"], -value["cards"]),
        "wrong": lambda value: (-value["wrong"], value["accuracy"]),
        "skips": lambda value: (-value["skips"], value["accuracy"]),
    }
    serialized.sort(key=sort_keys[exercise_sort])
    return {
        "breakdown": breakdown,
        "items": serialized if limit is None else serialized[:limit],
        "item_count": len(serialized),
    }


def build_dashboard(filters: AnalyticsFilters) -> dict[str, Any]:
    """Calculate all metrics displayed on the admin dashboard."""
    rows = _action_rows(filters)
    counts = _counts(rows)
    active_users = len({row.user_id for row in rows})
    total_users = db.session.scalar(
        select(func.count(User.id)).where(User.is_admin.is_(False))
    ) or 0
    registered_users = db.session.scalar(
        select(func.count(User.id)).where(
            User.is_admin.is_(False),
            (User.yandex_id.is_not(None)) | (User.telegram_id.is_not(None))
        )
    ) or 0
    summary = {
        "total_users": total_users,
        "registered_users": registered_users,
        "anonymous_users": total_users - registered_users,
        "active_users": active_users,
        "dau": _period_active_count(filters, 1),
        "wau": _period_active_count(filters, 7),
        "mau": _period_active_count(filters, 30),
        "cards_per_user": round(counts["cards"] / active_users, 1)
        if active_users else 0.0,
        **counts,
        **_session_metrics(rows),
        **_lifecycle_metrics(filters, rows),
    }
    return {
        "filters": filters,
        "summary": summary,
        "daily": _daily_series(filters, rows),
        "content": _content_analytics(
            rows,
            exercise_query=filters.exercise_query,
            exercise_sort=filters.exercise_sort,
        ),
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
    rows = _action_rows(item_filters, item_id=item_id)
    counts = _counts(rows)
    return {
        "id": item.id,
        "title": _item_title(item),
        "type": item.type,
        "task": item.task_number,
        "category": item.category.name if item.category else "—",
        "unique_users": len({row.user_id for row in rows}),
        "repeat_users": sum(
            count > 1
            for count in _frequency(row.user_id for row in rows).values()
        ),
        **counts,
        "daily": _daily_series(item_filters, rows),
    }


def build_item_export(filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """Return every per-item aggregate matching the export filters."""
    return _content_analytics(
        _action_rows(filters),
        limit=None,
        exercise_query=filters.exercise_query,
        exercise_sort=filters.exercise_sort,
    )["items"]


def _frequency(values) -> dict[Any, int]:
    result: dict[Any, int] = defaultdict(int)
    for value in values:
        result[value] += 1
    return result
