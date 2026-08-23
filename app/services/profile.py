from datetime import datetime
from typing import Any

from app.extensions import db
from app.models import SpellingExercise, User
from app.utils import get_user_stats


BOOLEAN_SETTINGS = {"strike", "notification", "day_results"}
TIME_SETTINGS = {"notification_time", "day_results_time"}


class InvalidSettings(ValueError):
    pass


def get_profile_stats(user: User) -> dict[str, int | float]:
    """Возвращает статистику для профиля, включая показатели администратора."""
    stats = get_user_stats(user.id)
    stats["user_id"] = user.id
    if user.is_admin:
        stats["explanations"] = SpellingExercise.query.filter(
            SpellingExercise.explanation.isnot(None)
        ).count()
        stats["users"] = User.query.count()
    return stats


def update_settings(user: User, payload: dict[str, Any]) -> None:
    """Проверяет и сохраняет настройки пользователя.

    :param user: Пользователь, чьи настройки изменяются.
    :param payload: Словарь изменяемых полей и значений.
    :return: ``None``.
    :raises PermissionError: Если недоступный пользователь включает админ-режим.
    :raises InvalidSettings: Если поля или значения не прошли проверку.
    """
    if "admin" in payload:
        if not user.is_admin:
            raise PermissionError("Access denied")
        if set(payload) != {"admin"} or not isinstance(payload["admin"], bool):
            raise InvalidSettings("Invalid admin value")
        return

    unknown_fields = set(payload) - BOOLEAN_SETTINGS - TIME_SETTINGS
    if unknown_fields:
        raise InvalidSettings(
            f"Unknown settings: {', '.join(sorted(unknown_fields))}"
        )

    for field, value in payload.items():
        if field in BOOLEAN_SETTINGS:
            if not isinstance(value, bool):
                raise InvalidSettings(f"{field} must be boolean")
        else:
            try:
                value = datetime.strptime(value, "%H:%M").time()
            except (TypeError, ValueError) as error:
                raise InvalidSettings(f"{field} must use HH:MM format") from error
        setattr(user.settings, field, value)

    db.session.commit()
