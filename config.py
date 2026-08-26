import json
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from limits import parse_many
from pydantic import (
    AliasChoices,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
        frozen=True,
    )

    # Database settings
    database_url: str = Field(
        default="sqlite:///app.db",
        validation_alias=AliasChoices(
            "DATABASE_URL", "SQLALCHEMY_DATABASE_URI"
        ),
        min_length=1,
    )

    # Flask settings
    secret_key: SecretStr = Field(validation_alias="SECRET_KEY")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    flask_host: str = Field(
        default='localhost', validation_alias="FLASK_HOST"
    )
    flask_port: int = Field(
        default=5000, validation_alias="FLASK_PORT", ge=1, le=65_535
    )
    strike_levels: Annotated[tuple[int, ...], NoDecode] = Field(
        default=(50, 100, 500, 1000), validation_alias="STRIKE_LEVELS"
    )

    tasks: dict[int, str] = Field(
        default_factory=lambda: {
            4: "Ударения",
            5: "Паронимы",
            9: "Правописание корней",
            10: "Правописание приставок",
            11: "Правописание суффиксов (кроме -Н-/-НН-)",
        },
        validation_alias="TASKS",
    )
    url: str = Field(
        default="https://type.eleday.ru/", validation_alias="URL"
    )

    # Yandex OAuth settings
    yandex_client_id: str | None = Field(
        default=None, validation_alias="YANDEX_CLIENT_ID"
    )
    yandex_client_secret: SecretStr | None = Field(
        default=None, validation_alias="YANDEX_CLIENT_SECRET"
    )
    yandex_redirect_uri: str | None = Field(
        default=None, validation_alias="YANDEX_REDIRECT_URI"
    )
    anonymous_action_limit: int = Field(
        default=30, validation_alias="ANONYMOUS_ACTION_LIMIT", ge=1
    )
    practice_card_batch_size: int = Field(
        default=3,
        validation_alias="PRACTICE_CARD_BATCH_SIZE",
        ge=1,
    )
    practice_card_batch_max: int = Field(
        default=12,
        validation_alias="PRACTICE_CARD_BATCH_MAX",
        ge=1,
    )
    practice_difficult_candidate_limit: int = Field(
        default=50,
        validation_alias="PRACTICE_DIFFICULT_CANDIDATE_LIMIT",
        ge=1,
    )
    practice_swipe_grace_strike: int = Field(
        default=3,
        validation_alias="PRACTICE_SWIPE_GRACE_STRIKE",
        ge=0,
    )
    rate_limit_default: str = Field(
        default="300 per minute",
        validation_alias="RATE_LIMIT_DEFAULT",
        min_length=1,
    )
    rate_limit_application: str = Field(
        default="3000 per hour",
        validation_alias="RATE_LIMIT_APPLICATION",
        min_length=1,
    )
    rate_limit_auth: str = Field(
        default="10 per minute",
        validation_alias="RATE_LIMIT_AUTH",
        min_length=1,
    )
    rate_limit_mutation: str = Field(
        default="120 per minute",
        validation_alias="RATE_LIMIT_MUTATION",
        min_length=1,
    )
    rate_limit_report: str = Field(
        default="5 per hour",
        validation_alias="RATE_LIMIT_REPORT",
        min_length=1,
    )
    rate_limit_storage_uri: str = Field(
        default="memory://",
        validation_alias="RATE_LIMIT_STORAGE_URI",
        min_length=1,
    )
    trusted_proxy_count: int = Field(
        default=0,
        validation_alias="TRUSTED_PROXY_COUNT",
        ge=0,
    )
    cookie_secure: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "COOKIE_SECURE", "SESSION_COOKIE_SECURE"
        ),
    )
    cookie_samesite: Literal["Lax", "Strict"] = Field(
        default="Lax",
        validation_alias=AliasChoices(
            "COOKIE_SAMESITE", "SESSION_COOKIE_SAMESITE"
        ),
    )
    remember_cookie_days: int = Field(
        default=30,
        validation_alias="REMEMBER_COOKIE_DAYS",
        ge=1,
        le=365,
    )
    hsts_enabled: bool | None = Field(
        default=None,
        validation_alias="HSTS_ENABLED",
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        """Проверяет минимальную длину секретного ключа.

        :param value: Секретный ключ приложения.
        :return: Проверенный секретный ключ.
        :raises ValueError: Если ключ короче шестнадцати символов.
        """
        if len(value.get_secret_value()) < 16:
            raise ValueError("SECRET_KEY must contain at least 16 characters")
        return value

    @field_validator("strike_levels", mode="before")
    @classmethod
    def parse_strike_levels(
        cls, value: Any
    ) -> tuple[Any, ...] | Any:
        """Принимает уровни серии из .env через запятую или JSON-массив."""
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if normalized.startswith("["):
            return json.loads(normalized)
        return tuple(level.strip() for level in normalized.split(","))

    @field_validator("strike_levels")
    @classmethod
    def validate_strike_levels(
        cls, value: tuple[int, ...]
    ) -> tuple[int, ...]:
        """Проверяет уровни серии на порядок и уникальность.

        :param value: Последовательность порогов серии.
        :return: Проверенная последовательность порогов.
        :raises ValueError: Если пороги пусты, неположительны или не упорядочены.
        """
        if not value:
            raise ValueError("STRIKE_LEVELS must not be empty")
        if any(level <= 0 for level in value):
            raise ValueError("STRIKE_LEVELS must contain positive integers")
        if tuple(sorted(set(value))) != value:
            raise ValueError(
                "STRIKE_LEVELS must be unique and sorted in ascending order"
            )
        return value

    @model_validator(mode="after")
    def validate_practice_batch_limits(self) -> "AppSettings":
        """Проверяет согласованность размеров пакета карточек.

        :return: Проверенный объект настроек.
        :raises ValueError: Если обычный размер пакета превышает максимум.
        """
        if self.practice_card_batch_size > self.practice_card_batch_max:
            raise ValueError(
                "PRACTICE_CARD_BATCH_SIZE must not exceed "
                "PRACTICE_CARD_BATCH_MAX"
            )
        return self

    @field_validator(
        "rate_limit_default",
        "rate_limit_application",
        "rate_limit_auth",
        "rate_limit_mutation",
        "rate_limit_report",
    )
    @classmethod
    def validate_rate_limit(cls, value: str) -> str:
        """Проверяет синтаксис лимита при запуске приложения."""
        try:
            parse_many(value)
        except ValueError as error:
            raise ValueError(f"Invalid rate limit: {value}") from error
        return value

    def to_flask_config(self) -> dict[str, Any]:
        """Преобразует настройки в словарь ключей Flask.

        :return: Проверенная конфигурация с именами, ожидаемыми расширениями.
        """
        secure_cookies = (
            not self.debug if self.cookie_secure is None else self.cookie_secure
        )
        hsts_enabled = (
            not self.debug if self.hsts_enabled is None else self.hsts_enabled
        )
        return {
            "DEBUG": self.debug,
            "FLASK_PORT": self.flask_port,
            "FLASK_HOST": self.flask_host,
            "SQLALCHEMY_DATABASE_URI": self.database_url,
            "SECRET_KEY": self.secret_key.get_secret_value(),
            "STRIKE_LEVELS": self.strike_levels,
            "TASKS": self.tasks,
            "URL": self.url,
            "YANDEX_CLIENT_ID": self.yandex_client_id,
            "YANDEX_CLIENT_SECRET": (
                self.yandex_client_secret.get_secret_value()
                if self.yandex_client_secret is not None
                else None
            ),
            "YANDEX_REDIRECT_URI": self.yandex_redirect_uri,
            "ANONYMOUS_ACTION_LIMIT": self.anonymous_action_limit,
            "PRACTICE_CARD_BATCH_SIZE": self.practice_card_batch_size,
            "PRACTICE_CARD_BATCH_MAX": self.practice_card_batch_max,
            "PRACTICE_DIFFICULT_CANDIDATE_LIMIT": (
                self.practice_difficult_candidate_limit
            ),
            "PRACTICE_SWIPE_GRACE_STRIKE": (
                self.practice_swipe_grace_strike
            ),
            "RATELIMIT_DEFAULT": self.rate_limit_default,
            "RATELIMIT_APPLICATION": self.rate_limit_application,
            "RATELIMIT_STORAGE_URI": self.rate_limit_storage_uri,
            "RATELIMIT_HEADERS_ENABLED": True,
            "RATE_LIMIT_AUTH": self.rate_limit_auth,
            "RATE_LIMIT_MUTATION": self.rate_limit_mutation,
            "RATE_LIMIT_REPORT": self.rate_limit_report,
            "TRUSTED_PROXY_COUNT": self.trusted_proxy_count,
            "SESSION_COOKIE_SECURE": secure_cookies,
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SAMESITE": self.cookie_samesite,
            "REMEMBER_COOKIE_SECURE": secure_cookies,
            "REMEMBER_COOKIE_HTTPONLY": True,
            "REMEMBER_COOKIE_SAMESITE": self.cookie_samesite,
            "REMEMBER_COOKIE_DURATION": timedelta(
                days=self.remember_cookie_days
            ),
            "HSTS_ENABLED": hsts_enabled,
        }


settings = AppSettings()  # type: ignore
