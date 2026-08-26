from typing import cast

from flask import (
    current_app,
    jsonify,
    redirect,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app.extensions import limiter
from app.models import User
from app.routes.profile import api_bp
from app.services.profile import InvalidSettings, get_profile_stats, update_settings
from app.services.backgrounds import choose_background


@api_bp.get("/background")
@login_required
def background():
    """Возвращает случайный фон для старых клиентов.

    :return: Изображение без кэширования для совместимого API.
    """
    user = cast(User, current_user._get_current_object())
    response = send_file(choose_background(user))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@api_bp.get("/stats")
@login_required
def stats():
    """Возвращает статистику профиля по запросу клиентской панели."""
    user = cast(User, current_user._get_current_object())
    return jsonify(get_profile_stats(user))


@api_bp.patch("/settings")
@limiter.limit(
    lambda: current_app.config["RATE_LIMIT_MUTATION"],
    override_defaults=False,
)
@login_required
def patch_settings():
    """Проверяет и изменяет настройки текущего пользователя.

    :return: JSON-ответ о результате изменения.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    user = cast(User, current_user._get_current_object())
    try:
        update_settings(user, payload)
    except PermissionError as error:
        return jsonify({"status": "error", "message": str(error)}), 403
    except InvalidSettings as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    if "admin" in payload:
        session["admin"] = payload["admin"]
    return jsonify({"status": "success"})


@api_bp.get("/avatar")
def avatar():
    """Возвращает аватар текущего пользователя.

    :return: Изображение профиля пользователя.
    """
    if not current_user.is_authenticated or current_user.is_anonymous_account:
        return redirect(url_for("static", filename="img/default_avatar.png"))
    user = cast(User, current_user._get_current_object())
    if user.avatar_url is None:
        return redirect(url_for("static", filename="img/default_avatar.png"))
    return redirect(user.avatar_url)
