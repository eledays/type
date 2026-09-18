from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from flask import current_app
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import Date, String, and_, case, cast, func, or_, select

from app.extensions import db
from app.models import (
    Action,
    Category,
    ParonymExercise,
    PracticeItem,
    SpellingExercise,
    User,
)
from app.search import normalize_exercise_search
from app.time_utils import UTC, ensure_utc

LEARNING_ACTIONS = (
    Action.RIGHT_ANSWER,
    Action.WRONG_ANSWER,
    Action.SKIP,
)
SESSION_GAP_SECONDS = 30 * 60
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
    timezone_name: str = "Europe/Moscow"

    @property
    def start_at(self) -> datetime:
        local = datetime.combine(
            self.start,
            time.min,
            tzinfo=ZoneInfo(self.timezone_name),
        )
        return local.astimezone(UTC)

    @property
    def end_at(self) -> datetime:
        local = datetime.combine(
            self.end + timedelta(days=1),
            time.min,
            tzinfo=ZoneInfo(self.timezone_name),
        )
        return local.astimezone(UTC)

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
    timezone_name = current_app.config["ANALYTICS_TIMEZONE"]
    today = datetime.now(ZoneInfo(timezone_name)).date()
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
        timezone_name=timezone_name,
    )


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _effective_identified_at():
    """Return the historical identification time, including legacy users."""
    return func.coalesce(
        User.identified_at,
        case(
            (
                (User.yandex_id.is_not(None))
                | (User.telegram_id.is_not(None)),
                User.created_at,
            ),
            else_=None,
        ),
    )


def _apply_user_filter(statement, filters: AnalyticsFilters, at=None):
    statement = statement.where(User.is_admin.is_(False))
    at = at if at is not None else filters.end_at
    identified_at = _effective_identified_at()
    if filters.user_type == "registered":
        return statement.where(
            identified_at.is_not(None), identified_at < at
        )
    if filters.user_type == "anonymous":
        return statement.where(
            (identified_at.is_(None)) | (identified_at >= at)
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
    include_before_start: bool = False,
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
            Action.datetime < (end_at or filters.end_at),
        )
    )
    if not include_before_start:
        statement = statement.where(
            Action.datetime >= (start_at or filters.start_at)
        )
    statement = _apply_user_filter(statement, filters, Action.datetime)
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


def _local_day(timestamp, filters: AnalyticsFilters):
    if db.session.get_bind().dialect.name == "postgresql":
        return func.date(func.timezone(filters.timezone_name, timestamp))
    raw_connection = db.session.connection().connection
    driver_connection: Any = getattr(
        raw_connection, "driver_connection", raw_connection
    )

    def local_date(value: Any, timezone_name: str) -> str | None:
        if value is None:
            return None
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value))
        )
        return ensure_utc(parsed).astimezone(
            ZoneInfo(timezone_name)
        ).date().isoformat()

    driver_connection.create_function("local_date", 2, local_date)
    return func.local_date(timestamp, filters.timezone_name)


