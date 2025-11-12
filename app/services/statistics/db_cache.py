from app import app, db, logger
from app.services.statistics import StatisticsConfig
from app.models import Action, UserWordStat, WordGlobalStat, ActionType

from typing import List, Dict, Tuple
from sqlalchemy.orm.query import Query
from sqlalchemy import func, and_, or_, cast
from datetime import datetime, timedelta


def update_db_cache():
    """
    Обновляет таблицы UserWordStat и WordGlobalStat на основе данных из Action.
    Подсчитывает статистику по правильным/неправильным ответам, пропускам и
    рассчитывает показатели сложности.
    """
    logger.info("Начинаем обновление кэша статистики...")

    # Очищаем существующие данные статистики
    db.session.query(UserWordStat).delete()
    db.session.query(WordGlobalStat).delete()

    # Получаем все действия, связанные со словами
    actions_query = (
        db.session.query(Action)
        .filter(
            and_(
                Action.word_id.isnot(None),
                Action.action.in_(
                    [ActionType.RIGHT_ANSWER, ActionType.WRONG_ANSWER, ActionType.SKIP]
                ),
            )
        )
        .order_by(Action.user_id, Action.word_id, Action.datetime)
    )

    logger.info("Подсчитываем статистику пользователей...")
    _update_user_word_stats(actions_query)

    logger.info("Подсчитываем глобальную статистику...")
    _update_word_global_stats()

    db.session.commit()
    logger.info("Обновление кэша статистики завершено!")


def _update_user_word_stats(actions_query):
    """Обновляет статистику UserWordStat на основе действий пользователей."""

    # Группируем действия по пользователю и слову
    user_word_stats = {}

    for action in actions_query:
        key = (action.user_id, action.word_id)

        if key not in user_word_stats:
            user_word_stats[key] = {
                "correct_count": 0,
                "wrong_count": 0,
                "skip_count": 0,
                "success_streak": 0,
                "current_streak": 0,
                "last_seen": None,
                "last_action": None,
                "actions_list": [],
            }

        stats = user_word_stats[key]
        stats["actions_list"].append(action)
        stats["last_seen"] = action.datetime
        stats["last_action"] = action.action

        # Подсчитываем типы действий
        if action.action == ActionType.RIGHT_ANSWER:
            stats["correct_count"] += 1
            stats["current_streak"] += 1
            stats["success_streak"] = max(
                stats["success_streak"], stats["current_streak"]
            )
        elif action.action == ActionType.WRONG_ANSWER:
            stats["wrong_count"] += 1
            stats["current_streak"] = 0
        elif action.action == ActionType.SKIP:
            stats["skip_count"] += 1
            stats["current_streak"] = 0

    # Создаем записи в UserWordStat
    user_stats_to_insert = []
    for (user_id, word_id), stats in user_word_stats.items():
        # Рассчитываем difficulty_score и time_score
        difficulty_score = _calculate_user_difficulty_score(
            stats["correct_count"], stats["wrong_count"], stats["skip_count"]
        )

        time_score = _calculate_time_score(stats["actions_list"])

        user_stat = UserWordStat()
        user_stat.user_id = user_id
        user_stat.word_id = word_id
        user_stat.correct_count = stats["correct_count"]
        user_stat.wrong_count = stats["wrong_count"]
        user_stat.skip_count = stats["skip_count"]
        user_stat.success_streak = stats["success_streak"]
        user_stat.last_seen = stats["last_seen"]
        user_stat.last_action = stats["last_action"]
        user_stat.difficulty_score = difficulty_score
        user_stat.time_score = time_score
        user_stats_to_insert.append(user_stat)

    if user_stats_to_insert:
        db.session.bulk_save_objects(user_stats_to_insert)


