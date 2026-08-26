from __future__ import annotations

import random
from functools import lru_cache
from typing import TYPE_CHECKING

from pymorphy3 import MorphAnalyzer
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.practice_item import PracticeItem

if TYPE_CHECKING:
    from app.models.paronym import Paronym


@lru_cache(maxsize=1)
def get_morph_analyzer() -> MorphAnalyzer:
    """Возвращает общий морфологический анализатор процесса.

    :return: Кэшированный экземпляр ``MorphAnalyzer``.
    """
    return MorphAnalyzer()


@lru_cache(maxsize=8192)
def inflect_word(word: str, word_tags: str) -> str:
    """Кэширует неизменяемый результат склонения слова для карточек."""
    parsed_word = get_morph_analyzer().parse(word)[0]
    inflected_word = parsed_word.inflect(set(word_tags.split(",")))
    return inflected_word.word if inflected_word else parsed_word.word


class ParonymExercise(PracticeItem):
    """Упражнение на выбор паронима для предложения."""

    __tablename__ = "paronym_exercise"

    id: Mapped[int] = mapped_column(
        ForeignKey("practice_item.id", ondelete="CASCADE"), primary_key=True
    )
    sentence: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    paronym_id: Mapped[int] = mapped_column(
        ForeignKey("paronym.id"), nullable=False, index=True
    )
    word_tags: Mapped[str] = mapped_column(String, nullable=False)

    paronym: Mapped[Paronym] = relationship(back_populates="exercises")

    __mapper_args__ = {"polymorphic_identity": "paronym"}

    def _inflect(self, word: str) -> str:
        """Склоняет пароним в форму, требуемую предложением.

        :param word: Пароним в нормальной форме.
        :return: Склонённое слово или исходная разобранная форма.
        """
        return inflect_word(word, self.word_tags)

    def get_answers(self) -> list[str]:
        """Формирует склонённые варианты из группы паронимов.

        :return: Варианты ответов в случайном порядке.
        """
        answers = [
            self._inflect(paronym.word)
            for paronym in self.paronym.group.paronyms
        ]
        # This randomness only controls presentation order.
        return random.sample(answers, k=len(answers))  # nosec B311

    def get_correct_answer(self) -> str:
        """Возвращает правильный пароним в форме предложения.

        :return: Склонённый правильный ответ.
        """
        return self._inflect(self.paronym.word)

    def get_prompt(self) -> str:
        """Возвращает предложение с пропуском.

        :return: Текст предложения для отображения.
        """
        return self.sentence