def _daily_series(
    filters: AnalyticsFilters,
    *,
    item_id: int | None = None,
) -> list[dict[str, Any]]:
    actions = _filtered_actions(filters, item_id=item_id).subquery()
    day_expression = _local_day(actions.c.datetime, filters)
    day = day_expression.label("day")
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
    actions = _filtered_actions(
        filters, include_before_start=True
    ).subquery()
    previous = func.lag(actions.c.datetime).over(
        partition_by=actions.c.user_id,
        order_by=(actions.c.datetime, actions.c.id),
    ).label("previous")
    timed_history = select(
        actions.c.user_id,
        actions.c.datetime,
        previous,
    ).subquery()
    timed = select(timed_history).where(
        timed_history.c.datetime >= filters.start_at
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
    session_span = case(
        ((gap >= 0) & (gap <= SESSION_GAP_SECONDS), gap),
        else_=0,
    )
    totals = db.session.execute(select(
        func.count(func.distinct(timed.c.user_id)),
        func.sum(new_session),
        func.sum(session_span),
    )).one()
    active_users = int(totals[0] or 0)
    sessions = int(totals[1] or 0)
    active_seconds = round(float(totals[2] or 0))

    period_actions = select(actions).where(
        actions.c.datetime >= filters.start_at
    ).subquery()
    local_day = _local_day(period_actions.c.datetime, filters)
    user_days = select(
        period_actions.c.user_id,
        local_day.label("day"),
    ).group_by(
        period_actions.c.user_id,
        local_day,
    ).subquery()
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


def _audience_counts(filters: AnalyticsFilters) -> dict[str, int | str]:
    base_conditions = (
        User.is_admin.is_(False),
        User.created_at < filters.end_at,
    )
    identified_at = _effective_identified_at()
    registered_condition = identified_at.is_not(None) & (
        identified_at < filters.end_at
    )
    anonymous_condition = identified_at.is_(None) | (
        identified_at >= filters.end_at
    )
    registered, anonymous = db.session.execute(select(
        func.sum(case((registered_condition, 1), else_=0)),
        func.sum(case((anonymous_condition, 1), else_=0)),
    ).where(*base_conditions)).one()
    registered = int(registered or 0)
    anonymous = int(anonymous or 0)
    if filters.user_type == "registered":
        total = registered
        label = "Авторизованные к концу периода"
    elif filters.user_type == "anonymous":
        total = anonymous
        label = "Анонимные к концу периода"
    else:
        total = registered + anonymous
        label = f"{registered} авторизованных · {anonymous} анонимных"
    return {
        "total_users": total,
        "registered_users": registered,
        "anonymous_users": anonymous,
        "audience_label": label,
    }


def _lifecycle_metrics(filters: AnalyticsFilters) -> dict[str, Any]:
    new_user_conditions = (
        User.is_admin.is_(False),
        User.created_at >= filters.start_at,
        User.created_at < filters.end_at,
    )
    new_users = db.session.scalar(
        select(func.count(User.id)).where(*new_user_conditions)
    ) or 0
    conversions = db.session.scalar(select(func.count(User.id)).where(
        *new_user_conditions,
        User.identified_at.is_not(None),
        User.identified_at > User.created_at,
        User.identified_at < filters.end_at,
    )) or 0

    actions = _filtered_actions(filters).subquery()
    returning_users = db.session.scalar(
        select(func.count(func.distinct(actions.c.user_id)))
        .join(User, User.id == actions.c.user_id)
        .where(User.created_at < filters.start_at)
    ) or 0
    earliest_cohort = filters.start_at - timedelta(days=30)
    retention = {}
    cohort_day = _local_day(User.created_at, filters)
    action_day = _local_day(actions.c.datetime, filters)
    retention_columns: list[Any] = []
    for offset in (1, 7, 30):
        if db.session.get_bind().dialect.name == "postgresql":
            target_day = func.cast(cohort_day, Date) + offset
        else:
            target_day = func.date(cohort_day, f"+{offset} days")
        eligible = (
            select(User.id.label("user_id"), target_day.label("target_day"))
            .where(
                User.is_admin.is_(False),
                User.created_at >= earliest_cohort,
                User.created_at < filters.end_at,
                target_day >= filters.start.isoformat(),
                target_day <= filters.end.isoformat(),
            )
            .subquery()
        )
        retention_columns.extend((
            select(func.count())
            .select_from(eligible)
            .scalar_subquery()
            .label(f"d{offset}_cohort"),
            select(func.count(func.distinct(eligible.c.user_id)))
            .select_from(eligible)
            .join(
                actions,
                (actions.c.user_id == eligible.c.user_id)
                & (action_day == eligible.c.target_day),
            )
            .scalar_subquery()
            .label(f"d{offset}_retained"),
        ))
    retention_row = db.session.execute(select(*retention_columns)).one()
    for offset in (1, 7, 30):
        cohort_size = int(getattr(retention_row, f"d{offset}_cohort") or 0)
        retained = int(getattr(retention_row, f"d{offset}_retained") or 0)
        retention[f"d{offset}"] = {
            "percent": round(retained * 100 / cohort_size, 1)
            if cohort_size else 0.0,
            "retained": retained,
            "cohort": cohort_size,
        }
    return {
        "new_users": int(new_users),
        "returning_users": int(returning_users),
        "conversions": int(conversions),
        "conversion_rate": round(conversions * 100 / new_users, 1)
        if new_users else 0.0,
        "retention": retention,
    }


def _period_active_counts(filters: AnalyticsFilters) -> dict[str, int]:
    """Calculate selected-period, daily, weekly, and monthly actives once."""
    end_at = filters.end_at
    starts = {
        "active_users": filters.start_at,
        "dau": end_at - timedelta(days=1),
        "wau": end_at - timedelta(days=7),
        "mau": end_at - timedelta(days=30),
    }
    actions = _filtered_actions(
        filters,
        start_at=min(starts.values()),
        end_at=end_at,
    ).subquery()
    row = db.session.execute(select(*(
        func.count(func.distinct(case(
            (actions.c.datetime >= start_at, actions.c.user_id),
            else_=None,
        ))).label(name)
        for name, start_at in starts.items()
    ))).one()
    return {name: int(getattr(row, name) or 0) for name in starts}


def _item_title(item: PracticeItem) -> str:
    prompt = item.get_prompt().strip()
    return prompt if len(prompt) <= 90 else f"{prompt[:87]}…"


def exercise_query_is_valid(value: str) -> bool:
    """Accept empty searches or queries with at least two letters/digits."""
    return not value.strip() or len(_compact_search(value)) >= 2


def _compact_search(value: str, *, keep_placeholder: bool = False) -> str:
    return normalize_exercise_search(
        value,
        keep_blank=keep_placeholder,
    )


def _exercise_search_condition(search_text, category, item_type, task, query: str):
    needle = _compact_search(query)
    blank_variants = [
        needle[:index] + "_" + needle[index + 1:]
        for index in range(len(needle))
    ]
    metadata = func.lower(func.replace(
        func.coalesce(category, "") + " "
        + item_type + " "
        + func.coalesce(cast(task, String), ""),
        "ё",
        "е",
    ))
    return or_(
        search_text.contains(needle),
        func.replace(search_text, "_", "").contains(needle),
        and_(
            search_text.contains("_", autoescape=True),
            or_(*(search_text.contains(variant) for variant in blank_variants)),
        ),
        metadata.contains(query.casefold().replace("ё", "е")),
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


def _item_statement(filters: AnalyticsFilters):
    """Build the ordered per-exercise aggregate statement."""
    actions = _filtered_actions(filters).subquery()
    right, wrong, skips = _count_expressions(actions)
    aggregates = select(
        actions.c.practice_item_id.label("item_id"),
        func.count(func.distinct(actions.c.user_id)).label("unique_users"),
        right.label("right_count"),
        wrong.label("wrong_count"),
        skips.label("skip_count"),
    ).group_by(actions.c.practice_item_id).subquery()

    item = PracticeItem.__table__
    spelling = SpellingExercise.__table__
    paronym = ParonymExercise.__table__
    category = Category.__table__
    prompt = case(
        (item.c.type == "spelling", spelling.c.word),
        else_=paronym.c.sentence,
    ).label("prompt")
    category_name = func.coalesce(category.c.name, "—").label("category")
    answered = aggregates.c.right_count + aggregates.c.wrong_count
    cards = answered + aggregates.c.skip_count
    accuracy = case(
        (answered > 0, aggregates.c.right_count * 100.0 / answered),
        else_=0.0,
    )
    statement = (
        select(
            item.c.id,
            prompt,
            item.c.type,
            item.c.task_number,
            category_name,
            aggregates.c.unique_users,
            aggregates.c.right_count,
            aggregates.c.wrong_count,
            aggregates.c.skip_count,
        )
        .select_from(
            aggregates
            .join(item, item.c.id == aggregates.c.item_id)
            .outerjoin(spelling, spelling.c.id == item.c.id)
            .outerjoin(paronym, paronym.c.id == item.c.id)
            .outerjoin(category, category.c.id == item.c.category_id)
        )
    )
    if filters.exercise_query:
        statement = statement.where(_exercise_search_condition(
            item.c.search_text,
            category.c.name,
            item.c.type,
            item.c.task_number,
            filters.exercise_query,
        ))
    order = {
        "accuracy": (accuracy.asc(), cards.desc(), item.c.id.asc()),
        "wrong": (aggregates.c.wrong_count.desc(), accuracy.asc(), item.c.id.asc()),
        "skips": (aggregates.c.skip_count.desc(), accuracy.asc(), item.c.id.asc()),
    }[filters.exercise_sort]
    return statement.order_by(*order)


def _serialize_item_row(row) -> dict[str, Any]:
    title = (row.prompt or "").strip()
    return {
        "id": row.id,
        "title": title if len(title) <= 90 else f"{title[:87]}…",
        "full_title": title,
        "type": row.type,
        "task": row.task_number,
        "category": row.category,
        "unique_users": int(row.unique_users),
        **_counts(row.right_count, row.wrong_count, row.skip_count),
    }


def _serialized_items(
    filters: AnalyticsFilters,
    *,
    limit: int | None = 10,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    statement = _item_statement(filters)
    total = int(db.session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ) or 0)
    if limit is not None:
        statement = statement.limit(limit).offset(offset)
    return [
        _serialize_item_row(row)
        for row in db.session.execute(statement)
    ], total


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


def _dashboard_cache_key(filters: AnalyticsFilters) -> str:
    payload = json.dumps(
        filters.as_query() | {"timezone": filters.timezone_name},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"type:analytics:dashboard:{digest}"


def _load_dashboard_cache(filters: AnalyticsFilters) -> dict[str, Any] | None:
    ttl = int(current_app.config.get("ANALYTICS_CACHE_SECONDS", 0))
    storage_uri = current_app.config.get("RATELIMIT_STORAGE_URI", "")
    if ttl <= 0 or not storage_uri.startswith(("redis://", "rediss://")):
        return None
    try:
        cached = Redis.from_url(storage_uri).get(_dashboard_cache_key(filters))
        if not isinstance(cached, (str, bytes, bytearray)):
            return None
        return json.loads(cached)
    except (RedisError, ValueError, TypeError):
        current_app.logger.warning("Analytics cache read failed", exc_info=True)
        return None


def _store_dashboard_cache(
    filters: AnalyticsFilters,
    dashboard: dict[str, Any],
) -> None:
    ttl = int(current_app.config.get("ANALYTICS_CACHE_SECONDS", 0))
    storage_uri = current_app.config.get("RATELIMIT_STORAGE_URI", "")
    if ttl <= 0 or not storage_uri.startswith(("redis://", "rediss://")):
        return
    try:
        Redis.from_url(storage_uri).setex(
            _dashboard_cache_key(filters),
            ttl,
            json.dumps(dashboard, ensure_ascii=False, separators=(",", ":")),
        )
    except (RedisError, TypeError, ValueError):
        current_app.logger.warning("Analytics cache write failed", exc_info=True)


def build_dashboard(filters: AnalyticsFilters) -> dict[str, Any]:
    """Calculate or retrieve all metrics displayed on the dashboard."""
    cached = _load_dashboard_cache(filters)
    if cached is not None:
        return {"filters": filters, **cached}
    counts = _summary_counts(filters)
    active_counts = _period_active_counts(filters)
    active_users = active_counts["active_users"]
    items, item_count = _serialized_items(filters)
    summary = {
        **_audience_counts(filters),
        "active_users": active_users,
        "dau": active_counts["dau"],
        "wau": active_counts["wau"],
        "mau": active_counts["mau"],
        "cards_per_user": round(counts["cards"] / active_users, 1)
        if active_users else 0.0,
        **counts,
        **_session_metrics(filters),
        **_lifecycle_metrics(filters),
    }
    dashboard = {
        "summary": summary,
        "daily": _daily_series(filters),
        "content": {
            "breakdown": _content_breakdown(filters),
            "items": items,
            "item_count": item_count,
        },
    }
    _store_dashboard_cache(filters, dashboard)
    return {"filters": filters, **dashboard}


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


def build_item_export(filters: AnalyticsFilters):
    """Yield per-item aggregates from a server-side streaming result."""
    statement = _item_statement(filters).execution_options(
        stream_results=True,
        yield_per=500,
    )
    for row in db.session.execute(statement):
        yield _serialize_item_row(row)
