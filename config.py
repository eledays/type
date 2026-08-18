from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Backup settings
    backup_path: Path = Field(
        default=Path("backups"), validation_alias="BACKUP_PATH"
    )
    backup_period: float = Field(
        default=1, validation_alias="BACKUP_PERIOD", gt=0
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
    strike_levels: tuple[int, ...] = Field(
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

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 16:
            raise ValueError("SECRET_KEY must contain at least 16 characters")
        return value

    @field_validator("strike_levels")
    @classmethod
    def validate_strike_levels(
        cls, value: tuple[int, ...]
    ) -> tuple[int, ...]:
        if not value:
            raise ValueError("STRIKE_LEVELS must not be empty")
        if any(level <= 0 for level in value):
            raise ValueError("STRIKE_LEVELS must contain positive integers")
        if tuple(sorted(set(value))) != value:
            raise ValueError(
                "STRIKE_LEVELS must be unique and sorted in ascending order"
            )
        return value

    def to_flask_config(self) -> dict[str, Any]:
        """Return validated settings using Flask extension key names."""
        return {
            "DEBUG": self.debug,
            "FLASK_PORT": self.flask_port,
            "FLASK_HOST": self.flask_host,
            "SQLALCHEMY_DATABASE_URI": self.database_url,
            "BACKUP_PATH": self.backup_path,
            "BACKUP_PERIOD": self.backup_period,
            "SECRET_KEY": self.secret_key.get_secret_value(),
            "STRIKE_LEVELS": self.strike_levels,
            "TASKS": self.tasks,
            "URL": self.url,
        }


settings = AppSettings()  # type: ignore
