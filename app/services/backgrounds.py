import random
from pathlib import Path

from flask import current_app

from app.models import User
from app.utils import get_cached_strike


def choose_background(user: User) -> Path:
    strike = get_cached_strike(user.id)
    levels = current_app.config["STRIKE_LEVELS"]
    use_yellow = user.settings.strike and levels[0] <= strike < levels[1]
    theme = "yellow" if use_yellow else "dark"
    directory = (
        Path(current_app.static_folder or "app/static")
        / "img"
        / "backs"
        / theme
    )
    return random.choice([path for path in directory.iterdir() if path.is_file()])
