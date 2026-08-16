from datetime import time

from sqlalchemy import Boolean, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column

from app import db


class Settings(db.Model):
    __tablename__ = "settings"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
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
