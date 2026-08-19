from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import random
from typing import Any

from flask import current_app, session
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    Action,
    Category,
    Paronym,
    ParonymExercise,
    ParonymGroup,
    PracticeItem,
    SpellingExercise,
    User,
)
from app.utils import add_action, get_anonymous_actions_remaining, get_cached_strike


class PracticeError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        """Создаёт доменную ошибку практики.

        :param code: Стабильный машинный код ошибки.
        :param message: Сообщение для клиента или журнала.
        :param status: HTTP-статус, соответствующий ошибке.
        :return: Новый экземпляр ошибки.
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class Card:
    item: PracticeItem
    info: list[str]

    @property
    def kind(self) -> str:
        """Возвращает API-тип карточки.

        :return: Строка ``spelling`` или ``paronym``.
        """
        return self.item.type


def serialize_card(card: Card, *, admin: bool = False) -> dict[str, Any]:
    """Преобразует карточку в компактное представление для API ленты.

    :param card: Доменная карточка с моделью и поясняющей информацией.
    :param admin: Нужно ли включить административное объяснение.
    :return: Словарь с данными карточки, не содержащий HTML.
    """
    item = card.item
    is_paronym = isinstance(item, ParonymExercise)
    return {
        "id": item.id,
        "type": card.kind,
        "prompt": item.get_prompt(),
        "blank": "_______" if is_paronym else "_",
        "answers": item.get_answers(),
        "info": card.info,
        "explanation": None if is_paronym or not admin else item.explanation,
    }


def select_cards(
    user: User,
    count: int,
    task_id: str = "",
    category_id: str = "",
    mistakes: bool = False,
    exclude_ids: set[int] | None = None,
) -> list[Card]:
    """Выбирает уникальный пакет карточек общими запросами к кандидатам.

    :param user: Пользователь, для которого формируется лента.
    :param count: Требуемое количество карточек.
    :param task_id: Идентификатор задания для фильтрации.
    :param category_id: Идентификатор категории для фильтрации.
    :param mistakes: Признак выборки только проблемных упражнений.
    :param exclude_ids: Идентификаторы карточек, уже находящихся в клиентском пуле.
    :return: Список выбранных карточек без повторов внутри пакета.
    :raises PracticeError: Если размер пакета некорректен или карточки не найдены.
    """
    max_count = int(current_app.config["PRACTICE_CARD_BATCH_MAX"])
    if count < 1 or count > max_count:
        raise PracticeError(
            "invalid_limit",
            f"Limit must be between 1 and {max_count}",
            400,
        )
    active_filters = sum((bool(task_id), bool(category_id), mistakes))
    if active_filters > 1:
        raise PracticeError(
            "incompatible_filters",
            "Task, category and mistakes filters cannot be combined",
            400,
        )
    excluded = set(exclude_ids or ())

    if task_id == "5":
        query = ParonymExercise.query.options(
            selectinload(ParonymExercise.paronym)
            .selectinload(Paronym.group)
            .selectinload(ParonymGroup.paronyms)
        )
        if excluded:
            query = query.filter(~ParonymExercise.id.in_(excluded))
        items = _random_window(query, count)
        if not items and excluded:
            return select_cards(user, count, task_id=task_id)
        if not items:
            raise PracticeError(
                "paronym_not_found",
                "No paronym exercises available",
                404,
            )
        info = [f'Фильтр: "Задание №{task_id}"']
        return [Card(item, info.copy()) for item in items]

    category = (
        db.session.get(Category, int(category_id))
        if category_id.isdigit()
        else None
    )
    if task_id:
        base_items = SpellingExercise.query.filter(
            SpellingExercise.task_number == task_id
        )
        base_info = [f'Фильтр: "Задание №{task_id}"']
    elif category_id:
        if category is None:
            raise PracticeError("category_not_found", "Category not found", 404)
        base_items = SpellingExercise.query.filter(
            SpellingExercise.category_id == category.id
        )
        base_info = [f'Фильтр: "Категория {category.name}"']
    else:
        base_items = SpellingExercise.query
        base_info = []
    if excluded:
        base_items = base_items.filter(~SpellingExercise.id.in_(excluded))

    if mistakes:
        stats = _answer_stats(user.id)
        difficulty = stats.c.wrong_count - stats.c.right_count
        items = _random_window(
            base_items.join(
                stats, SpellingExercise.id == stats.c.practice_item_id
            ).filter(difficulty > 0),
            count,
        )
        if not items and excluded:
            return select_cards(user, count, mistakes=True)
        if not items:
            raise PracticeError("word_not_found", "No words available", 404)
        return [
            Card(item, ['Фильтр: "Неверные ответы"']) for item in items
        ]

    unseen_query = base_items.outerjoin(
        Action,
        and_(
            SpellingExercise.id == Action.practice_item_id,
            Action.user_id == user.id,
        ),
    ).filter(Action.id.is_(None))
    unseen_count = unseen_query.count()
    unseen = _random_window(unseen_query, count, total=unseen_count)

    stats = _answer_stats(user.id)
    difficulty = stats.c.wrong_count - stats.c.right_count
    difficult = (
        base_items.join(
            stats, SpellingExercise.id == stats.c.practice_item_id
        )
        .filter(difficulty > 0)
        .order_by(difficulty.desc())
        .limit(int(current_app.config["PRACTICE_DIFFICULT_CANDIDATE_LIMIT"]))
        .all()
    )

    selected: list[Card] = []
    selected_ids: set[int] = set()
    while len(selected) < count and (unseen or difficult):
        choose_unseen = bool(unseen) and (
            not difficult
            or random.randrange(unseen_count + len(difficult)) < unseen_count
        )
        if choose_unseen:
            item = unseen.pop()
            reason = "Это слово встретилось первый раз"
            unseen_count = max(0, unseen_count - 1)
        else:
            item = random.choice(difficult)
            difficult.remove(item)
            reason = "Это слово встретилось из-за большого количества ошибок"
        if item.id in selected_ids:
            continue
        selected_ids.add(item.id)
        selected.append(Card(item, [*base_info, reason]))

    remaining = count - len(selected)
    if remaining:
        fallback = base_items
        if selected_ids:
            fallback = fallback.filter(~SpellingExercise.id.in_(selected_ids))
        for item in _random_window(fallback, remaining):
            selected_ids.add(item.id)
            selected.append(Card(
                item,
                [*base_info, "Это слово встретилось случайно"],
            ))

    if not selected and excluded:
        return select_cards(
            user,
            count,
            task_id=task_id,
            category_id=category_id,
            mistakes=mistakes,
        )
    if not selected:
        raise PracticeError("word_not_found", "No words available", 404)
    return selected


def select_card(
    user: User,
    task_id: str = "",
    category_id: str = "",
    mistakes: bool = False,
) -> Card:
    """Выбирает одну карточку по правилам персональной ленты.

    :param user: Пользователь, для которого выбирается карточка.
    :param task_id: Идентификатор задания для фильтрации.
    :param category_id: Идентификатор категории для фильтрации.
    :param mistakes: Признак выборки только проблемных упражнений.
    :return: Выбранная карточка.
    :raises PracticeError: Если подходящая карточка не найдена.
    """
    return select_cards(
        user,
        1,
        task_id=task_id,
        category_id=category_id,
        mistakes=mistakes,
    )[0]


def _get_typed_item(item_id: int, item_type: str) -> PracticeItem:
    """Находит карточку и проверяет заявленный клиентом тип.

    :param item_id: Единый идентификатор карточки.
    :param item_type: Ожидаемый API-тип карточки.
    :return: Карточка с совпадающим типом.
    :raises PracticeError: Если тип неизвестен или карточка не найдена.
    """
    if item_type not in {"spelling", "paronym"}:
        raise PracticeError("invalid_card_type", "Invalid card type", 400)
    item = db.session.get(PracticeItem, item_id)
    if item is None or item.type != item_type:
        raise PracticeError("item_not_found", "Practice item not found", 404)
    return item


def check_answer(
    user: User,
    item_id: int,
    answer: str,
    item_type: str,
) -> dict[str, Any]:
    """Проверяет ответ и сохраняет действие пользователя.

    :param user: Пользователь, отправивший ответ.
    :param item_id: Единый идентификатор карточки практики.
    :param answer: Выбранный пользователем вариант ответа.
    :param item_type: Тип карточки: ``spelling`` или ``paronym``.
    :return: Результат проверки, раскрытый текст и состояние серии.
    :raises PracticeError: Если карточка не найдена или исчерпана квота.
    """
    _ensure_quota(user)
    item = _get_typed_item(item_id, item_type)
    right_answer = item.get_correct_answer()
    blank = "_______" if item_type == "paronym" else "_"
    full_item = item.get_prompt().replace(blank, right_answer)
    correct = answer == right_answer
    if user.settings.strike:
        session["strike"] = get_cached_strike(user.id) + 1 if correct else 0
    add_action(
        user_id=user.id,
        action=Action.RIGHT_ANSWER if correct else Action.WRONG_ANSWER,
        practice_item_id=item_id,
    )
    return {
        "correct": correct,
        "full_word": full_item,
        "explanation": item.explanation if item_type == "spelling" else None,
        "strike": {
            "n": session.get("strike"),
            "levels": current_app.config["STRIKE_LEVELS"],
        },
    }


def _can_skip_without_confirmation(user: User, item_id: int) -> bool:
    """Проверяет, можно ли пропустить карточку без подтверждения.

    :param user: Пользователь, выполняющий свайп.
    :param item_id: Единый идентификатор карточки.
    :return: ``True``, если отдельное подтверждение не требуется.
    """
    if not user.settings.strike:
        return True
    grace_strike = int(current_app.config["PRACTICE_SWIPE_GRACE_STRIKE"])
    return (
        item_id in _recent_item_ids(user.id)
        or get_cached_strike(user.id) <= grace_strike
    )


def skip_card(
    user: User,
    item_id: int,
    item_type: str,
    *,
    confirmed: bool = False,
) -> int:
    """Пропускает карточку и применяет правила серии и квоты.

    :param user: Пользователь, выполняющий пропуск.
    :param item_id: Единый идентификатор карточки практики.
    :param item_type: Тип карточки: ``spelling`` или ``paronym``.
    :param confirmed: Подтверждён ли пользователем сброс длинной серии.
    :return: Актуальная длина серии после пропуска.
    :raises PracticeError: Если карточка не найдена, исчерпана квота или
        требуется подтверждение сброса серии.
    """
    _get_typed_item(item_id, item_type)
    _ensure_quota(user)
    if not confirmed and not _can_skip_without_confirmation(user, item_id):
        raise PracticeError(
            "strike_reset_confirmation_required",
            "Skipping this card will reset the strike",
            409,
        )
    if item_id in _recent_item_ids(user.id):
        return get_cached_strike(user.id)
    if user.settings.strike:
        session["strike"] = 0
    add_action(
        user_id=user.id,
        action=Action.SKIP,
        practice_item_id=item_id,
    )
    return 0


def report_word(item_id: int) -> bool:
    """Записывает пользовательский отчёт об ошибке в упражнении.

    :param item_id: Идентификатор орфографического упражнения.
    :return: ``True`` при успешной записи, иначе ``False``.
    """
    item = db.session.get(SpellingExercise, item_id)
    if item is None:
        return False
    with Path("mistakes.txt").open("a", encoding="utf-8") as report_file:
        report_file.write(f"{datetime.now()} - {item.word} [{item.id}]\n")
    current_app.logger.info(
        "Practice item reported as a mistake: %s [%s]", item.word, item.id
    )
    return True


def _answer_stats(user_id: int):
    """Строит подзапрос агрегированной статистики ответов по карточкам.

    :param user_id: Идентификатор пользователя.
    :return: SQLAlchemy-подзапрос с количеством ошибок и верных ответов.
    """
    return (
        db.session.query(
            Action.practice_item_id,
            func.sum(
                case((Action.action == Action.WRONG_ANSWER, 1), else_=0)
            ).label("wrong_count"),
            func.sum(
                case((Action.action == Action.RIGHT_ANSWER, 1), else_=0)
            ).label("right_count"),
        )
        .filter(Action.user_id == user_id)
        .group_by(Action.practice_item_id)
        .subquery()
    )


def _recent_item_ids(user_id: int, limit: int = 3) -> list[int]:
    """Возвращает последние идентификаторы карточек пользователя.

    :param user_id: Идентификатор пользователя.
    :param limit: Максимальное количество идентификаторов.
    :return: Идентификаторы от нового действия к старому.
    """
    return list(db.session.scalars(
        select(Action.practice_item_id)
        .where(Action.user_id == user_id)
        .order_by(Action.datetime.desc())
        .limit(limit)
    ))


def _random_window(query, count: int, total: int | None = None) -> list[Any]:
    """Выбирает случайное окно без сортировки всей таблицы.

    :param query: SQLAlchemy-запрос с кандидатами.
    :param count: Максимальное количество строк.
    :param total: Заранее вычисленное количество строк, если оно известно.
    :return: Список строк из случайной позиции запроса.
    """
    row_count = query.count() if total is None else total
    if row_count <= 0:
        return []
    offset = random.randrange(row_count - count + 1) if row_count > count else 0
    return query.offset(offset).limit(count).all()


def _ensure_quota(user: User) -> None:
    """Проверяет наличие доступного действия у анонимного пользователя.

    :param user: Пользователь, для которого проверяется квота.
    :return: ``None``.
    :raises PracticeError: Если лимит анонимных действий исчерпан.
    """
    if get_anonymous_actions_remaining(user) == 0:
        raise PracticeError(
            "anonymous_limit_reached",
            "Войдите через Яндекс, чтобы продолжить.",
            403,
        )
