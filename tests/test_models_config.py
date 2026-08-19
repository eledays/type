from pydantic import ValidationError
import pytest

from tests.base import AppTestCase
from config import AppSettings


class TestModel(AppTestCase):
    def test_word_returns_an_independent_answer_copy(self) -> None:
        with self.app.app_context():
            word = self.make_word(word="м_л_ко", answers=["о", "а"])
            answers = word.get_answers()
            assert sorted(answers) == ["а", "о"]
            assert answers is not word.answers


class TestConfig(AppTestCase):
    def test_settings_are_exported_with_flask_extension_names(self) -> None:
        settings = AppSettings(
            SECRET_KEY="a-secure-test-secret",
            DATABASE_URL="sqlite:///custom.db",
            STRIKE_LEVELS=(10, 20, 30),
        )
        exported = settings.to_flask_config()
        assert exported["SQLALCHEMY_DATABASE_URI"] == "sqlite:///custom.db"
        assert exported["STRIKE_LEVELS"] == (10, 20, 30)
        assert exported["SECRET_KEY"] == "a-secure-test-secret"

    def test_settings_reject_weak_secrets_and_invalid_strike_levels(self) -> None:
        for values in (
            {"SECRET_KEY": "short"},
            {"SECRET_KEY": "a-secure-test-secret", "STRIKE_LEVELS": "20,10"},
            {"SECRET_KEY": "a-secure-test-secret", "STRIKE_LEVELS": "10,10"},
            {"SECRET_KEY": "a-secure-test-secret", "STRIKE_LEVELS": "0,10"},
            {
                "SECRET_KEY": "a-secure-test-secret",
                "PRACTICE_CARD_BATCH_SIZE": 4,
                "PRACTICE_CARD_BATCH_MAX": 3,
            },
        ):
            with pytest.raises(ValidationError):
                AppSettings(**values)
