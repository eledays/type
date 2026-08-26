import random
from pathlib import Path

from flask import current_app

from app.models import User
def choose_background(user: User) -> Path:
    """Выбирает фоновое изображение для ленты.

    :param user: Пользователь, для которого выбирается тема фона.
    :return: Путь к случайному WebP-фону или исходному изображению.
    """
    theme = "dark"
    directory = (
        Path(current_app.static_folder or "app/static")
        / "img"
        / "backs"
        / theme
    )
    webp_files = [path for path in directory.glob("*.webp") if path.is_file()]
    files = webp_files or [path for path in directory.iterdir() if path.is_file()]
    # This randomness only selects a visual background.
    return random.choice(files)  # nosec B311
