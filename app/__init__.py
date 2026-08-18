from collections.abc import Mapping
from typing import Any

from flask import Flask
from app.extensions import db, migrate, login_manager

from config import settings


def create_app(config: Mapping[str, Any] | None = None) -> Flask:
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

    from app.auth import load_user
    from app.cli import register_commands
    from app.routes import register_blueprints

    login_manager.user_loader(load_user)
    register_commands(app)
    register_blueprints(app)

    return app
