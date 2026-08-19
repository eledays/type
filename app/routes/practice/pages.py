from typing import cast

from flask import current_app, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.models import Category, User
from app.routes.practice import bp
from app.services.practice import PracticeError, select_card
from app.utils import get_anonymous_actions_remaining, get_cached_strike


@bp.get("/")
@login_required
def index():
    user = cast(User, current_user._get_current_object())
    card_url = url_for(
        "practice.next_card",
        task=request.args.get("task"),
        category=request.args.get("category"),
        mode=request.args.get("mode"),
    )
    return render_template(
        "index.html",
        strike=get_cached_strike(user.id) if user.settings.strike else None,
        anonymous_remaining=get_anonymous_actions_remaining(user),
        card_url=card_url,
    )


@bp.get("/filters")
def filters():
    return render_template(
        "filters.html",
        categories=Category.query.all(),
        tasks=current_app.config["TASKS"],
    )


@bp.get("/practice/cards/next")
@login_required
def next_card():
    user = cast(User, current_user._get_current_object())
    try:
        card = select_card(
            user,
            task_id=request.args.get("task", ""),
            category_id=request.args.get("category", ""),
            mistakes=request.args.get("mode") == "mistakes",
        )
    except PracticeError as error:
        return error.message, error.status
    return render_template(
        "frame_inner.html",
        word=card.note,
        info_str=card.info,
        admin=user.is_admin and session.get("admin", False),
        demo=False,
    )
