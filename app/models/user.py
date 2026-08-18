from __future__ import annotations

from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy import BigInteger, Boolean, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.action import Action
    from app.models.settings import Settings


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True
    )
    yandex_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True
    )
    yandex_login: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    settings: Mapped[Settings] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )
    actions: Mapped[list[Action]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def is_anonymous_account(self) -> bool:
        """Whether this row represents a browser-only temporary account."""
        return self.yandex_id is None and self.telegram_id is None

    @property
    def display_name(self) -> str:
        full_name = " ".join(
            part for part in (self.first_name, self.last_name) if part
        )
        return full_name or self.yandex_login or "Анонимный пользователь"
