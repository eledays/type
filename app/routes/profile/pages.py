from typing import cast

from flask import current_app, render_template, session
from flask_login import current_user, login_required

from app.models import User
from app.routes.profile import bp
from app.services.auth import oauth_is_configured
from app.services.profile import get_profile_stats


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
    stats = get_profile_stats(user)
    return render_template(
        "settings.html",
        user=user,
        settings=user.settings,
        admin=admin_mode,
        stats=stats,
        oauth_configured=oauth_is_configured(),
    )
