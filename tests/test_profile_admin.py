from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import event

from tests.base import AppTestCase

from app.extensions import db
from app.models import Action, SpellingExercise, User
from app.utils import get_strike, get_user_stats


class TestProfile(AppTestCase):
    def test_settings_accept_boolean_and_time_values(self) -> None:
        response = self.client.patch(
            "/api/v1/profile/settings",
            json={
                "strike": False,
                "notification": True,
                "notification_time": "08:45",
                "day_results_time": "21:10",
            },
        )
        assert response.status_code == 200
        user_id = self.current_user_id()
        with self.app.app_context():
            settings = db.session.get(User, user_id).settings
            assert not settings.strike
            assert settings.notification
            assert settings.notification_time.strftime("%H:%M") == "08:45"
            assert settings.day_results_time.strftime("%H:%M") == "21:10"

    def test_settings_reject_unknown_fields_wrong_types_and_bad_times(self) -> None:
        cases = [
            ({"unknown": True}, "Unknown settings"),
            ({"strike": 1}, "strike must be boolean"),
            ({"notification_time": "25:00"}, "HH:MM"),
            ([], "Invalid JSON"),
        ]
        for payload, message in cases:
            response = self.client.patch(
                "/api/v1/profile/settings", json=payload
            )
            assert response.status_code == 400
            assert message in response.get_json()["message"]

    def test_only_database_admin_can_toggle_admin_mode(self) -> None:
        denied = self.client.patch(
            "/api/v1/profile/settings", json={"admin": True}
        )
        assert denied.status_code == 403

        user_id = self.current_user_id()
        with self.app.app_context():
            db.session.get(User, user_id).is_admin = True
            db.session.commit()
        enabled = self.client.patch(
            "/api/v1/profile/settings", json={"admin": True}
        )
        assert enabled.status_code == 200
        with self.client.session_transaction() as browser_session:
            assert browser_session["admin"]

    def test_background_response_disables_browser_caching(self) -> None:
        image_path = self.app.static_folder + "/img/backs/dark/0.jpeg"
        with patch("app.routes.profile.api.choose_background", return_value=image_path):
            response = self.client.get("/api/v1/profile/background")
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == (
            "no-cache, no-store, must-revalidate"
        )
        assert response.headers["Pragma"] == "no-cache"
        response.close()

    def test_profile_stats_calculate_counts_streak_percentage_and_time(self) -> None:
        user_id = self.current_user_id()
        start = datetime(2026, 1, 1, 10, 0)
        with self.app.app_context():
            word = self.make_word()
            actions = [
                Action(user_id=user_id, practice_item_id=word.id, action=Action.RIGHT_ANSWER, datetime=start),
                Action(user_id=user_id, practice_item_id=word.id, action=Action.RIGHT_ANSWER, datetime=start + timedelta(seconds=20)),
                Action(user_id=user_id, practice_item_id=word.id, action=Action.WRONG_ANSWER, datetime=start + timedelta(seconds=50)),
                Action(user_id=user_id, practice_item_id=word.id, action=Action.SKIP, datetime=start + timedelta(minutes=20)),
            ]
            db.session.add_all(actions)
            db.session.commit()
            assert get_strike(user_id) == 0
            assert get_user_stats(user_id) == {
                "correct": 2,
                "mistakes": 1,
                "skips": 1,
                "correct_percent": 66.7,
                "avg_time_per_word": 25.0,
                "best_streak": 2,
            }

    def test_profile_stats_do_not_scan_action_history(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            word = self.make_word()
            db.session.add(Action(
                user_id=user_id,
                practice_item_id=word.id,
                action=Action.RIGHT_ANSWER,
            ))
            db.session.commit()
            db.session.expunge_all()
            statements: list[str] = []

            def capture_statement(
                _connection, _cursor, statement, _parameters, _context, _many
            ) -> None:
                statements.append(statement)

            event.listen(db.engine, "before_cursor_execute", capture_statement)
            try:
                get_user_stats(user_id)
            finally:
                event.remove(
                    db.engine, "before_cursor_execute", capture_statement
                )

            assert any("user_practice_stats" in sql for sql in statements)
            assert not any("FROM action" in sql for sql in statements)


class TestAdminApi(AppTestCase):
    @pytest.fixture(autouse=True)
    def admin_context(self, app_context):
        self.user_id = self.current_user_id()
        with self.app.app_context():
            self.word_id = self.make_word().id

    def test_non_admin_is_forbidden(self) -> None:
        response = self.client.patch(
            f"/api/v1/admin/words/{self.word_id}/explanation",
            json={"explanation": "Правило"},
        )
        assert response.status_code == 403

    def test_admin_can_update_explanation_and_delete_answer(self) -> None:
        with self.app.app_context():
            db.session.get(User, self.user_id).is_admin = True
            db.session.commit()

        updated = self.client.patch(
            f"/api/v1/admin/words/{self.word_id}/explanation",
            json={"explanation": "Проверочное слово"},
        )
        deleted = self.client.delete(
            f"/api/v1/admin/words/{self.word_id}/answers",
            json={"answer": "а"},
        )
        protected = self.client.delete(
            f"/api/v1/admin/words/{self.word_id}/answers",
            json={"answer": "о"},
        )
        assert updated.status_code == 200
        assert deleted.status_code == 200
        assert protected.status_code == 404
        with self.app.app_context():
            word = db.session.get(SpellingExercise, self.word_id)
            assert word.explanation == "Проверочное слово"
            assert word.answers == ["о"]

    def test_admin_endpoints_validate_payload_and_missing_resources(self) -> None:
        with self.app.app_context():
            db.session.get(User, self.user_id).is_admin = True
            db.session.commit()

        invalid = self.client.patch(
            f"/api/v1/admin/words/{self.word_id}/explanation",
            json={"explanation": 12},
        )
        absent_word = self.client.patch(
            "/api/v1/admin/words/999/explanation", json={"explanation": "x"}
        )
        absent_answer = self.client.delete(
            f"/api/v1/admin/words/{self.word_id}/answers",
            json={"answer": "ы"},
        )
        assert invalid.status_code == 400
        assert absent_word.status_code == 404
        assert absent_answer.status_code == 404
