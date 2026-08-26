from flask import Blueprint, current_app, jsonify, redirect, url_for
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db, limiter


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
    try:
        db.session.execute(text("SELECT 1"))
        redis_client = Redis.from_url(
            current_app.config["RATELIMIT_STORAGE_URI"],
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        redis_client.ping()
    except (SQLAlchemyError, RedisError, ValueError):
        db.session.rollback()
        current_app.logger.warning(
            "Readiness dependency check failed", exc_info=True
        )
        return jsonify({"status": "unavailable"}), 503
    return jsonify({"status": "ok"})


@bp.get("/favicon.ico")
def favicon():
    """Перенаправляет стандартный адрес favicon на статический файл.

    :return: Перенаправление к иконке приложения.
    """
    return redirect(url_for("static", filename="img/fav.ico"), code=308)
