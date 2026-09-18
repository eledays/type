from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from flask import Flask, g, request
from prometheus_client import Counter, Gauge, Histogram

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

HTTP_REQUESTS = Counter(
    "type_http_requests_total",
    "Completed HTTP requests.",
    ("method", "endpoint", "status"),
)
HTTP_DURATION = Histogram(
    "type_http_request_duration_seconds",
    "HTTP request duration.",
    ("method", "endpoint"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
HTTP_IN_PROGRESS = Gauge(
    "type_http_requests_in_progress",
    "HTTP requests currently being processed.",
    multiprocess_mode="livesum",
)
UNHANDLED_EXCEPTIONS = Counter(
    "type_unhandled_exceptions_total",
    "Unhandled request exceptions.",
    ("endpoint", "exception"),
)
DEPENDENCY_UP = Gauge(
    "type_dependency_up",
    "Whether an application dependency passed its latest readiness check.",
    ("dependency",),
    multiprocess_mode="max",
)

LOG_FIELDS = (
    "event",
    "request_id",
    "method",
    "path",
    "endpoint",
    "status_code",
    "duration_ms",
    "dependency",
)


class JsonFormatter(logging.Formatter):
    """Render one structured JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _endpoint() -> str:
    return request.url_rule.rule if request.url_rule is not None else "unmatched"


def configure_observability(app: Flask) -> None:
    """Install request correlation, HTTP metrics, and structured logging."""
    if app.config.get("LOG_FORMAT") == "json" and not app.testing:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        app.logger.handlers.clear()
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        app.logger.propagate = False

    @app.before_request
    def start_observation() -> None:
        supplied_id = request.headers.get("X-Request-ID", "")
        g.request_id = (
            supplied_id
            if REQUEST_ID_PATTERN.fullmatch(supplied_id)
            else str(uuid4())
        )
        g.request_started_at = perf_counter()
        HTTP_IN_PROGRESS.inc()

    @app.after_request
    def finish_observation(response):
        duration = perf_counter() - g.get("request_started_at", perf_counter())
        endpoint = _endpoint()
        HTTP_IN_PROGRESS.dec()
        HTTP_REQUESTS.labels(
            request.method, endpoint, str(response.status_code)
        ).inc()
        HTTP_DURATION.labels(request.method, endpoint).observe(duration)
        response.headers["X-Request-ID"] = g.get("request_id", str(uuid4()))
        if not app.testing:
            app.logger.info(
                "request_completed",
                extra={
                    "event": "request_completed",
                    "request_id": g.get("request_id"),
                    "method": request.method,
                    "path": request.path,
                    "endpoint": endpoint,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 3),
                },
            )
        return response

    from flask import got_request_exception

    @got_request_exception.connect_via(app, weak=False)
    def record_exception(_sender: Flask, exception: BaseException, **_extra) -> None:
        UNHANDLED_EXCEPTIONS.labels(
            _endpoint(), type(exception).__name__
        ).inc()
        app.logger.error(
            "request_failed",
            extra={
                "event": "request_failed",
                "request_id": g.get("request_id"),
                "method": request.method,
                "path": request.path,
                "endpoint": _endpoint(),
            },
            exc_info=(type(exception), exception, exception.__traceback__),
        )


def prometheus_multiprocess_enabled() -> bool:
    """Return whether metrics use the Gunicorn multiprocess directory."""
    return bool(os.environ.get("PROMETHEUS_MULTIPROC_DIR"))
