from datetime import timedelta

from pydantic import ValidationError
import pytest

from tests.base import AppTestCase
from config import AppSettings


TEST_SECRET = "a-secure-test-secret-with-32-characters"


class TestModel(AppTestCase):
    def test_word_returns_an_independent_answer_copy(self) -> None:
        with self.app.app_context():
            word = self.make_word(word="м_л_ко", answers=["о", "а"])
            answers = word.get_answers()
            assert sorted(answers) == ["а", "о"]
            assert answers is not word.answers

    def test_correct_answer_does_not_depend_on_option_order(self) -> None:
        with self.app.app_context():
            word = self.make_word(
                answers=["а", "о"],
                correct_answer="о",
            )
            assert word.get_correct_answer() == "о"

    def test_correct_answer_must_be_one_of_the_options(self) -> None:
        with self.app.app_context(), pytest.raises(ValueError):
            self.make_word(
                answers=["а", "и"],
                correct_answer="о",
            )


class TestConfig(AppTestCase):
    def test_settings_are_exported_with_flask_extension_names(self) -> None:
        settings = AppSettings(
            SECRET_KEY=TEST_SECRET,
            DATABASE_URL="sqlite:///custom.db",
            STRIKE_LEVELS=(10, 20, 30),
        )
        exported = settings.to_flask_config()
        assert exported["SQLALCHEMY_DATABASE_URI"] == "sqlite:///custom.db"
        assert exported["STRIKE_LEVELS"] == (10, 20, 30)
        assert exported["SECRET_KEY"] == TEST_SECRET
        assert exported["RATELIMIT_DEFAULT"] == "300 per minute"
        assert exported["RATELIMIT_APPLICATION"] == "3000 per hour"
        assert exported["RATELIMIT_HEADERS_ENABLED"]
        assert exported["TRUSTED_PROXY_COUNT"] == 0
        assert exported["MAX_CONTENT_LENGTH"] == 65_536
        assert exported["TRUSTED_HOSTS"] == ["type.eleday.ru"]
        assert exported["SESSION_COOKIE_SECURE"]
        assert exported["SESSION_COOKIE_HTTPONLY"]
        assert exported["SESSION_COOKIE_SAMESITE"] == "Lax"
        assert exported["REMEMBER_COOKIE_DURATION"] == timedelta(days=30)
        assert exported["HSTS_ENABLED"]

    def test_debug_defaults_disable_https_only_options(self) -> None:
        settings = AppSettings(
            SECRET_KEY=TEST_SECRET,
            DEBUG=True,
        )

        exported = settings.to_flask_config()

        assert not exported["SESSION_COOKIE_SECURE"]
        assert not exported["REMEMBER_COOKIE_SECURE"]
        assert not exported["HSTS_ENABLED"]

    @pytest.mark.parametrize(
        "levels",
        ("10,20,30", "[10, 20, 30]"),
    )
    def test_settings_accept_strike_levels_from_env_formats(
        self, levels: str
    ) -> None:
        settings = AppSettings(
            SECRET_KEY=TEST_SECRET,
            STRIKE_LEVELS=levels,
        )
        assert settings.strike_levels == (10, 20, 30)

    def test_settings_reject_weak_secrets_and_invalid_strike_levels(self) -> None:
        for values in (
            {"SECRET_KEY": "short"},
            {"SECRET_KEY": "replace-with-at-least-32-random-characters"},
            {"SECRET_KEY": TEST_SECRET, "STRIKE_LEVELS": "20,10"},
            {"SECRET_KEY": TEST_SECRET, "STRIKE_LEVELS": "10,10"},
            {"SECRET_KEY": TEST_SECRET, "STRIKE_LEVELS": "0,10"},
            {
                "SECRET_KEY": TEST_SECRET,
                "PRACTICE_CARD_BATCH_SIZE": 4,
                "PRACTICE_CARD_BATCH_MAX": 3,
            },
            {
                "SECRET_KEY": TEST_SECRET,
                "RATE_LIMIT_DEFAULT": "not a limit",
            },
            {"SECRET_KEY": TEST_SECRET, "URL": "http://example.com"},
            {
                "SECRET_KEY": TEST_SECRET,
                "YANDEX_REDIRECT_URI": "http://example.com/callback",
            },
            {
                "SECRET_KEY": TEST_SECRET,
                "DEBUG": True,
                "FLASK_HOST": "0.0.0.0",
            },
            {
                "SECRET_KEY": TEST_SECRET,
                "RATE_LIMIT_STORAGE_URI": "memory://",
            },
        ):
            with pytest.raises(ValidationError):
                AppSettings(**values)
