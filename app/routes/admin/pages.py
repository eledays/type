from __future__ import annotations

import csv
import unicodedata
from io import StringIO
from pathlib import Path

from flask import (
    Response,
    current_app,
    render_template,
    request,
    stream_with_context,
    url_for,
)

from app.extensions import limiter
from app.models import Category
from app.routes.admin import pages_bp
from app.security.decorators import admin_required
from app.services.analytics import (
    build_dashboard,
    build_item_export,
    exercise_query_is_valid,
    parse_filters,
)


def _static_url(filename: str) -> str:
    path = Path(current_app.static_folder or "app/static") / filename
    return url_for("static", filename=filename, v=path.stat().st_mtime_ns)


def _format_duration(seconds: int | float) -> str:
    rounded = max(0, round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} ч {minutes} мин"
    if minutes:
        return f"{minutes} мин {secs} сек"
    return f"{secs} сек"


@pages_bp.get("/analytics")
@admin_required
def analytics():
    """Render the private product and learning analytics dashboard."""
    filters = parse_filters(request.args)
    if not exercise_query_is_valid(filters.exercise_query):
        filters = parse_filters({
            key: value
            for key, value in request.args.items()
            if key != "exercise_query"
        })
    dashboard = build_dashboard(filters)
    query = filters.as_query()
    return render_template(
        "admin/analytics.html",
        **dashboard,
        categories=Category.query.order_by(Category.name).all(),
        tasks=current_app.config["TASKS"],
        query=query,
        exercise_query=filters.exercise_query,
        search_reset_query={
            key: value
            for key, value in query.items()
            if key != "exercise_query"
        },
        sort_queries={
            sort: query | {"exercise_sort": sort}
            for sort in ("accuracy", "wrong", "skips")
        },
        format_duration=_format_duration,
        style_url=_static_url("css/style.css"),
        analytics_style_url=_static_url("css/analytics.css"),
        analytics_search_script_url=_static_url("js/analytics-search.js"),
        analytics_script_url=_static_url("js/analytics.js"),
        favicon_url=_static_url("img/fav.ico"),
    )


@pages_bp.get("/analytics.csv")
@limiter.limit(
    lambda: current_app.config["RATE_LIMIT_ANALYTICS_EXPORT"],
    override_defaults=False,
)
@admin_required
def analytics_csv():
    """Export per-exercise analytics matching the current filters."""
    filters = parse_filters(request.args)

    def generate_rows():
        output = StringIO()
        writer = csv.writer(output)

        def encode(row: list[object]) -> str:
            writer.writerow(row)
            value = output.getvalue()
            output.seek(0)
            output.truncate(0)
            return value

        yield "\ufeff"
        yield encode([
            "item_id", "title", "type", "task", "category",
            "unique_users", "cards", "right", "wrong", "skips",
            "accuracy_percent",
        ])
        for item in build_item_export(filters):
            yield encode([
                item["id"],
                _csv_safe(item["full_title"]),
                _csv_safe(item["type"]),
                item["task"] or "",
                _csv_safe(item["category"]),
                item["unique_users"],
                item["cards"],
                item["right"],
                item["wrong"],
                item["skips"],
                item["accuracy"],
            ])

    filename = f"analytics-{filters.start}-{filters.end}.csv"
    return Response(
        stream_with_context(generate_rows()),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _csv_safe(value: object) -> object:
    """Prevent spreadsheet programs from evaluating exported text as formulas."""
    if not isinstance(value, str) or not value:
        return value
    first_meaningful = next((
        character
        for character in value
        if not character.isspace()
        and character != "\ufeff"
        and unicodedata.category(character) != "Cf"
    ), "")
    if first_meaningful in {"=", "+", "-", "@"}:
        return f"'{value}"
    return value
