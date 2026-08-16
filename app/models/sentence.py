from __future__ import annotations

import random
from typing import ClassVar

from pymorphy3 import MorphAnalyzer
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db
from app.models.paronym import Paronym


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

    def get_answers(self) -> list[str]:
        """Return the paronym variants inflected for this sentence."""
        analyzer = MorphAnalyzer()
        tags = set(self.word_tags.split(","))
        answers: list[str] = []

        for paronym in self.word.group.paronyms:
            parsed_word = analyzer.parse(paronym.word)[0]
            inflected_word = parsed_word.inflect(tags)
            answers.append(
                inflected_word.word if inflected_word else parsed_word.word
            )

        return random.sample(answers, k=len(answers))

    def get_html(self) -> str:
        return self.sentence
