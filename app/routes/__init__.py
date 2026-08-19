from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.routes.admin import bp as admin_api_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.legacy import bp as legacy_bp
    from app.routes.practice import api_bp as practice_api_bp
    from app.routes.practice import bp as practice_bp
    from app.routes.profile import api_bp as profile_api_bp
    from app.routes.profile import bp as profile_bp
    from app.routes.system import bp as system_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(practice_bp)
    app.register_blueprint(practice_api_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(profile_api_bp)
    app.register_blueprint(admin_api_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(legacy_bp)
