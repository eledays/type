from datetime import datetime
from typing import cast

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    session,
)
from flask_login import current_user, login_required, login_user

from app.extensions import db
from app.models import Settings, User, Word
from app.utils import get_user_stats


BOOLEAN_SETTINGS = {"strike", "notification", "day_results"}
TIME_SETTINGS = {"notification_time", "day_results_time"}
bp = Blueprint("users", __name__)


@bp.before_app_request
def ensure_authenticated_user() -> None:
    """Restore a legacy identity or create a browser-bound guest account."""
    if request.endpoint == "static":
        return

    if current_user.is_authenticated:
        return

    legacy_user_id = session.pop("user_id", None)
    if isinstance(legacy_user_id, bool):
        return
    try:
        parsed_legacy_id = int(legacy_user_id)
    except (TypeError, ValueError):
        parsed_legacy_id = None

    user = (
        db.session.get(User, parsed_legacy_id)
        if parsed_legacy_id is not None
        else None
    )
    if user is None and parsed_legacy_id is not None:
        user = User.query.filter_by(telegram_id=parsed_legacy_id).first()
    if user is None:
        user = User(settings=Settings())
        db.session.add(user)
        db.session.commit()
        # The remember cookie lets a guest return later and still merge the
        # accumulated progress when they decide to sign in.
        login_user(user, remember=True)
        return

    if user.settings is None:
        user.settings = Settings()
        db.session.commit()
    login_user(user, remember=not user.is_anonymous_account)


@bp.route("/settings")
@bp.route("/profile")
@login_required
def settings():
    user = cast(User, current_user._get_current_object())
    admin_mode = 0
    if user.is_admin:
        admin_mode = 2 if session.get("admin", False) else 1

    stats = get_user_stats(user.id)
    stats["user_id"] = user.id
    if user.is_admin:
        stats["explanations"] = Word.query.filter(
            Word.explanation.isnot(None)
        ).count()
        stats["users"] = User.query.count()

    return render_template(
        "settings.html",
        user=user,
        settings=user.settings,
        admin=admin_mode,
        stats=stats,
        oauth_configured=bool(
            current_app.config.get("YANDEX_CLIENT_ID")
            and current_app.config.get("YANDEX_CLIENT_SECRET")
        ),
    )


@bp.route("/set_settings", methods=["POST"])
@login_required
def set_settings():
    user = cast(User, current_user._get_current_object())
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    if "admin" in payload:
        if not user.is_admin:
            return jsonify({"status": "error", "message": "Access denied"}), 403
        if set(payload) != {"admin"} or not isinstance(payload["admin"], bool):
            return jsonify({"status": "error", "message": "Invalid admin value"}), 400
        session["admin"] = payload["admin"]
        return jsonify({"status": "success"})

    unknown_fields = set(payload) - BOOLEAN_SETTINGS - TIME_SETTINGS
    if unknown_fields:
        return jsonify({
            "status": "error",
            "message": f"Unknown settings: {', '.join(sorted(unknown_fields))}",
        }), 400

    for field, value in payload.items():
        if field in BOOLEAN_SETTINGS:
            if not isinstance(value, bool):
                return jsonify({
                    "status": "error",
                    "message": f"{field} must be boolean",
                }), 400
        else:
            try:
                value = datetime.strptime(value, "%H:%M").time()
            except (TypeError, ValueError):
                return jsonify({
                    "status": "error",
                    "message": f"{field} must use HH:MM format",
                }), 400

        setattr(user.settings, field, value)

    db.session.commit()
    return jsonify({"status": "success"})
