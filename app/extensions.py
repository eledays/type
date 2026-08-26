from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user
from flask_login.config import (
    COOKIE_DURATION,
    COOKIE_HTTPONLY,
    COOKIE_NAME,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
)
from flask_login.utils import encode_cookie
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


class TimezoneAwareLoginManager(LoginManager):
    """Совместимый с Python 3.12 менеджер cookie для Flask-Login 0.6.3.

    Исправление уже подготовлено для Flask-Login 0.7.0. После обновления до
    этой версии переопределение можно удалить.
    """

    def _set_cookie(self, response: Any) -> None:
        """Сохраняет cookie сессии только при наличии изменений.

        :param response: Исходящий Flask-ответ.
        :return: ``None``.
        """
        config = current_app.config
        cookie_name = config.get("REMEMBER_COOKIE_NAME", COOKIE_NAME)
        domain = config.get("REMEMBER_COOKIE_DOMAIN")
        path = config.get("REMEMBER_COOKIE_PATH", "/")
        secure = config.get("REMEMBER_COOKIE_SECURE", COOKIE_SECURE)
        httponly = config.get("REMEMBER_COOKIE_HTTPONLY", COOKIE_HTTPONLY)
        samesite = config.get("REMEMBER_COOKIE_SAMESITE", COOKIE_SAMESITE)

        if "_remember_seconds" in session:
            duration = timedelta(seconds=session["_remember_seconds"])
        else:
            duration = config.get(
                "REMEMBER_COOKIE_DURATION", COOKIE_DURATION
            )
        if isinstance(duration, int):
            duration = timedelta(seconds=duration)
        try:
            expires = datetime.now(timezone.utc) + duration
        except TypeError as error:
            raise Exception(
                "REMEMBER_COOKIE_DURATION must be a datetime.timedelta, "
                f"instead got: {duration}"
            ) from error

        response.set_cookie(
            cookie_name,
            value=encode_cookie(str(session["_user_id"])),
            expires=expires,
            domain=domain,
            path=path,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
        )


def rate_limit_key() -> str:
    """Ограничивает зарегистрированных по ID, остальных по IP-адресу."""
    if (
        current_user.is_authenticated
        and not current_user.is_anonymous_account
    ):
        return f"user:{current_user.get_id()}"
    return f"ip:{get_remote_address()}"


db = SQLAlchemy()
migrate = Migrate()
login_manager = TimezoneAwareLoginManager()
limiter = Limiter(key_func=rate_limit_key)
