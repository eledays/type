from __future__ import annotations

import random
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.action import Action
    from app.models.category import Category


class Word(db.Model):
    __tablename__ = "word"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    explanation: Mapped[str | None] = mapped_column(String(2048))
    answers: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    task_number: Mapped[int | None] = mapped_column(Integer, index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.id"), nullable=False, index=True
    )
    mistake: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    category: Mapped[Category] = relationship(back_populates="words")
    actions: Mapped[list[Action]] = relationship(back_populates="word")

    def get_answers(self) -> list[str]:
        """Возвращает копию вариантов ответа в случайном порядке.

        :return: Новый перемешанный список вариантов.
        """
        return random.sample(self.answers, k=len(self.answers))
