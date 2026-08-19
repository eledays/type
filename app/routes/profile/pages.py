from typing import cast

from flask import current_app, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.models import User, Word
from app.routes.profile import bp
from app.services.auth import oauth_is_configured
from app.utils import get_user_stats


@bp.get("/profile")
@login_required
def index():
    """Отображает профиль, настройки и статистику пользователя.

    :return: HTML-страница профиля.
    """
    user = cast(User, current_user._get_current_object())
    admin_mode = (
        2
        if user.is_admin and session.get("admin", False)
        else int(user.is_admin)
    )
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
        oauth_configured=oauth_is_configured(),
    )


@bp.get("/settings")
def legacy_settings_redirect():
    """Перенаправляет старый адрес настроек на профиль.

    :return: Постоянное перенаправление на страницу профиля.
    """
    query = request.query_string.decode()
    target = url_for("profile.index")
    return redirect(f"{target}?{query}" if query else target, code=308)
