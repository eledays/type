from flask import current_app, session

from app.extensions import db
from app.models import Action, User, UserPracticeStats


def add_action(
    user_id: int,
    action: int,
    practice_item_id: int,
) -> Action:
    """Создаёт действие пользователя над карточкой практики.

    :param user_id: Идентификатор пользователя.
    :param action: Код выполненного действия.
    :param practice_item_id: Единый идентификатор карточки практики.
    :return: Сохранённая запись действия.
    """
    action_record = Action()
    action_record.user_id = user_id
    action_record.practice_item_id = practice_item_id
    action_record.action = action
    db.session.add(action_record)
    db.session.commit()
    return action_record


def get_anonymous_actions_remaining(user: User) -> int | None:
    """Возвращает остаток анонимной квоты.

    :param user: Пользователь, для которого рассчитывается квота.
    :return: Остаток действий или ``None`` для зарегистрированного пользователя.
    """
    if not user.is_anonymous_account:
        return None
    stats = db.session.get(UserPracticeStats, user.id)
    used = (
        stats.right_count + stats.wrong_count + stats.skip_count
        if stats is not None
        else 0
    )
    limit = int(current_app.config["ANONYMOUS_ACTION_LIMIT"])
    return max(0, limit - used)


def get_strike(user_id: int) -> int:
    """Вычисляет текущую серию верных ответов по истории действий.

    :param user_id: Идентификатор пользователя.
    :return: Количество последовательных верных ответов с конца истории.
    """
    stats = db.session.get(UserPracticeStats, user_id)
    return stats.current_streak if stats is not None else 0


def get_cached_strike(user_id: int) -> int:
    """Возвращает серию из сессии или вычисляет её при первом обращении.

    :param user_id: Идентификатор пользователя.
    :return: Текущая длина серии.
    """
    if "strike" not in session:
        session["strike"] = get_strike(user_id)
    return int(session["strike"])


def get_user_stats(user_id: int) -> dict[str, int | float]:
    """Рассчитывает сводную статистику практики пользователя.

    :param user_id: Идентификатор пользователя.
    :return: Количество ответов и пропусков, точность, темп и лучшая серия.
    """
    stats = db.session.get(UserPracticeStats, user_id)
    correct = stats.right_count if stats is not None else 0
    mistakes = stats.wrong_count if stats is not None else 0
    skips = stats.skip_count if stats is not None else 0
    best_streak = stats.best_streak if stats is not None else 0

    answered = correct + mistakes
    percent_correct = (correct / answered * 100) if answered else 0
    average_seconds = (
        stats.active_seconds / stats.timed_intervals
        if stats is not None and stats.timed_intervals
        else 0
    )

    return {
        "correct": correct,
        "mistakes": mistakes,
        "skips": skips,
        "correct_percent": round(percent_correct, 1),
        "avg_time_per_word": round(average_seconds, 1),
        "best_streak": best_streak,
    }
