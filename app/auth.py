from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from flask import abort
from flask_login import current_user, login_required

from app.extensions import db
from app.models import User


View = TypeVar("View", bound=Callable[..., Any])


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
