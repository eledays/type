from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.practice_item import PracticeItem
    from app.models.user import User


class ErrorReport(db.Model):
    """Сообщение пользователя об ошибке в приложении или упражнении."""

    __tablename__ = "error_report"
    __table_args__ = (
        Index("ix_error_report_item_created", "practice_item_id", "created_at"),
        Index("ix_error_report_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    practice_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("practice_item.id", ondelete="SET NULL")
    )
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    user: Mapped[User] = relationship(back_populates="error_reports")
    practice_item: Mapped[PracticeItem | None] = relationship(
        back_populates="error_reports"
    )