def _update_word_global_stats():
    """Обновляет глобальную статистику WordGlobalStat на основе UserWordStat."""

    # Агрегируем данные из UserWordStat для каждого слова
    global_stats_query = db.session.query(
        UserWordStat.word_id,
        func.sum(UserWordStat.correct_count).label("total_correct"),
        func.sum(UserWordStat.wrong_count).label("total_wrong"),
        func.sum(UserWordStat.skip_count).label("total_skip"),
    ).group_by(UserWordStat.word_id)

    global_stats_to_insert = []
    for row in global_stats_query:
        difficulty_score: float = _calculate_global_difficulty_score(
            row.total_correct, row.total_wrong, row.total_skip
        )

        global_stat = WordGlobalStat()
        global_stat.word_id = row.word_id
        global_stat.correct_count = row.total_correct
        global_stat.wrong_count = row.total_wrong
        global_stat.skip_count = row.total_skip
        global_stat.difficulty_score = difficulty_score
        global_stats_to_insert.append(global_stat)

    if global_stats_to_insert:
        db.session.bulk_save_objects(global_stats_to_insert)


def _calculate_user_difficulty_score(
    correct_count: int, wrong_count: int, skip_count: int
) -> float:
    """
    Рассчитывает индивидуальный показатель сложности для пользователя и слова.

    Args:
        correct_count: Количество правильных ответов
        wrong_count: Количество неправильных ответов
        skip_count: Количество пропусков

    Returns:
        float: Показатель сложности от 0.0 до 1.0
    """
    total_attempts: int = correct_count + wrong_count + skip_count

    if total_attempts == 0:
        return StatisticsConfig.DEFAULT_DIFFICULTY_SCORE

    weighted_errors: float = wrong_count + (
        skip_count * StatisticsConfig.SKIP_WEIGHT_MULTIPLIER
    )

    # Формула с настраиваемым сглаживающим фактором
    smoothing = StatisticsConfig.USER_DIFFICULTY_SMOOTHING
    difficulty = (weighted_errors + smoothing) / (total_attempts + smoothing * 2)

    return min(1.0, max(0.0, difficulty))


def _calculate_time_score(actions_list: List[Action]) -> float:
    """
    Рассчитывает временной показатель на основе давности последнего ответа.

    Логика расчета (система интервального повторения):
    - 0.1 = недавний ответ (не нужно повторять)
    - 1.0 = базовый период забывания прошел
    - > 1.0 = давно не отвечали (нужно повторить)
    - 5.0 = очень давно (срочно повторить)

    Args:
        actions_list: Список действий пользователя для данного слова

    Returns:
        float: Временной показатель от MIN_TIME_SCORE до MAX_TIME_SCORE
    """
    if not actions_list:
        return StatisticsConfig.DEFAULT_TIME_SCORE

    # Находим последнее действие
    last_action = max(actions_list, key=lambda x: x.datetime)

    # Рассчитываем количество дней с последнего действия
    now = datetime.now()
    days_since_last = (now - last_action.datetime).total_seconds() / (24 * 3600)

    # Ограничиваем максимальным периодом
    days_since_last = min(days_since_last, StatisticsConfig.MAX_FORGETTING_DAYS)

    # Нормализация относительно базового периода забывания
    time_score = days_since_last / StatisticsConfig.BASE_FORGETTING_DAYS

    # Ограничиваем настраиваемым диапазоном
    return min(
        StatisticsConfig.MAX_TIME_SCORE,
        max(StatisticsConfig.MIN_TIME_SCORE, time_score),
    )


def _calculate_global_difficulty_score(
    total_correct: int, total_wrong: int, total_skip: int
) -> float:
    """
    Рассчитывает глобальный показатель сложности слова для всех пользователей.
    Использует настройки из StatisticsConfig.

    Args:
        total_correct: Общее количество правильных ответов
        total_wrong: Общее количество неправильных ответов
        total_skip: Общее количество пропусков

    Returns:
        float: Глобальный показатель сложности от 0.0 до 1.0
    """
    total_attempts = total_correct + total_wrong + total_skip

    if total_attempts == 0:
        return StatisticsConfig.DEFAULT_DIFFICULTY_SCORE

    # Пропуски считаются как более тяжелые ошибки
    weighted_errors = total_wrong + (
        total_skip * StatisticsConfig.SKIP_WEIGHT_MULTIPLIER
    )

    # Больший сглаживающий фактор для глобальной статистики
    smoothing = StatisticsConfig.GLOBAL_DIFFICULTY_SMOOTHING
    difficulty = (weighted_errors + smoothing) / (total_attempts + smoothing * 2)

    return min(1.0, max(0.0, difficulty))
