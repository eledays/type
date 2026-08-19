from datetime import timedelta

from flask import current_app, session
from sqlalchemy import desc, select

from app.extensions import db
from app.models import Action, User


def add_action(
    user_id: int,
    action: int,
    word_id: int | None = None,
    sentence_id: int | None = None,
) -> Action:
    """Создаёт действие пользователя над словом или предложением.

    :param user_id: Идентификатор пользователя.
    :param action: Код выполненного действия.
    :param word_id: Идентификатор слова, если действие относится к слову.
    :param sentence_id: Идентификатор предложения, если действие относится к нему.
    :return: Сохранённая запись действия.
    :raises ValueError: Если указаны оба объекта или не указан ни один.
    """
    if (word_id is None) == (sentence_id is None):
        raise ValueError("Action must reference exactly one note")
    action_record = Action()
    action_record.user_id = user_id
    action_record.word_id = word_id
    action_record.sentence_id = sentence_id
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
    used = db.session.scalar(
        select(db.func.count(Action.id)).where(
            Action.user_id == user.id,
            Action.action.in_([
                Action.RIGHT_ANSWER,
                Action.WRONG_ANSWER,
                Action.SKIP,
            ]),
        )
    ) or 0
    limit = int(current_app.config["ANONYMOUS_ACTION_LIMIT"])
    return max(0, limit - used)


def get_strike(user_id: int) -> int:
    """Вычисляет текущую серию верных ответов по истории действий.

    :param user_id: Идентификатор пользователя.
    :return: Количество последовательных верных ответов с конца истории.
    """
    actions = db.session.scalars(
        select(Action.action)
        .where(
            Action.user_id == user_id,
            Action.action.in_([
                Action.RIGHT_ANSWER,
                Action.WRONG_ANSWER,
                Action.SKIP,
            ]),
        )
        .order_by(desc(Action.datetime))
    )

    streak = 0
    for action in actions:
        if action == Action.RIGHT_ANSWER:
            streak += 1
        else:
            break

    return streak


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
    actions = db.session.execute(
        select(Action.action, Action.datetime)
        .where(
            Action.user_id == user_id,
            Action.action.in_([
                Action.RIGHT_ANSWER,
                Action.WRONG_ANSWER,
                Action.SKIP,
            ]),
        )
        .order_by(Action.datetime)
    )

    mistakes = 0
    skips = 0
    correct = 0
    best_streak = 0
    current_streak = 0

    total_time = timedelta()
    last_time = None
    timed_intervals = 0
    max_pause = timedelta(minutes=10)

    for action in actions:
        if last_time is not None:
            pause = action.datetime - last_time
            if pause <= max_pause:
                total_time += pause
                timed_intervals += 1
        last_time = action.datetime

        if action.action == Action.RIGHT_ANSWER:
            correct += 1
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        elif action.action == Action.WRONG_ANSWER:
            mistakes += 1
            current_streak = 0
        elif action.action == Action.SKIP:
            skips += 1
            current_streak = 0

    answered = correct + mistakes
    percent_correct = (correct / answered * 100) if answered else 0
    average_seconds = (
        total_time.total_seconds() / timed_intervals
        if timed_intervals
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
