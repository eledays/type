import random
from functools import lru_cache
from pathlib import Path

from flask import current_app

from app.models import User


@lru_cache(maxsize=8)
def _theme_files(static_root: str, theme: str) -> tuple[Path, ...]:
    """Один раз строит упорядоченный манифест фоновых изображений."""
    directory = Path(static_root) / "img" / "backs" / theme
    webp_files = tuple(sorted(directory.glob("*.webp")))
    if webp_files:
        return webp_files
    return tuple(sorted(path for path in directory.iterdir() if path.is_file()))


def get_background_pools() -> dict[str, tuple[Path, ...]]:
    """Возвращает кэшированные наборы оптимизированных фонов по темам."""
    static_root = current_app.static_folder or "app/static"
    return {
        theme: _theme_files(static_root, theme)
        for theme in ("dark", "yellow")
    }


def choose_background(user: User) -> Path:
    """Выбирает фоновое изображение для ленты.

    :param user: Пользователь, для которого выбирается тема фона.
    :return: Путь к случайному WebP-фону или исходному изображению.
    """
    theme = "dark"
    files = _theme_files(current_app.static_folder or "app/static", theme)
    # This randomness only selects a visual background.
    return random.choice(files)  # nosec B311
