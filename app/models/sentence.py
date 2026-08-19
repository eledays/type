from __future__ import annotations

import random
from functools import lru_cache
from typing import TYPE_CHECKING, ClassVar

from pymorphy3 import MorphAnalyzer
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.paronym import Paronym

if TYPE_CHECKING:
    from app.models.action import Action


@lru_cache(maxsize=1)
def get_morph_analyzer() -> MorphAnalyzer:
    """Возвращает общий морфологический анализатор процесса.

    :return: Кэшированный экземпляр ``MorphAnalyzer``.
    """
    return MorphAnalyzer()


class Sentence(db.Model):
    __tablename__ = "sentence"

    explanation: ClassVar[str] = ""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sentence: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    word_id: Mapped[int] = mapped_column(
        ForeignKey("paronym.id"), nullable=False
    )
    word_tags: Mapped[str] = mapped_column(String, nullable=False)

    word: Mapped[Paronym] = relationship(back_populates="sentences")
    actions: Mapped[list[Action]] = relationship(back_populates="sentence")

    def get_answers(self) -> list[str]:
        """Формирует склонённые варианты паронимов для предложения.

        :return: Варианты ответов в случайном порядке.
        """
        analyzer = get_morph_analyzer()
        tags = set(self.word_tags.split(","))
        answers: list[str] = []

        for paronym in self.word.group.paronyms:
            parsed_word = analyzer.parse(paronym.word)[0]
            inflected_word = parsed_word.inflect(tags)
            answers.append(
                inflected_word.word if inflected_word else parsed_word.word
            )

        return random.sample(answers, k=len(answers))
