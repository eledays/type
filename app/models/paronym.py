from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.paronym_group import ParonymGroup
    from app.models.sentence import Sentence


class Paronym(db.Model):
    __tablename__ = "paronym"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("paronym_group.id"), nullable=False
    )

    group: Mapped[ParonymGroup] = relationship(back_populates="paronyms")
    sentences: Mapped[list[Sentence]] = relationship(back_populates="word")

    def get_all_group_paronyms(self) -> list[str]:
        """Возвращает все слова из группы текущего паронима.

        :return: Список текстов паронимов.
        """
        return [paronym.word for paronym in self.group.paronyms]
