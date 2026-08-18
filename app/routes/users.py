from datetime import datetime
from typing import cast

from flask import Blueprint, jsonify, render_template, request, session
from flask_login import current_user, login_required, login_user

from app.extensions import db
from app.models import Settings, User, Word
from app.utils import get_user_stats


BOOLEAN_SETTINGS = {"strike", "notification", "day_results"}
TIME_SETTINGS = {"notification_time", "day_results_time"}
bp = Blueprint("users", __name__)


@bp.before_app_request
def ensure_authenticated_user() -> None:
    if request.endpoint == "static":
        return

    user = None
    if current_user.is_authenticated:
        user = cast(User, current_user._get_current_object())
    else:
        legacy_user_id = session.pop("user_id", None)
        if not isinstance(legacy_user_id, bool):
            try:
                parsed_legacy_id = int(legacy_user_id)
            except (TypeError, ValueError):
                parsed_legacy_id = None
            if parsed_legacy_id is not None:
                user = db.session.get(User, parsed_legacy_id)
                if user is None:
                    user = User.query.filter_by(
                        telegram_id=parsed_legacy_id
                    ).first()

    if user is None:
        user = User(settings=Settings())
        db.session.add(user)
        db.session.commit()
        session.clear()
    elif user.settings is None:
        user.settings = Settings()
        db.session.commit()

    if not current_user.is_authenticated:
        login_user(user, remember=True)


@bp.route("/settings")
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
        settings=user.settings,
        admin=admin_mode,
        stats=stats,
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
