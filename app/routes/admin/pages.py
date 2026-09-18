from __future__ import annotations

import csv
import unicodedata
from io import StringIO
from pathlib import Path

from flask import (
    Response,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from flask_login import current_user

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
from app.services.reports import (
    InvalidReport,
    list_error_reports,
    update_error_report,
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


@pages_bp.get("/reports")
@admin_required
def reports():
    """Render the administrator queue of user-submitted error reports."""
    status = request.args.get("status", "open")
    try:
        page = max(1, int(request.args.get("page", "1")))
        report_items, total = list_error_reports(status, page=page)
    except (ValueError, InvalidReport):
        abort(400, description="Invalid report filters")
    return render_template(
        "admin/reports.html",
        reports=report_items,
        total=total,
        status=status,
        page=page,
        has_previous=page > 1,
        has_next=page * 50 < total,
        statuses={
            "open": "Открыт",
            "in_progress": "В работе",
            "resolved": "Решён",
            "rejected": "Отклонён",
        },
        style_url=_static_url("css/style.css"),
        analytics_style_url=_static_url("css/analytics.css"),
        favicon_url=_static_url("img/fav.ico"),
    )


@pages_bp.post("/reports/<int:report_id>")
@limiter.limit(
    lambda: current_app.config["RATE_LIMIT_MUTATION"],
    override_defaults=False,
)
@admin_required
def update_report(report_id: int):
    """Update report status and internal note from the admin queue."""
    try:
        report = update_error_report(
            report_id,
            status=request.form.get("status", ""),
            admin_note=request.form.get("admin_note", ""),
        )
    except InvalidReport as error:
        abort(error.status, description=error.message)
    if report is None:
        abort(404, description="Report not found")
    current_app.logger.info(
        "admin_action=update_report user_id=%s report_id=%s status=%s",
        current_user.get_id(),
        report.id,
        report.status,
    )
    return redirect(url_for(
        "admin.reports",
        status=request.form.get("return_status", "open"),
    ))


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
