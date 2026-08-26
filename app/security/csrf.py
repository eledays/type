from datetime import timedelta
from typing import Any

from flask import Flask, current_app, jsonify, request, session
from werkzeug.datastructures import MultiDict
from wtforms import Form
from wtforms.csrf.session import SessionCSRF


class CSRFForm(Form):
    """Связывает CSRF-токен WTForms с Flask-сессией."""

    class Meta:
        csrf = True
        csrf_class = SessionCSRF
        csrf_time_limit = timedelta(hours=1)

        @property
        def csrf_secret(self) -> bytes:
            """Возвращает секрет приложения в формате WTForms."""
            secret = current_app.secret_key
            if not secret:
                raise RuntimeError("SECRET_KEY is required for CSRF protection")
            return secret.encode("utf-8") if isinstance(secret, str) else secret

        @property
        def csrf_context(self) -> Any:
            """Использует Flask-сессию как хранилище CSRF."""
            return session


def generate_csrf_token() -> str:
    """Создаёт токен для HTML-форм и JavaScript-запросов."""
    return CSRFForm().csrf_token.current_token


def _submitted_token() -> MultiDict[str, str]:
    """Извлекает токен из формы или заголовка JSON-запроса."""
    token = request.form.get("csrf_token") or request.headers.get(
        "X-CSRFToken", ""
    )
    return MultiDict({"csrf_token": token})


def register_csrf(app: Flask) -> None:
    """Включает WTForms CSRF для всех изменяющих запросов."""
    app.jinja_env.globals["csrf_token"] = generate_csrf_token

    @app.before_request
    def protect_from_csrf():
        if (
            not current_app.config.get("WTF_CSRF_ENABLED", True)
            or request.method not in {"POST", "PUT", "PATCH", "DELETE"}
        ):
            return None

        form = CSRFForm(_submitted_token())
        if form.validate():
            return None

        message = form.csrf_token.errors[0]
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "csrf_failed",
                "message": message,
            }), 400
        return message, 400
