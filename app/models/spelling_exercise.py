from __future__ import annotations

import random

from sqlalchemy import CheckConstraint, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.extensions import db
from app.models.practice_item import PracticeItem


class SpellingExercise(PracticeItem):
    """Упражнение на вставку символа в слово."""

    __tablename__ = "spelling_exercise"
    __table_args__ = (
        CheckConstraint(
            "correct_answer != ''",
            name="ck_spelling_correct_answer_not_empty",
        ),
    )

    id: Mapped[int] = mapped_column(
        ForeignKey("practice_item.id", ondelete="CASCADE"), primary_key=True
    )
    word: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    answers: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(128), nullable=False)

    __mapper_args__ = {"polymorphic_identity": "spelling"}

    @validates("answers")
    def validate_answers(self, key: str, value: list[str]) -> list[str]:
        """Проверяет непустой список вариантов и наличие правильного ответа.

        :param key: Имя проверяемого ORM-поля.
        :param value: Новый список вариантов ответа.
        :return: Проверенный список вариантов.
        :raises ValueError: Если список пуст или не содержит правильный ответ.
        """
        if not value:
            raise ValueError("Answer options cannot be empty")
        correct_answer = getattr(self, "correct_answer", None)
        if correct_answer and correct_answer not in value:
            raise ValueError("Correct answer must be one of the options")
        return value

    @validates("correct_answer")
    def validate_correct_answer(self, key: str, value: str) -> str:
        """Проверяет явно заданный правильный ответ.

        :param key: Имя проверяемого ORM-поля.
        :param value: Новый правильный ответ.
        :return: Проверенный правильный ответ.
        :raises ValueError: Если ответ пуст или отсутствует среди вариантов.
        """
        if not value:
            raise ValueError("Correct answer cannot be empty")
        answers = getattr(self, "answers", None)
        if answers and value not in answers:
            raise ValueError("Correct answer must be one of the options")
        return value

    def get_answers(self) -> list[str]:
        """Возвращает копию вариантов ответа в случайном порядке.

        :return: Новый перемешанный список вариантов.
        """
        # This randomness only controls presentation order.
        return random.sample(  # nosec B311
            self.answers, k=len(self.answers)
        )

    def get_correct_answer(self) -> str:
        """Возвращает явно сохранённый правильный ответ.

        :return: Правильный вариант ответа.
        """
        return self.correct_answer

    def get_prompt(self) -> str:
        """Возвращает слово с пропуском.

        :return: Шаблон слова для отображения.
        """
        return self.word
