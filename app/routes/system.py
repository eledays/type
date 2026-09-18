import hmac
import os

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    request,
    url_for,
)
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db, limiter
from app.observability import DEPENDENCY_UP

bp = Blueprint("system", __name__)


@bp.get("/health/live")
@limiter.exempt
def liveness():
    """Подтверждает, что HTTP-процесс принимает запросы."""
    return jsonify({"status": "ok"})


@bp.get("/health/ready")
@limiter.exempt
def readiness():
    """Проверяет доступность PostgreSQL и Redis."""
    available = True
    try:
        db.session.execute(text("SELECT 1"))
        DEPENDENCY_UP.labels("database").set(1)
    except SQLAlchemyError:
        available = False
        DEPENDENCY_UP.labels("database").set(0)
        db.session.rollback()
        current_app.logger.warning(
            "readiness_check_failed",
            extra={
                "event": "readiness_check_failed",
                "dependency": "database",
            },
            exc_info=True,
        )
    try:
        redis_client = Redis.from_url(
            current_app.config["RATELIMIT_STORAGE_URI"],
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        redis_client.ping()
        DEPENDENCY_UP.labels("redis").set(1)
    except (RedisError, ValueError):
        available = False
        DEPENDENCY_UP.labels("redis").set(0)
        current_app.logger.warning(
            "readiness_check_failed",
            extra={
                "event": "readiness_check_failed",
                "dependency": "redis",
            },
            exc_info=True,
        )
    if not available:
        return jsonify({"status": "unavailable"}), 503
    return jsonify({"status": "ok"})


@bp.get("/metrics")
@limiter.exempt
def metrics():
    """Expose token-protected Prometheus metrics for the operator."""
    expected = current_app.config.get("METRICS_TOKEN")
    supplied = request.headers.get("Authorization", "")
    authorized = bool(
        expected
        and supplied.startswith("Bearer ")
        and hmac.compare_digest(supplied[7:], expected)
    )
    if not authorized:
        return Response(
            "Authentication required\n",
            status=401,
            headers={"WWW-Authenticate": "Bearer"},
            content_type="text/plain; charset=utf-8",
        )
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = REGISTRY
    return Response(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)


@bp.get("/favicon.ico")
def favicon():
    """Перенаправляет стандартный адрес favicon на статический файл.

    :return: Перенаправление к иконке приложения.
    """
    return redirect(url_for("static", filename="img/fav.ico"), code=308)
