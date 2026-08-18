from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db

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
    notification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notification_time: Mapped[time] = mapped_column(
        Time, nullable=False, default=lambda: time(12, 0)
    )
    day_results: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    day_results_time: Mapped[time] = mapped_column(
        Time, nullable=False, default=lambda: time(20, 0)
    )

    user: Mapped[User] = relationship(back_populates="settings")
