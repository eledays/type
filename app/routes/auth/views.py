from urllib.parse import urlencode
import secrets

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.routes.auth import bp
from app.services.auth import (
    OAuthError,
    authenticate_yandex,
    oauth_is_configured,
    safe_next_url,
    validate_state,
)


YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"


def _redirect_uri() -> str:
    return current_app.config.get("YANDEX_REDIRECT_URI") or url_for(
        "auth.yandex_callback", _external=True
    )


@bp.get("")
def login():
    next_url = safe_next_url(request.args.get("next"))
    if current_user.is_authenticated and not current_user.is_anonymous_account:
        return redirect(next_url)
    return render_template(
        "auth.html", oauth_configured=oauth_is_configured(), next_url=next_url
    )


@bp.get("/yandex")
def yandex_login():
    if not oauth_is_configured():
        abort(503, description="Yandex OAuth is not configured")
    state = secrets.token_urlsafe(32)
    session["yandex_oauth_state"] = state
    session["yandex_oauth_next"] = safe_next_url(request.args.get("next"))
    query = urlencode({
        "response_type": "code",
        "client_id": current_app.config["YANDEX_CLIENT_ID"],
        "redirect_uri": _redirect_uri(),
        "state": state,
    })
    return redirect(f"{YANDEX_AUTHORIZE_URL}?{query}")


@bp.get("/yandex/callback")
def yandex_callback():
    expected_state = session.pop("yandex_oauth_state", None)
    received_state = request.args.get("state")
    next_url = safe_next_url(session.pop("yandex_oauth_next", None))
    if not validate_state(expected_state, received_state):
        abort(400, description="Invalid OAuth state")
    if request.args.get("error"):
        flash(
            "Вход через Яндекс был отменён или завершился ошибкой.",
            "error",
        )
        return redirect(url_for("auth.login"))
    code = request.args.get("code")
    if not code or not oauth_is_configured():
        abort(400, description="Missing OAuth authorization code")
    try:
        user = authenticate_yandex(code, _redirect_uri())
    except OAuthError:
        current_app.logger.exception("Yandex OAuth request failed")
        flash(
            "Не удалось войти через Яндекс. Попробуйте ещё раз.",
            "error",
        )
        return redirect(url_for("auth.login"))
    session.clear()
    login_user(user, remember=True)
    return redirect(next_url)


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    logout_user()
    return redirect(url_for("practice.index"))
