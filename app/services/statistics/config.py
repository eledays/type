from typing import Dict


class StatisticsConfig:
    """
    Конфигурация для расчета статистических показателей.
    """

    # === DIFFICULTY SCORE SETTINGS ===

    # Коэффициент веса пропусков относительно неправильных ответов
    SKIP_WEIGHT_MULTIPLIER = 1.5

    # Сглаживающие факторы (чтобы избежать крайних значений 0.0 и 1.0)
    USER_DIFFICULTY_SMOOTHING = 1  # Для индивидуальной статистики
    GLOBAL_DIFFICULTY_SMOOTHING = 5  # Для глобальной статистики (более консервативный)

    # Значение по умолчанию для новых слов без статистики
    DEFAULT_DIFFICULTY_SCORE = 0.5

    # === TIME SCORE SETTINGS (на основе давности последнего ответа) ===

    # Базовый период забывания в днях (соответствует time_score = 1.0)
    BASE_FORGETTING_DAYS = 7.0

    # Максимальный период для учета (в днях)
    MAX_FORGETTING_DAYS = 365.0

    # Диапазон итогового time_score
    MIN_TIME_SCORE = 0.1  # Недавний ответ (не нужно повторять)
    MAX_TIME_SCORE = 5.0  # Очень давний ответ (срочно повторить)

    # Значение по умолчанию для time_score (для новых слов)
    DEFAULT_TIME_SCORE = 2.0  # Новые слова имеют средний приоритет

    # === STREAK SETTINGS ===

    # Минимальная длина streak для бонусов (если понадобится в будущем)
    MIN_STREAK_FOR_BONUS = 3

    @classmethod
    def get_config_dict(cls) -> Dict[str, float]:
        """Возвращает все настройки в виде словаря для логирования или API."""
        return {
            "skip_weight_multiplier": cls.SKIP_WEIGHT_MULTIPLIER,
            "user_difficulty_smoothing": cls.USER_DIFFICULTY_SMOOTHING,
            "global_difficulty_smoothing": cls.GLOBAL_DIFFICULTY_SMOOTHING,
            "default_difficulty_score": cls.DEFAULT_DIFFICULTY_SCORE,
            "base_forgetting_days": cls.BASE_FORGETTING_DAYS,
            "max_forgetting_days": cls.MAX_FORGETTING_DAYS,
            "min_time_score": cls.MIN_TIME_SCORE,
            "max_time_score": cls.MAX_TIME_SCORE,
            "default_time_score": cls.DEFAULT_TIME_SCORE,
            "min_streak_for_bonus": cls.MIN_STREAK_FOR_BONUS,
        }

    @classmethod
    def update_from_dict(cls, config: Dict[str, float]) -> None:
        """Обновляет настройки из словаря (для ИИ-оптимизации или A/B тестов)."""
        if "skip_weight_multiplier" in config:
            cls.SKIP_WEIGHT_MULTIPLIER = config["skip_weight_multiplier"]
        if "user_difficulty_smoothing" in config:
            cls.USER_DIFFICULTY_SMOOTHING = config["user_difficulty_smoothing"]
        if "global_difficulty_smoothing" in config:
            cls.GLOBAL_DIFFICULTY_SMOOTHING = config["global_difficulty_smoothing"]
        if "default_difficulty_score" in config:
            cls.DEFAULT_DIFFICULTY_SCORE = config["default_difficulty_score"]
        if "base_forgetting_days" in config:
            cls.BASE_FORGETTING_DAYS = config["base_forgetting_days"]
        if "max_forgetting_days" in config:
            cls.MAX_FORGETTING_DAYS = config["max_forgetting_days"]
        if "min_time_score" in config:
            cls.MIN_TIME_SCORE = config["min_time_score"]
        if "max_time_score" in config:
            cls.MAX_TIME_SCORE = config["max_time_score"]
        if "default_time_score" in config:
            cls.DEFAULT_TIME_SCORE = config["default_time_score"]
