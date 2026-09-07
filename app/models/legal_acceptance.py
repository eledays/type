from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.time_utils import utc_now

if TYPE_CHECKING:
    from app.models.user import User


class LegalAcceptance(db.Model):
    """Audit record proving acceptance of a specific document set."""

    __tablename__ = "legal_acceptance"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    terms_version: Mapped[str] = mapped_column(String(32), nullable=False)
    privacy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    personal_data_consent_version: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    user: Mapped[User] = relationship(back_populates="legal_acceptances")
