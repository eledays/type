from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from flask import abort
from flask_login import current_user, login_required


View = TypeVar("View", bound=Callable[..., Any])


def admin_required(view: View) -> View:
    """Allow access only to authenticated database administrators."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return cast(View, login_required(wrapped))
