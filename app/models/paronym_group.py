from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.paronym import Paronym


class ParonymGroup(db.Model):
    __tablename__ = "paronym_group"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    paronyms: Mapped[list[Paronym]] = relationship(back_populates="group")
