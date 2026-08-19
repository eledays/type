import hmac
from typing import Any, cast
from urllib.parse import urlsplit

import requests
from flask import current_app
from flask_login import current_user

from app.extensions import db
from app.models import Settings, User
from app.models.action import Action


YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_USER_INFO_URL = "https://login.yandex.ru/info"
OAUTH_TIMEOUT_SECONDS = 10


class OAuthError(RuntimeError):
    pass


def oauth_is_configured() -> bool:
    """Проверяет наличие обязательных параметров Яндекс OAuth.

    :return: ``True``, если идентификатор и секрет клиента настроены.
    """
    return bool(
        current_app.config.get("YANDEX_CLIENT_ID")
        and current_app.config.get("YANDEX_CLIENT_SECRET")
    )


def safe_next_url(value: str | None) -> str:
    """Оставляет только безопасный локальный URL перенаправления.

    :param value: URL, полученный от клиента.
    :return: Безопасный локальный URL или корневой путь.
    """
    if not value:
        return "/"
    parsed = urlsplit(value)
    is_local = (
        not parsed.scheme
        and not parsed.netloc
        and value.startswith("/")
    )
    return value if is_local else "/"


def validate_state(expected: str | None, received: str | None) -> bool:
    """Сравнивает ожидаемое и полученное состояние OAuth.

    :param expected: Значение из пользовательской сессии.
    :param received: Значение из callback-запроса.
    :return: Результат безопасного сравнения значений.
    """
    return bool(expected and received and hmac.compare_digest(expected, received))


def authenticate_yandex(code: str, redirect_uri: str) -> User:
    """Обменивает OAuth-код на профиль и авторизует пользователя.

    :param code: Одноразовый код авторизации Яндекса.
    :param redirect_uri: Callback URL текущего приложения.
    :return: Созданный или найденный пользователь.
    :raises OAuthError: Если Яндекс вернул ошибочный ответ.
    """
    try:
        token_response = requests.post(
            YANDEX_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
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
    except (requests.RequestException, ValueError) as error:
        raise OAuthError("Yandex OAuth request failed") from error

    yandex_id = profile.get("id")
    if not isinstance(yandex_id, (str, int)) or not str(yandex_id):
        raise OAuthError("Yandex profile response has no user id")
    return _merge_yandex_profile(profile, str(yandex_id))


def _merge_yandex_profile(profile: dict[str, Any], yandex_id: str) -> User:
    """Объединяет профиль Яндекса с текущим локальным аккаунтом.

    :param profile: Проверенный ответ API профиля Яндекса.
    :param yandex_id: Нормализованный идентификатор Яндекса.
    :return: Сохранённый пользователь приложения.
    """
    current_account = (
        cast(User, current_user._get_current_object())
        if current_user.is_authenticated
        else None
    )
    user = User.query.filter_by(yandex_id=yandex_id).first()
    if user is None:
        if current_account is not None and current_account.yandex_id is None:
            user = current_account
        else:
            user = User(settings=Settings())
            db.session.add(user)
        user.yandex_id = yandex_id
    elif (
        current_account is not None
        and current_account.id != user.id
        and current_account.is_anonymous_account
    ):
        Action.query.filter_by(user_id=current_account.id).update(
            {Action.user_id: user.id}, synchronize_session=False
        )
        db.session.delete(current_account)

    user.yandex_login = _profile_text(profile, "login", 255)
    user.first_name = _profile_text(profile, "first_name", 255)
    user.last_name = _profile_text(profile, "last_name", 255)
    user.avatar_url = _avatar_url(profile)
    if user.settings is None:
        user.settings = Settings()
    db.session.commit()
    return user


def _profile_text(
    profile: dict[str, Any], key: str, max_length: int
) -> str | None:
    """Извлекает и ограничивает текстовое поле профиля.

    :param profile: Данные профиля Яндекса.
    :param key: Имя извлекаемого поля.
    :param max_length: Максимальная длина результата.
    :return: Очищенный текст или ``None``.
    """
    value = profile.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:max_length] if value else None


def _avatar_url(profile: dict[str, Any]) -> str | None:
    """Формирует URL аватара из данных профиля.

    :param profile: Данные профиля Яндекса.
    :return: URL аватара или ``None`` при его отсутствии.
    """
    if profile.get("is_avatar_empty") is True:
        return None
    avatar_id = _profile_text(profile, "default_avatar_id", 255)
    if avatar_id is None:
        return None
    return f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200"
