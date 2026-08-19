from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.action import Action
    from app.models.category import Category


class PracticeItem(db.Model):
    """Базовая модель карточки практики."""

    __tablename__ = "practice_item"
    __table_args__ = (
        CheckConstraint(
            "type IN ('spelling', 'paronym')",
            name="ck_practice_item_type",
        ),
        CheckConstraint(
            "type != 'spelling' OR category_id IS NOT NULL",
            name="ck_spelling_category_required",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    task_number: Mapped[int | None] = mapped_column(Integer, index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id"), index=True
    )
    explanation: Mapped[str | None] = mapped_column(String(2048))

    category: Mapped[Category | None] = relationship(back_populates="items")
    actions: Mapped[list[Action]] = relationship(
        back_populates="practice_item",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "practice_item",
    }

    def get_answers(self) -> list[str]:
        """Возвращает варианты ответа для карточки.

        :return: Новый список вариантов ответа.
        :raises NotImplementedError: Если тип упражнения не реализовал варианты.
        """
        raise NotImplementedError

    def get_correct_answer(self) -> str:
        """Возвращает правильный ответ для карточки.

        :return: Правильный ответ в форме, ожидаемой от пользователя.
        :raises NotImplementedError: Если тип упражнения не реализовал ответ.
        """
        raise NotImplementedError

    def get_prompt(self) -> str:
        """Возвращает текст карточки с пропуском.

        :return: Текст задания для отображения.
        :raises NotImplementedError: Если тип упражнения не реализовал текст.
        """
        raise NotImplementedError
