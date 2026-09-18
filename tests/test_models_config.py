from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Action, LegalAcceptance, UserPracticeStats
from app.time_utils import utc_now
from config import AppSettings
from tests.base import AppTestCase

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

    def test_database_rejects_unknown_action_type(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            word = self.make_word()
            db.session.add(Action(
                user_id=user_id,
                practice_item_id=word.id,
                action=999,
            ))
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_database_rejects_invalid_aggregate_values(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            stats = db.session.get(UserPracticeStats, user_id)
            stats.current_streak = 2
            stats.best_streak = 1
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

            stats = db.session.get(UserPracticeStats, user_id)
            stats.right_count = -1
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_only_one_active_acceptance_exists_per_document_set(self) -> None:
        user_id = self.current_user_id()
        versions = {
            "terms_version": "v1",
            "privacy_version": "v1",
            "personal_data_consent_version": "v1",
        }
        with self.app.app_context():
            db.session.add_all([
                LegalAcceptance(user_id=user_id, **versions),
                LegalAcceptance(user_id=user_id, **versions),
            ])
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

            revoked = LegalAcceptance(
                user_id=user_id,
                revoked_at=utc_now(),
                **versions,
            )
            active = LegalAcceptance(user_id=user_id, **versions)
            db.session.add_all([revoked, active])
            db.session.commit()
            assert LegalAcceptance.query.count() == 2


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
        assert exported["RATE_LIMIT_ANALYTICS_SEARCH"] == "60 per minute"
        assert exported["RATELIMIT_HEADERS_ENABLED"]
        assert exported["TRUSTED_PROXY_COUNT"] == 0
        assert exported["MAX_CONTENT_LENGTH"] == 65_536
        assert exported["ANALYTICS_TIMEZONE"] == "Europe/Moscow"
        assert exported["LOG_FORMAT"] == "json"
        assert exported["METRICS_TOKEN"] is None
        assert exported["LEGAL_OPERATOR_NAME"] == "Test operator"
        assert exported["LEGAL_CONSENT_REQUIRED"]
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
            {
                "SECRET_KEY": TEST_SECRET,
                "ANALYTICS_TIMEZONE": "Not/A-Timezone",
            },
            {
                "SECRET_KEY": TEST_SECRET,
                "LEGAL_OPERATOR_NAME": None,
                "LEGAL_CONTACT_EMAIL": None,
            },
            {"SECRET_KEY": TEST_SECRET, "METRICS_TOKEN": "too-short"},
        ):
            with pytest.raises(ValidationError):
                AppSettings(**values)
