from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.practice_item import PracticeItem
    from app.models.user import User


class Action(db.Model):
    __tablename__ = "action"
    __table_args__ = (
        Index("ix_action_user_item", "user_id", "practice_item_id"),
        Index("ix_action_user_datetime", "user_id", "datetime"),
        Index("ix_action_user_action", "user_id", "action"),
    )

    RIGHT_ANSWER: ClassVar[int] = 100
    WRONG_ANSWER: ClassVar[int] = 101
    SKIP: ClassVar[int] = 102
    SAVE_WORD: ClassVar[int] = 103

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )
    practice_item_id: Mapped[int] = mapped_column(
        ForeignKey("practice_item.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[int] = mapped_column(Integer, nullable=False)
    datetime: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    user: Mapped[User] = relationship(back_populates="actions")
    practice_item: Mapped[PracticeItem] = relationship(back_populates="actions")
