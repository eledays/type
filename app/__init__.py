from collections.abc import Mapping
from typing import Any

from flask import Flask, request

from app.extensions import db, migrate, login_manager

from config import settings


def create_app(config: Mapping[str, Any] | None = None) -> Flask:
    """Создаёт и настраивает экземпляр Flask-приложения.

    :param config: Необязательные значения, переопределяющие базовую конфигурацию.
    :return: Полностью настроенное Flask-приложение.
    """
    app = Flask(__name__)
    app.config.from_mapping(settings.to_flask_config())
    if config is not None:
        app.config.from_mapping(config)

    db.init_app(app)
    migrate.init_app(
        app,
        db,
        compare_type=True,
        render_as_batch=True,
    )
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = None

    from app.cli import register_commands
    from app.routes import register_blueprints
    from app.security.session import ensure_authenticated_user, load_user

    login_manager.user_loader(load_user)
    app.before_request(ensure_authenticated_user)
    register_commands(app)
    register_blueprints(app)

    @app.after_request
    def cache_versioned_static_assets(response):
        """Назначает долгий кэш версионированным статическим ресурсам.

        :param response: Исходящий Flask-ответ.
        :return: Ответ с обновлённым заголовком ``Cache-Control``.
        """
        if (
            request.path.startswith("/static/img/backs/")
            or (
                request.path.startswith("/static/")
                and request.args.get("v")
            )
        ):
            response.headers["Cache-Control"] = (
                "public, max-age=31536000, immutable"
            )
        return response

    return app
