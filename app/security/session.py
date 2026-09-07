from flask import current_app, jsonify, redirect, request, session, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_user

from app.extensions import db
from app.models import Settings, User
from app.services.auth import safe_next_url
from app.services.legal import (
    create_anonymous_user,
    has_current_legal_acceptance,
)


def load_user(user_id: str) -> User | None:
    """Загружает пользователя для Flask-Login.

    :param user_id: Строковый идентификатор из пользовательской сессии.
    :return: Пользователь или ``None`` при некорректном идентификаторе.
    """
    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, parsed_user_id)


def ensure_authenticated_user() -> None:
    """Создаёт временного пользователя для нового браузера.

    :return: ``None``.
    """
    sessionless_endpoints = {
        "static",
        "system.liveness",
        "system.readiness",
        "legal.terms",
        "legal.privacy",
        "legal.personal_data_consent",
        "legal.consent",
    }
    if (
        request.endpoint in sessionless_endpoints
        or current_user.is_authenticated
    ):
        return
    if current_app.config.get("LEGAL_CONSENT_REQUIRED", True):
        return

    authenticate_browser_user()


def authenticate_browser_user() -> User:
    """Restore a legacy profile or create and log in an anonymous profile."""
    if current_user.is_authenticated:
        return current_user._get_current_object()

    legacy_user_id = session.pop("user_id", None)
    if isinstance(legacy_user_id, bool):
        legacy_user_id = None
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
        user = create_anonymous_user()
        db.session.commit()
        login_user(user, remember=True)
        return user

    if user.settings is None:
        user.settings = Settings()
        db.session.commit()
    login_user(user, remember=not user.is_anonymous_account)
    return user


def require_current_legal_acceptance() -> ResponseReturnValue | None:
    """Block every non-public application endpoint until explicit consent."""
    if not current_app.config.get("LEGAL_CONSENT_REQUIRED", True):
        return None
    public_endpoints = {
        "static",
        "system.liveness",
        "system.readiness",
        "system.favicon",
        "legal.terms",
        "legal.privacy",
        "legal.personal_data_consent",
        "legal.consent",
        "legal.accept_consent",
    }
    if request.endpoint in public_endpoints:
        return None
    accepted = current_user.is_authenticated and has_current_legal_acceptance(
        current_user._get_current_object()
    )
    if accepted:
        return None
    consent_url = url_for(
        "legal.consent",
        next=safe_next_url(request.full_path.rstrip("?")),
    )
    if request.path.startswith("/api/"):
        return jsonify({
            "error": "legal_consent_required",
            "message": "Legal consent is required before using the service",
            "consent_url": consent_url,
        }), 403
    return redirect(consent_url)
