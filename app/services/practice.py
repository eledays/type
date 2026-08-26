from dataclasses import dataclass
import random
from typing import Any

from flask import current_app, session
from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectin_polymorphic, selectinload

from app.extensions import db
from app.models import (
    Action,
    Category,
    Paronym,
    ParonymExercise,
    ParonymGroup,
    PracticeItem,
    PracticeProgress,
    GlobalPracticeStats,
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


@dataclass
class ItemProgress:
    """Краткая оценка знания одной карточки пользователем."""

    success_rate: float
    right_count: int
    failure_weight: float
    latest_action: int | None


ADAPTIVE_SEQUENCE = (
    "learning",
    "learning",
    "comfortable",
    "review",
    "learning",
    "new",
    "learning",
    "comfortable",
    "review",
    "learning",
)
RECENT_PROGRESS_LIMIT = 30
REPEAT_GAP = 3


def serialize_card(
    card: Card,
    *,
    admin: bool = False,
    stats: dict[str, int | float] | None = None,
) -> dict[str, Any]:
    """Преобразует карточку в компактное представление для API ленты.

    :param card: Доменная карточка с моделью и поясняющей информацией.
    :param admin: Нужно ли включить административное объяснение.
    :param stats: Личная статистика пользователя по карточке.
    :return: Словарь с данными карточки, не содержащий HTML.
    """
    item = card.item
    is_paronym = isinstance(item, ParonymExercise)
    task_number = item.task_number
    task_title = current_app.config["TASKS"].get(task_number)
    return {
        "id": item.id,
        "type": card.kind,
        "prompt": item.get_prompt(),
        "blank": "_______" if is_paronym else "_",
        "answers": item.get_answers(),
        "info": card.info,
        "task": {
            "number": task_number,
            "title": task_title,
        },
        "stats": stats or {
            "correct": 0,
            "mistakes": 0,
            "skips": 0,
            "correct_percent": 0,
        },
        "explanation": None if is_paronym or not admin else item.explanation,
    }


def serialize_cards(
    cards: list[Card],
    user_id: int,
    *,
    admin: bool = False,
) -> list[dict[str, Any]]:
    """Сериализует пакет карточек с личной статистикой одним запросом."""
    item_ids = [card.item.id for card in cards]
    stats_by_item: dict[int, dict[str, int | float]] = {}
    if item_ids:
        rows = db.session.execute(
            select(
                PracticeProgress.practice_item_id,
                PracticeProgress.right_count,
                PracticeProgress.wrong_count,
                PracticeProgress.skip_count,
            )
            .where(
                PracticeProgress.user_id == user_id,
                PracticeProgress.practice_item_id.in_(item_ids),
            )
        )
        for item_id, correct, mistakes, skips in rows:
            correct_count = int(correct or 0)
            mistake_count = int(mistakes or 0)
            answered = correct_count + mistake_count
            stats_by_item[item_id] = {
                "correct": correct_count,
                "mistakes": mistake_count,
                "skips": int(skips or 0),
                "correct_percent": round(
                    correct_count / answered * 100, 1
                ) if answered else 0,
            }
    return [
        serialize_card(
            card,
            admin=admin,
            stats=stats_by_item.get(card.item.id),
        )
        for card in cards
    ]


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

    category = (
        db.session.get(Category, int(category_id))
        if category_id.isdigit()
        else None
    )
    base_items = PracticeItem.query.options(
        selectin_polymorphic(
            PracticeItem,
            [SpellingExercise, ParonymExercise],
        ),
        selectinload(ParonymExercise.paronym)
        .selectinload(Paronym.group)
        .selectinload(ParonymGroup.paronyms),
    )
    if task_id:
        base_items = base_items.filter(
            PracticeItem.task_number == task_id
        )
        base_info = [f'Фильтр: "Задание №{task_id}"']
    elif category_id:
        if category is None:
            raise PracticeError("category_not_found", "Category not found", 404)
        base_items = base_items.filter(PracticeItem.category_id == category.id)
        base_info = [f'Фильтр: "Категория {category.name}"']
    else:
        base_info = []
    if excluded:
        base_items = base_items.filter(~PracticeItem.id.in_(excluded))

    if mistakes:
        difficulty = (
            PracticeProgress.wrong_count
            + 0.5 * PracticeProgress.skip_count
            - PracticeProgress.right_count
        )
        items = _random_window(
            base_items.join(
                PracticeProgress,
                and_(
                    PracticeItem.id == PracticeProgress.practice_item_id,
                    PracticeProgress.user_id == user.id,
                ),
            ).filter(difficulty > 0),
            count,
        )
        if not items and excluded:
            return select_cards(user, count, mistakes=True)
        if not items:
            raise PracticeError(
                "item_not_found", "No practice items available", 404
            )
        return [
            Card(item, ['Фильтр: "Неверные ответы"']) for item in items
        ]

    seen_query = base_items.join(
        PracticeProgress,
        and_(
            PracticeItem.id == PracticeProgress.practice_item_id,
            PracticeProgress.user_id == user.id,
        ),
    )
    unseen_query = base_items.outerjoin(
        PracticeProgress,
        and_(
            PracticeItem.id == PracticeProgress.practice_item_id,
            PracticeProgress.user_id == user.id,
        ),
    ).filter(PracticeProgress.user_id.is_(None))
    candidate_limit = max(
        count * 4,
        int(current_app.config["PRACTICE_DIFFICULT_CANDIDATE_LIMIT"]),
    )
    candidates = _random_window(seen_query, candidate_limit)
    candidate_ids = {item.id for item in candidates}
    candidates.extend(
        item
        for item in _random_window(unseen_query, candidate_limit)
        if item.id not in candidate_ids
    )
    recent_actions = _recent_progress_actions(user.id)
    progress_item_ids = [item.id for item in candidates]
    user_stats = _user_answer_stats(user.id, progress_item_ids)
    progress = _item_progress(
        user_stats,
        recent_actions,
        _global_answer_stats(progress_item_ids),
    )
    pools = _adaptive_pools(candidates, progress)
    recent_ids = {
        action.practice_item_id
        for action in recent_actions[:REPEAT_GAP]
    }
    action_count = _user_action_count(user.id)

    selected: list[Card] = []
    selected_ids: set[int] = set()

    # После двух неудач начинаем пакет со знакомой лёгкой карточки. Это не
    # отменяет обучение, но не даёт ленте превращаться в череду поражений.
    if count and _has_failure_streak(recent_actions, length=2):
        recovery_choice = _take_candidate(
            pools,
            "comfortable",
            selected_ids,
            recent_ids,
            progress,
        )
        if recovery_choice is not None:
            recovery, _ = recovery_choice
            selected.append(Card(
                recovery,
                [*base_info, "Знакомое задание после сложной серии"],
            ))
            selected_ids.add(recovery.id)

    sequence_offset = int(action_count) % len(ADAPTIVE_SEQUENCE)
    while len(selected) < count:
        pool_name = ADAPTIVE_SEQUENCE[
            (sequence_offset + len(selected)) % len(ADAPTIVE_SEQUENCE)
        ]
        choice = _take_candidate(
            pools,
            pool_name,
            selected_ids,
            recent_ids,
            progress,
        )
        if choice is None:
            break
        item, actual_pool = choice
        selected_ids.add(item.id)
        selected.append(Card(
            item,
            [*base_info, _selection_reason(actual_pool)],
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
        raise PracticeError(
            "item_not_found", "No practice items available", 404
        )
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
    anonymous_remaining = _ensure_quota(user)
    item = _get_typed_item(item_id, item_type)
    right_answer = item.get_correct_answer()
    blank = "_______" if item_type == "paronym" else "_"
    full_item = item.get_prompt().replace(blank, right_answer)
    correct = answer == right_answer
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
        "anonymous_remaining": (
            None
            if anonymous_remaining is None
            else anonymous_remaining - 1
        ),
    }


def _can_skip_without_confirmation(
    user: User,
    item_id: int,
    recent_item_ids: list[int],
) -> bool:
    """Проверяет, можно ли пропустить карточку без подтверждения.

    :param user: Пользователь, выполняющий свайп.
    :param item_id: Единый идентификатор карточки.
    :return: ``True``, если отдельное подтверждение не требуется.
    """
    grace_strike = int(current_app.config["PRACTICE_SWIPE_GRACE_STRIKE"])
    return (
        item_id in recent_item_ids
        or get_cached_strike(user.id) <= grace_strike
    )


def skip_card(
    user: User,
    item_id: int,
    item_type: str,
    *,
    confirmed: bool = False,
) -> tuple[int, int | None]:
    """Пропускает карточку и применяет правила серии и квоты.

    :param user: Пользователь, выполняющий пропуск.
    :param item_id: Единый идентификатор карточки практики.
    :param item_type: Тип карточки: ``spelling`` или ``paronym``.
    :param confirmed: Подтверждён ли пользователем сброс длинной серии.
    :return: Актуальная серия и остаток анонимной квоты.
    :raises PracticeError: Если карточка не найдена, исчерпана квота или
        требуется подтверждение сброса серии.
    """
    _get_typed_item(item_id, item_type)
    anonymous_remaining = _ensure_quota(user)
    recent_item_ids = _recent_item_ids(user.id)
    if not confirmed and not _can_skip_without_confirmation(
        user, item_id, recent_item_ids
    ):
        raise PracticeError(
            "strike_reset_confirmation_required",
            "Skipping this card will reset the strike",
            409,
        )
    if item_id in recent_item_ids:
        return get_cached_strike(user.id), anonymous_remaining
    session["strike"] = 0
    add_action(
        user_id=user.id,
        action=Action.SKIP,
        practice_item_id=item_id,
    )
    return 0, (
        None if anonymous_remaining is None else anonymous_remaining - 1
    )


def _recent_progress_actions(user_id: int) -> list[Action]:
    """Возвращает последние учебные действия для адаптивной оценки."""
    return list(db.session.scalars(
        select(Action)
        .where(
            Action.user_id == user_id,
            Action.action.in_([
                Action.RIGHT_ANSWER,
                Action.WRONG_ANSWER,
                Action.SKIP,
            ]),
        )
        .order_by(Action.datetime.desc(), Action.id.desc())
        .limit(RECENT_PROGRESS_LIMIT)
    ))


def _global_answer_stats(
    item_ids: list[int],
) -> dict[int, tuple[int, int, int]]:
    """Возвращает глобальную статистику только для кандидатов ленты."""
    if not item_ids:
        return {}
    rows = db.session.execute(
        select(
            GlobalPracticeStats.practice_item_id,
            GlobalPracticeStats.right_count,
            GlobalPracticeStats.wrong_count,
            GlobalPracticeStats.skip_count,
        ).where(GlobalPracticeStats.practice_item_id.in_(item_ids))
    )
    return {
        item_id: (int(right or 0), int(wrong or 0), int(skipped or 0))
        for item_id, right, wrong, skipped in rows
    }


def _user_answer_stats(
    user_id: int,
    item_ids: list[int],
) -> dict[int, tuple[int, int, int]]:
    """Возвращает прогресс пользователя только для кандидатов ленты."""
    if not item_ids:
        return {}
    rows = db.session.execute(
        select(
            PracticeProgress.practice_item_id,
            PracticeProgress.right_count,
            PracticeProgress.wrong_count,
            PracticeProgress.skip_count,
        )
        .where(
            PracticeProgress.user_id == user_id,
            PracticeProgress.practice_item_id.in_(item_ids),
        )
    )
    return {
        item_id: (int(right or 0), int(wrong or 0), int(skipped or 0))
        for item_id, right, wrong, skipped in rows
    }


def _user_action_count(user_id: int) -> int:
    """Считает учебные действия по компактным строкам прогресса."""
    return int(db.session.scalar(
        select(func.sum(
            PracticeProgress.right_count
            + PracticeProgress.wrong_count
            + PracticeProgress.skip_count
        )).where(PracticeProgress.user_id == user_id)
    ) or 0)


def _item_progress(
    user_stats: dict[int, tuple[int, int, int]],
    recent_actions: list[Action],
    global_stats: dict[int, tuple[int, int, int]],
) -> dict[int, ItemProgress]:
    """Оценивает вероятность успеха по свежим и общим ответам."""
    latest_actions: dict[int, int] = {}
    recent_stats: dict[int, list[int]] = {}
    for action in recent_actions:
        latest_actions.setdefault(action.practice_item_id, action.action)
        stats = recent_stats.setdefault(action.practice_item_id, [0, 0, 0])
        if action.action == Action.RIGHT_ANSWER:
            stats[0] += 1
        elif action.action == Action.WRONG_ANSWER:
            stats[1] += 1
        elif action.action == Action.SKIP:
            stats[2] += 1

    result: dict[int, ItemProgress] = {}
    for item_id, (right, wrong, skipped) in user_stats.items():
        global_right, global_wrong, global_skips = global_stats.get(
            item_id, (0, 0, 0)
        )
        global_failures = global_wrong + 0.5 * global_skips
        global_rate = (global_right + 3) / (
            global_right + global_failures + 6
        )
        recent_right, recent_wrong, recent_skipped = recent_stats.get(
            item_id, [0, 0, 0]
        )
        # Последние 30 действий учитываются второй раз, поэтому свежий
        # прогресс влияет на ленту сильнее давних успехов и ошибок.
        weighted_right = right + recent_right
        failure_weight = (
            wrong + recent_wrong + 0.5 * (skipped + recent_skipped)
        )
        success_rate = (weighted_right + 3 * global_rate) / (
            weighted_right + failure_weight + 3
        )
        result[item_id] = ItemProgress(
            success_rate=success_rate,
            right_count=right,
            failure_weight=failure_weight,
            latest_action=latest_actions.get(item_id),
        )
    return result


def _adaptive_pools(
    candidates: list[PracticeItem],
    progress: dict[int, ItemProgress],
) -> dict[str, list[PracticeItem]]:
    """Разделяет карточки на новые, обучающие, лёгкие и повторяемые."""
    pools: dict[str, list[PracticeItem]] = {
        "new": [],
        "learning": [],
        "comfortable": [],
        "review": [],
    }
    for item in candidates:
        item_progress = progress.get(item.id)
        if item_progress is None:
            pools["new"].append(item)
        elif (
            item_progress.latest_action in {
                Action.WRONG_ANSWER,
                Action.SKIP,
            }
            or item_progress.success_rate < 0.65
        ):
            pools["review"].append(item)
        elif (
            item_progress.right_count >= 2
            and item_progress.success_rate >= 0.80
        ):
            pools["comfortable"].append(item)
        else:
            pools["learning"].append(item)
    return pools


def _take_candidate(
    pools: dict[str, list[PracticeItem]],
    requested_pool: str,
    selected_ids: set[int],
    recent_ids: set[int],
    progress: dict[int, ItemProgress],
) -> tuple[PracticeItem, str] | None:
    """Выбирает карточку из нужной зоны и безопасных запасных зон."""
    fallback_order = {
        "learning": ("learning", "new", "comfortable", "review"),
        "comfortable": ("comfortable", "learning", "new", "review"),
        "review": ("review", "learning", "comfortable", "new"),
        "new": ("new", "learning", "comfortable", "review"),
    }
    for pool_name in fallback_order[requested_pool]:
        available = [
            item for item in pools[pool_name] if item.id not in selected_ids
        ]
        if not available:
            continue
        spaced = [item for item in available if item.id not in recent_ids]
        choices = spaced or available
        if requested_pool == "comfortable" and pool_name != "comfortable":
            return max(
                choices,
                key=lambda item: progress.get(
                    item.id, ItemProgress(0.5, 0, 0, None)
                ).success_rate,
            ), pool_name
        # This randomness only selects a practice card.
        return random.choice(choices), pool_name  # nosec B311
    return None


def _has_failure_streak(actions: list[Action], length: int) -> bool:
    """Проверяет, закончилась ли история серией ошибок или пропусков."""
    if len(actions) < length:
        return False
    failures = {Action.WRONG_ANSWER, Action.SKIP}
    return all(action.action in failures for action in actions[:length])


def _selection_reason(pool_name: str) -> str:
    """Возвращает понятное пользователю объяснение выбора карточки."""
    return {
        "new": "Новое задание",
        "learning": "Задание из вашей зоны обучения",
        "comfortable": "Знакомое задание для закрепления",
        "review": "Повторение задания, которое вызвало затруднение",
    }[pool_name]


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
    # This randomness only selects a practice card.
    offset = 0
    if row_count > count:
        offset = random.randrange(row_count - count + 1)  # nosec B311
    return query.offset(offset).limit(count).all()


def _ensure_quota(user: User) -> int | None:
    """Проверяет наличие доступного действия у анонимного пользователя.

    :param user: Пользователь, для которого проверяется квота.
    :return: Остаток квоты до действия или ``None`` для обычного пользователя.
    :raises PracticeError: Если лимит анонимных действий исчерпан.
    """
    remaining = get_anonymous_actions_remaining(user)
    if remaining == 0:
        raise PracticeError(
            "anonymous_limit_reached",
            "Войдите через Яндекс, чтобы продолжить.",
            403,
        )
    return remaining
