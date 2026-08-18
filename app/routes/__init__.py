from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.routes.admin import bp as admin_bp
    from app.routes.core import bp as core_bp
    from app.routes.filters import bp as filters_bp
    from app.routes.user_pages import bp as user_pages_bp
    from app.routes.users import bp as users_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(core_bp)
    app.register_blueprint(filters_bp)
    app.register_blueprint(user_pages_bp)
    app.register_blueprint(users_bp)
