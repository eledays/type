from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class Settings(db.Model):
    __tablename__ = "settings"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    strike: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    user: Mapped[User] = relationship(back_populates="settings")
