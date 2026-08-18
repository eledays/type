from collections.abc import Callable
from functools import wraps
import hmac
import secrets
from typing import Any, TypeVar, cast
from urllib.parse import urlencode, urlsplit

import requests
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from app.extensions import db
from app.models import Settings, User
from app.models.action import Action


View = TypeVar("View", bound=Callable[..., Any])
bp = Blueprint("auth", __name__, url_prefix="/auth")

YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_USER_INFO_URL = "https://login.yandex.ru/info"
OAUTH_TIMEOUT_SECONDS = 10


def load_user(user_id: str) -> User | None:
    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, parsed_user_id)


def admin_required(view: View) -> View:
    """Allow access only to users marked as administrators in the database."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return cast(View, login_required(wrapped))


def _oauth_is_configured() -> bool:
    return bool(
        current_app.config.get("YANDEX_CLIENT_ID")
        and current_app.config.get("YANDEX_CLIENT_SECRET")
    )


def _safe_next_url(value: str | None) -> str:
    """Accept local paths only, preventing redirects to third-party sites."""
    if not value:
        return url_for("user_pages.index")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/"):
        return url_for("user_pages.index")
    return value


def _redirect_uri() -> str:
    return current_app.config.get("YANDEX_REDIRECT_URI") or url_for(
        "auth.yandex_callback", _external=True
    )


@bp.get("")
def login_page():
    if (
        current_user.is_authenticated
        and not current_user.is_anonymous_account
    ):
        return redirect(_safe_next_url(request.args.get("next")))
    return render_template(
        "auth.html",
        oauth_configured=_oauth_is_configured(),
        next_url=_safe_next_url(request.args.get("next")),
    )


@bp.get("/yandex")
def yandex_login():
    if not _oauth_is_configured():
        abort(503, description="Yandex OAuth is not configured")

    state = secrets.token_urlsafe(32)
    session["yandex_oauth_state"] = state
    session["yandex_oauth_next"] = _safe_next_url(request.args.get("next"))
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
    next_url = _safe_next_url(session.pop("yandex_oauth_next", None))

    if (
        not expected_state
        or not received_state
        or not hmac.compare_digest(expected_state, received_state)
    ):
        abort(400, description="Invalid OAuth state")

    if request.args.get("error"):
        flash("Вход через Яндекс был отменён или завершился ошибкой.", "error")
        return redirect(url_for("auth.login_page"))

    code = request.args.get("code")
    if not code or not _oauth_is_configured():
        abort(400, description="Missing OAuth authorization code")

    try:
        token_response = requests.post(
            YANDEX_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _redirect_uri(),
            },
            auth=(
                current_app.config["YANDEX_CLIENT_ID"],
                current_app.config["YANDEX_CLIENT_SECRET"],
            ),
            timeout=OAUTH_TIMEOUT_SECONDS,
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Yandex response has no access token")

        profile_response = requests.get(
            YANDEX_USER_INFO_URL,
            params={"format": "json"},
            headers={"Authorization": f"OAuth {access_token}"},
            timeout=OAUTH_TIMEOUT_SECONDS,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
        if not isinstance(profile, dict):
            raise ValueError("Yandex profile response is not an object")
    except (requests.RequestException, ValueError):
        current_app.logger.exception("Yandex OAuth request failed")
        flash("Не удалось войти через Яндекс. Попробуйте ещё раз.", "error")
        return redirect(url_for("auth.login_page"))

    yandex_id = profile.get("id")
    if not isinstance(yandex_id, (str, int)) or not str(yandex_id):
        current_app.logger.error("Yandex profile response has no user id")
        flash("Яндекс не вернул идентификатор пользователя.", "error")
        return redirect(url_for("auth.login_page"))

    current_account = (
        cast(User, current_user._get_current_object())
        if current_user.is_authenticated
        else None
    )
    user = User.query.filter_by(yandex_id=str(yandex_id)).first()

    if user is None:
        # Converting the current guest keeps all of its actions and settings.
        # A legacy Telegram account can be linked in the same way.
        if current_account is not None and current_account.yandex_id is None:
            user = current_account
        else:
            user = User()
            user.settings = Settings()
            db.session.add(user)
        user.yandex_id = str(yandex_id)
    elif (
        current_account is not None
        and current_account.id != user.id
        and current_account.is_anonymous_account
    ):
        # The Yandex account already exists. Move guest progress before
        # deleting the temporary row; the transaction keeps this atomic.
        Action.query.filter_by(user_id=current_account.id).update(
            {Action.user_id: user.id}, synchronize_session=False
        )
        db.session.delete(current_account)

    login = _profile_text(profile, "login", 255)
    user.yandex_login = login
    user.first_name = _profile_text(profile, "first_name", 255)
    user.last_name = _profile_text(profile, "last_name", 255)
    user.avatar_url = _avatar_url(profile)
    if user.settings is None:
        user.settings = Settings()
    db.session.commit()

    # Drop guest-only cached state after the account switch. OAuth values have
    # already been consumed, so no application state needs to survive it.
    session.clear()
    login_user(user, remember=True)
    return redirect(next_url)


def _profile_text(
    profile: dict[str, Any], key: str, max_length: int
) -> str | None:
    value = profile.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:max_length] if value else None


def _avatar_url(profile: dict[str, Any]) -> str | None:
    """Build the documented public portrait URL from Yandex's avatar id."""
    if profile.get("is_avatar_empty") is True:
        return None
    avatar_id = _profile_text(profile, "default_avatar_id", 255)
    if avatar_id is None:
        return None
    return f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200"


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("user_pages.index"))
