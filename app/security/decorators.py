from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from flask import abort
from flask_login import current_user, login_required


View = TypeVar("View", bound=Callable[..., Any])


def admin_required(view: View) -> View:
    """Ограничивает обработчик активным административным режимом.

    :param view: Защищаемый Flask-обработчик.
    :return: Обёрнутый обработчик с проверкой прав.
    """
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        """Проверяет права и вызывает исходный обработчик.

        :param args: Позиционные аргументы исходного обработчика.
        :param kwargs: Именованные аргументы исходного обработчика.
        :return: Результат исходного обработчика или ответ с кодом 403.
        """
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return cast(View, login_required(wrapped))
