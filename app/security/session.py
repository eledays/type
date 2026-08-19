from flask import request, session
from flask_login import current_user, login_user

from app.extensions import db
from app.models import Settings, User


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
    if request.endpoint == "static" or current_user.is_authenticated:
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
        user = User()
        user.settings = Settings()
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        return

    if user.settings is None:
        user.settings = Settings()
        db.session.commit()
    login_user(user, remember=not user.is_anonymous_account)
