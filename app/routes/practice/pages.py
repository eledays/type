from pathlib import Path
from typing import cast

from flask import current_app, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.models import Category, User
from app.routes.practice import bp
from app.services.auth import oauth_is_configured
from app.services.backgrounds import choose_background
from app.services.practice import (
    PracticeError,
    select_cards,
    serialize_cards,
)
from app.services.profile import get_profile_stats
from app.utils import (
    get_anonymous_actions_remaining,
    get_cached_strike,
)


@bp.get("/")
@login_required
def index():
    """Отображает однодокументную ленту с начальным пакетом карточек.

    :return: HTML-страница практики.
    """
    user = cast(User, current_user._get_current_object())
    task = request.args.get("task", "")
    category = request.args.get("category", "")
    mode = request.args.get("mode", "")
    admin = user.is_admin and session.get("admin", False)
    initial_error = None
    try:
        selected_cards = select_cards(
            user,
            int(current_app.config["PRACTICE_CARD_BATCH_SIZE"]),
            task_id=task,
            category_id=category,
            mistakes=mode == "mistakes",
        )
        initial_cards = serialize_cards(
            selected_cards, user.id, admin=admin
        )
    except PracticeError as error:
        initial_cards = []
        initial_error = error.message

    background = choose_background(user)
    stats = get_profile_stats(user)
    static_root = current_app.static_folder

    def static_url(filename: str) -> str:
        """Формирует версионированный URL статического ресурса.

        :param filename: Путь ресурса относительно каталога ``static``.
        :return: URL с версией на основе времени изменения файла.
        """
        path = Path(static_root or "app/static") / filename
        return url_for(
            "static",
            filename=filename,
            v=path.stat().st_mtime_ns,
        )

    background_name = (
        background.relative_to(static_root).as_posix()
        if static_root is not None
        else background.as_posix()
    )
    background_root = background.parent.parent
    background_pools = {
        theme: [
            url_for(
                "static",
                filename=path.relative_to(static_root).as_posix(),
                v=path.stat().st_mtime_ns,
            )
            for path in sorted((background_root / theme).glob("*.webp"))
        ]
        for theme in ("dark", "yellow")
    }
    return render_template(
        "index.html",
        strike=get_cached_strike(user.id) if user.settings.strike else None,
        anonymous_remaining=get_anonymous_actions_remaining(user),
        initial_cards=initial_cards,
        initial_error=initial_error,
        admin=admin,
        background_url=url_for(
            "static",
            filename=background_name,
            v=background.stat().st_mtime_ns,
        ),
        feed_query={"task": task, "category": category, "mode": mode},
        strike_levels=current_app.config["STRIKE_LEVELS"],
        background_pools=background_pools,
        card_batch_size=current_app.config["PRACTICE_CARD_BATCH_SIZE"],
        categories=Category.query.all(),
        tasks=current_app.config["TASKS"],
        user=user,
        settings=user.settings,
        stats=stats,
        oauth_configured=oauth_is_configured(),
        style_url=static_url("css/style.css"),
        index_style_url=static_url("css/index.css"),
        feed_script_url=static_url("js/feed.js"),
        favicon_url=static_url("img/fav.ico"),
    )


@bp.get("/filters")
def filters():
    """Отображает страницу выбора фильтров практики.

    :return: HTML-страница со списком категорий и заданий.
    """
    return render_template(
        "filters.html",
        categories=Category.query.all(),
        tasks=current_app.config["TASKS"],
    )
