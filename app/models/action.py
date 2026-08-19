from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.sentence import Sentence
    from app.models.user import User
    from app.models.word import Word


class Action(db.Model):
    __tablename__ = "action"
    __table_args__ = (
        CheckConstraint(
            "word_id IS NULL OR sentence_id IS NULL",
            name="ck_action_single_note",
        ),
        Index("ix_action_user_word", "user_id", "word_id"),
        Index("ix_action_user_sentence", "user_id", "sentence_id"),
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
    word_id: Mapped[int | None] = mapped_column(
        ForeignKey("word.id", ondelete="SET NULL")
    )
    sentence_id: Mapped[int | None] = mapped_column(
        ForeignKey("sentence.id", ondelete="SET NULL")
    )
    action: Mapped[int] = mapped_column(Integer, nullable=False)
    datetime: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    user: Mapped[User] = relationship(back_populates="actions")
    word: Mapped[Word | None] = relationship(back_populates="actions")
    sentence: Mapped[Sentence | None] = relationship(back_populates="actions")
