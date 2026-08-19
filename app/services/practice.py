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
    ParonymGroup,
    Sentence,
    User,
    Word,
)
from app.models.sentence import get_morph_analyzer
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
    note: Word | Sentence
    info: list[str]

    @property
    def kind(self) -> str:
        """Возвращает API-тип карточки.

        :return: Строка ``word`` или ``sentence``.
        """
        return "sentence" if isinstance(self.note, Sentence) else "word"


def serialize_card(card: Card, *, admin: bool = False) -> dict[str, Any]:
    """Преобразует карточку в компактное представление для API ленты.

    :param card: Доменная карточка с моделью и поясняющей информацией.
    :param admin: Нужно ли включить административное объяснение.
    :return: Словарь с данными карточки, не содержащий HTML.
    """
    note = card.note
    is_sentence = isinstance(note, Sentence)
    return {
        "id": note.id,
        "type": card.kind,
        "prompt": note.sentence if is_sentence else note.word,
        "blank": "_______" if is_sentence else "_",
        "answers": note.get_answers(),
        "info": card.info,
        "explanation": (
            None if is_sentence or not admin else note.explanation
        ),
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
    :param mistakes: Признак выборки только проблемных слов.
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
        query = Sentence.query.options(
            selectinload(Sentence.word)
            .selectinload(Paronym.group)
            .selectinload(ParonymGroup.paronyms)
        )
        if excluded:
            query = query.filter(~Sentence.id.in_(excluded))
        notes = _random_window(query, count)
        if not notes and excluded:
            return select_cards(
                user,
                count,
                task_id=task_id,
                category_id=category_id,
                mistakes=mistakes,
            )
        if not notes:
            raise PracticeError("sentence_not_found", "No sentences available", 404)
        info = [f'Фильтр: "Задание №{task_id}"']
        return [Card(note, info.copy()) for note in notes]

    category = (
        db.session.get(Category, int(category_id))
        if category_id.isdigit()
        else None
    )
    if task_id:
        base_words = Word.query.filter(Word.task_number == task_id)
        base_info = [f'Фильтр: "Задание №{task_id}"']
    elif category_id:
        if category is None:
            raise PracticeError("category_not_found", "Category not found", 404)
        base_words = Word.query.filter(Word.category_id == category.id)
        base_info = [f'Фильтр: "Категория {category.name}"']
    else:
        base_words = Word.query
        base_info = []
    if excluded:
        base_words = base_words.filter(~Word.id.in_(excluded))

    if mistakes:
        stats = _answer_stats(user.id)
        difficulty = stats.c.wrong_count - stats.c.right_count
        notes = _random_window(
            base_words.join(stats, Word.id == stats.c.word_id).filter(
                difficulty > 0
            ),
            count,
        )
        if not notes and excluded:
            return select_cards(
                user,
                count,
                task_id=task_id,
                category_id=category_id,
                mistakes=mistakes,
            )
        if not notes:
            raise PracticeError("word_not_found", "No words available", 404)
        return [
            Card(note, ['Фильтр: "Неверные ответы"']) for note in notes
        ]

    unseen_query = base_words.outerjoin(
        Action,
        and_(Word.id == Action.word_id, Action.user_id == user.id),
    ).filter(Action.id.is_(None))
    unseen_count = unseen_query.count()
    unseen = _random_window(unseen_query, count, total=unseen_count)

    stats = _answer_stats(user.id)
    difficulty = stats.c.wrong_count - stats.c.right_count
    difficult = (
        base_words.join(stats, Word.id == stats.c.word_id)
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
            note = unseen.pop()
            reason = "Это слово встретилось первый раз"
            unseen_count = max(0, unseen_count - 1)
        else:
            note = random.choice(difficult)
            difficult.remove(note)
            reason = "Это слово встретилось из-за большого количества ошибок"
        if note.id in selected_ids:
            continue
        selected_ids.add(note.id)
        selected.append(Card(note, [*base_info, reason]))

    remaining = count - len(selected)
    if remaining:
        fallback = base_words
        if selected_ids:
            fallback = fallback.filter(~Word.id.in_(selected_ids))
        for note in _random_window(fallback, remaining):
            selected_ids.add(note.id)
            selected.append(Card(
                note,
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
    :param mistakes: Признак выборки только проблемных слов.
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


def check_answer(
    user: User,
    note_id: int,
    answer: str,
    note_type: str,
) -> dict[str, Any]:
    """Проверяет ответ и сохраняет действие пользователя.

    :param user: Пользователь, отправивший ответ.
    :param note_id: Идентификатор слова или предложения.
    :param answer: Выбранный пользователем вариант ответа.
    :param note_type: Тип карточки: ``word`` или ``sentence``.
    :return: Результат проверки, раскрытый текст и состояние серии.
    :raises PracticeError: Если карточка не найдена или исчерпана квота.
    """
    _ensure_quota(user)
    if note_type not in {"word", "sentence"}:
        raise PracticeError("invalid_card_type", "Invalid card type", 400)
    is_paronym = note_type == "sentence"
    if is_paronym:
        note = db.session.get(Sentence, note_id)
        if note is None:
            raise PracticeError("sentence_not_found", "Sentence not found", 404)
        parsed_word = get_morph_analyzer().parse(note.word.word)[0]
        inflected_word = parsed_word.inflect(set(note.word_tags.split(",")))
        right_answer = inflected_word.word if inflected_word else parsed_word.word
        full_note = note.sentence.replace("_______", right_answer)
        explanation = None
    else:
        note = db.session.get(Word, note_id)
        if note is None:
            raise PracticeError("word_not_found", "Word not found", 404)
        right_answer = note.answers[0]
        full_note = note.word.replace("_", right_answer) if "_" in note.word else right_answer
        explanation = note.explanation

    correct = answer == right_answer
    if user.settings.strike:
        session["strike"] = get_cached_strike(user.id) + 1 if correct else 0
    add_action(
        user_id=user.id,
        action=Action.RIGHT_ANSWER if correct else Action.WRONG_ANSWER,
        word_id=None if is_paronym else note_id,
        sentence_id=note_id if is_paronym else None,
    )
    return {
        "correct": correct,
        "full_word": full_note,
        "explanation": explanation,
        "strike": {
            "n": session.get("strike"),
            "levels": current_app.config["STRIKE_LEVELS"],
        },
    }


def _can_skip_without_confirmation(
    user: User,
    note_id: int,
    note_type: str,
) -> bool:
    """Проверяет, можно ли пропустить карточку без подтверждения.

    :param user: Пользователь, выполняющий свайп.
    :param note_id: Идентификатор слова или предложения.
    :param note_type: Тип карточки: ``word`` или ``sentence``.
    :return: ``True``, если отдельное подтверждение не требуется.
    """
    if not user.settings.strike:
        return True
    last_ids = _recent_note_ids(user.id, note_type)
    grace_strike = int(current_app.config["PRACTICE_SWIPE_GRACE_STRIKE"])
    return note_id in last_ids or get_cached_strike(user.id) <= grace_strike


def skip_card(
    user: User,
    note_id: int,
    note_type: str,
    *,
    confirmed: bool = False,
) -> int:
    """Пропускает карточку и применяет правила серии и квоты.

    :param user: Пользователь, выполняющий пропуск.
    :param note_id: Идентификатор слова или предложения.
    :param note_type: Тип карточки: ``word`` или ``sentence``.
    :param confirmed: Подтверждён ли пользователем сброс длинной серии.
    :return: Актуальная длина серии после пропуска.
    :raises PracticeError: Если карточка не найдена, исчерпана квота или
        требуется подтверждение сброса серии.
    """
    if note_type == "sentence":
        if db.session.get(Sentence, note_id) is None:
            raise PracticeError("sentence_not_found", "Sentence not found", 404)
        word_id = None
        sentence_id = note_id
    elif note_type == "word":
        if db.session.get(Word, note_id) is None:
            raise PracticeError("word_not_found", "Word not found", 404)
        word_id = note_id
        sentence_id = None
    else:
        raise PracticeError("invalid_card_type", "Invalid card type", 400)

    _ensure_quota(user)
    if not confirmed and not _can_skip_without_confirmation(
        user,
        note_id,
        note_type,
    ):
        raise PracticeError(
            "strike_reset_confirmation_required",
            "Skipping this card will reset the strike",
            409,
        )
    last_ids = _recent_note_ids(user.id, note_type)
    if note_id in last_ids:
        return get_cached_strike(user.id)
    if user.settings.strike:
        session["strike"] = 0
    add_action(
        user_id=user.id,
        action=Action.SKIP,
        word_id=word_id,
        sentence_id=sentence_id,
    )
    return 0


def report_word(word_id: int) -> bool:
    """Помечает слово как ошибочное и записывает пользовательский отчёт.

    :param word_id: Идентификатор слова.
    :return: ``True`` при успешной отметке, иначе ``False``.
    """
    word = db.session.get(Word, word_id)
    if word is None:
        return False
    word.mistake = True
    db.session.commit()
    with Path("mistakes.txt").open("a", encoding="utf-8") as report_file:
        report_file.write(f"{datetime.now()} - {word.word} [{word.id}]\n")
    current_app.logger.info("Word reported as a mistake: %s [%s]", word.word, word.id)
    return True


def _answer_stats(user_id: int):
    """Строит подзапрос агрегированной статистики ответов по словам.

    :param user_id: Идентификатор пользователя.
    :return: SQLAlchemy-подзапрос с количеством ошибок и верных ответов.
    """
    return (
        db.session.query(
            Action.word_id,
            func.sum(
                case((Action.action == Action.WRONG_ANSWER, 1), else_=0)
            ).label("wrong_count"),
            func.sum(
                case((Action.action == Action.RIGHT_ANSWER, 1), else_=0)
            ).label("right_count"),
        )
        .filter(Action.user_id == user_id, Action.word_id.is_not(None))
        .group_by(Action.word_id)
        .subquery()
    )


def _recent_note_ids(
    user_id: int,
    note_type: str,
    limit: int = 3,
) -> list[int]:
    """Возвращает последние идентификаторы карточек заданного типа.

    :param user_id: Идентификатор пользователя.
    :param note_type: Тип карточки: ``word`` или ``sentence``.
    :param limit: Максимальное количество идентификаторов.
    :return: Идентификаторы от нового действия к старому.
    """
    note_column = (
        Action.sentence_id if note_type == "sentence" else Action.word_id
    )
    return list(db.session.scalars(
        select(note_column)
        .where(Action.user_id == user_id, note_column.is_not(None))
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
