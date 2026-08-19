from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import random
from typing import Any

from flask import current_app, session
from pymorphy3.analyzer import MorphAnalyzer
from sqlalchemy import and_, case, func

from app.extensions import db
from app.models import Action, Category, Sentence, User, Word
from app.utils import add_action, get_anonymous_actions_remaining, get_cached_strike


class PracticeError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class Card:
    note: Word | Sentence
    info: list[str]


def select_card(
    user: User,
    task_id: str = "",
    category_id: str = "",
    mistakes: bool = False,
) -> Card:
    if task_id == "5":
        sentence = Sentence.query.order_by(func.random()).first()
        if sentence is None:
            raise PracticeError("sentence_not_found", "No sentences available", 404)
        return Card(sentence, [f'Фильтр: "Задание №{task_id}"'])

    category = (
        db.session.get(Category, int(category_id))
        if category_id.isdigit()
        else None
    )
    if task_id:
        base_words = Word.query.filter(Word.task_number == task_id)
        info = [f'Фильтр: "Задание №{task_id}"']
    elif category_id:
        if category is None:
            raise PracticeError("category_not_found", "Category not found", 404)
        base_words = Word.query.filter(Word.category_id == category.id)
        info = [f'Фильтр: "Категория {category.name}"']
    elif mistakes:
        word = _mistake_word(user.id)
        if word is None:
            raise PracticeError("word_not_found", "No words available", 404)
        return Card(word, ['Фильтр: "Неверные ответы"'])
    else:
        base_words = Word.query
        info = []

    unseen_words = base_words.outerjoin(
        Action,
        and_(Word.id == Action.word_id, Action.user_id == user.id),
    ).filter(Action.id.is_(None))

    stats = _answer_stats(user.id)
    difficulty = stats.c.wrong_count - stats.c.right_count
    difficult_words = (
        base_words.join(stats, Word.id == stats.c.word_id)
        .filter(difficulty > 0)
        .order_by(difficulty.desc())
        .limit(50)
        .all()
    )
    unseen_count = unseen_words.count()
    difficult_count = len(difficult_words)
    choose_unseen = unseen_count > 0 and (
        difficult_count == 0
        or random.randrange(unseen_count + difficult_count) < unseen_count
    )

    if choose_unseen:
        word = unseen_words.order_by(func.random()).first()
        info.append("Это слово встретилось первый раз")
    elif difficult_words:
        word = random.choice(difficult_words)
        info.append(
            "Это слово встретилось из-за большого количества ошибок"
        )
    else:
        word = base_words.order_by(func.random()).first()
        info.append("Это слово встретилось случайно")

    if word is None:
        raise PracticeError("word_not_found", "No words available", 404)
    return Card(word, info)


def check_answer(user: User, note_id: int, answer: str) -> dict[str, Any]:
    _ensure_quota(user)
    is_paronym = len(answer) > 2 and answer.islower()
    if is_paronym:
        note = db.session.get(Sentence, note_id)
        if note is None:
            raise PracticeError("sentence_not_found", "Sentence not found", 404)
        parsed_word = MorphAnalyzer().parse(note.word.word)[0]
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
    if not is_paronym:
        add_action(
            user_id=user.id,
            word_id=note_id,
            action=Action.RIGHT_ANSWER if correct else Action.WRONG_ANSWER,
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


def can_swipe(user: User, word_id: int) -> bool:
    if not user.settings.strike:
        return True
    last_ids = [
        action.word_id
        for action in Action.query.filter(Action.user_id == user.id)
        .order_by(Action.datetime.desc())
        .limit(3)
    ]
    return word_id in last_ids or get_cached_strike(user.id) <= 3


def skip_word(user: User, word_id: int) -> int:
    _ensure_quota(user)
    if db.session.get(Word, word_id) is None:
        raise PracticeError("word_not_found", "Word not found", 404)
    last_ids = [
        action.word_id
        for action in Action.query.filter(Action.user_id == user.id)
        .order_by(Action.datetime.desc())
        .limit(3)
    ]
    if word_id in last_ids:
        return get_cached_strike(user.id)
    if user.settings.strike:
        session["strike"] = 0
    add_action(user_id=user.id, word_id=word_id, action=Action.SKIP)
    return 0


def report_word(word_id: int) -> bool:
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
        .filter(Action.user_id == user_id)
        .group_by(Action.word_id)
        .subquery()
    )


def _mistake_word(user_id: int) -> Word | None:
    stats = _answer_stats(user_id)
    return (
        db.session.query(Word)
        .join(stats, Word.id == stats.c.word_id)
        .filter(stats.c.wrong_count > stats.c.right_count)
        .order_by(func.random())
        .first()
    )


def _ensure_quota(user: User) -> None:
    if get_anonymous_actions_remaining(user) == 0:
        raise PracticeError(
            "anonymous_limit_reached",
            "Войдите через Яндекс, чтобы продолжить.",
            403,
        )
