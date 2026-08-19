from unittest.mock import patch

import pytest

from tests.base import AppTestCase

from app.extensions import db
from app.models import Action, User, Word
from app.services.practice import PracticeError, select_card


class TestPracticeApi(AppTestCase):
    def test_attempt_rejects_invalid_payloads_and_unknown_words(self) -> None:
        cases = [
            ({}, "invalid_attempt", 400),
            ({"word_id": "1", "answer": "о"}, "invalid_attempt", 400),
            ({"word_id": 999, "answer": "о"}, "word_not_found", 404),
        ]
        for payload, error, status in cases:
            response = self.client.post("/api/v1/attempts", json=payload)
            assert response.status_code == status
            assert response.get_json()["error"] == error

        response = self.client.post(
            "/api/v1/attempts", data="not json", content_type="text/plain"
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid_json"

    def test_right_and_wrong_answers_update_actions_and_strike(self) -> None:
        with self.app.app_context():
            word_id = self.make_word().id

        right = self.client.post(
            "/api/v1/attempts", json={"word_id": word_id, "answer": "о"}
        ).get_json()
        wrong = self.client.post(
            "/api/v1/attempts", json={"word_id": word_id, "answer": "и"}
        ).get_json()

        assert right["correct"]
        assert right["full_word"] == "молоко"
        assert right["strike"]["n"] == 1
        assert not wrong["correct"]
        assert wrong["strike"]["n"] == 0
        with self.app.app_context():
            assert [
                action.action for action in Action.query.order_by(Action.id)
            ] == [Action.RIGHT_ANSWER, Action.WRONG_ANSWER]

    def test_anonymous_quota_blocks_further_attempts_and_skips(self) -> None:
        with self.app.app_context():
            word_id = self.make_word().id

        for _ in range(3):
            response = self.client.post(
                "/api/v1/attempts", json={"word_id": word_id, "answer": "о"}
            )
            assert response.status_code == 200

        blocked = self.client.post(
            "/api/v1/attempts", json={"word_id": word_id, "answer": "о"},
            headers={"Referer": "/?task=4"},
        )
        assert blocked.status_code == 403
        assert blocked.get_json()["error"] == "anonymous_limit_reached"
        assert "/auth" in blocked.get_json()["login_url"]

        blocked_skip = self.client.post(
            "/api/v1/attempts/skip", json={"word_id": word_id}
        )
        assert blocked_skip.status_code == 403

    def test_registered_user_has_no_quota(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            user = db.session.get(User, user_id)
            user.yandex_id = "yandex-user"
            word_id = self.make_word().id
            db.session.commit()

        for _ in range(5):
            response = self.client.post(
                "/api/v1/attempts", json={"word_id": word_id, "answer": "о"}
            )
            assert response.status_code == 200
            assert response.get_json()["anonymous_remaining"] is None

    def test_duplicate_skip_does_not_create_another_action(self) -> None:
        with self.app.app_context():
            word_id = self.make_word().id

        first = self.client.post(
            "/api/v1/attempts/skip", json={"word_id": word_id}
        )
        second = self.client.post(
            "/api/v1/attempts/skip", json={"word_id": word_id}
        )
        assert first.status_code == 200
        assert second.status_code == 200
        with self.app.app_context():
            assert Action.query.filter_by(action=Action.SKIP).count() == 1

    def test_skip_and_swipe_validate_word_id(self) -> None:
        bad_skip = self.client.post("/api/v1/attempts/skip", json={"word_id": "1"})
        missing_swipe = self.client.get("/api/v1/swipe-permission")
        unknown_skip = self.client.post(
            "/api/v1/attempts/skip", json={"word_id": 999}
        )
        assert bad_skip.status_code == 400
        assert missing_swipe.status_code == 400
        assert unknown_skip.status_code == 404

    def test_swipe_is_blocked_during_a_long_streak_for_a_new_word(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            target_id = self.make_word(word="ц_ль").id
            previous_ids = [
                self.make_word(word=f"сл_во{index}").id for index in range(4)
            ]
            db.session.add_all([
                Action(
                    user_id=user_id,
                    word_id=word_id,
                    action=Action.RIGHT_ANSWER,
                )
                for word_id in previous_ids
            ])
            db.session.commit()
        with self.client.session_transaction() as browser_session:
            browser_session["strike"] = 4

        blocked = self.client.get(
            f"/api/v1/swipe-permission?word_id={target_id}"
        )
        allowed_recent = self.client.get(
            f"/api/v1/swipe-permission?word_id={previous_ids[-1]}"
        )
        assert blocked.get_json() == {"status": "no"}
        assert allowed_recent.get_json() == {"status": "yes"}

    def test_card_selection_supports_task_category_and_mistakes(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            first = self.make_word(word="д_м", task_number=9, category_name="Корни")
            second = self.make_word(word="л_с", task_number=10, category_name="Лес")
            db.session.add_all([
                Action(user_id=user_id, word_id=second.id, action=Action.WRONG_ANSWER),
                Action(user_id=user_id, word_id=second.id, action=Action.WRONG_ANSWER),
                Action(user_id=user_id, word_id=second.id, action=Action.RIGHT_ANSWER),
            ])
            db.session.commit()
            user = db.session.get(User, user_id)
            assert select_card(user, task_id="9").note.id == first.id
            assert (
                select_card(user, category_id=str(second.category_id)).note.id
                == second.id
            )
            assert select_card(user, mistakes=True).note.id == second.id

    def test_card_selection_returns_clear_not_found_errors(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            user = db.session.get(User, user_id)
            with pytest.raises(PracticeError, match="Category not found"):
                select_card(user, category_id="999")
            with pytest.raises(PracticeError, match="No words available"):
                select_card(user)

    def test_word_report_marks_word_and_handles_missing_word(self) -> None:
        with self.app.app_context():
            word_id = self.make_word().id

        with patch("app.services.practice.Path") as path:
            created = self.client.post(f"/api/v1/words/{word_id}/reports")
        missing = self.client.post("/api/v1/words/999/reports")

        assert created.status_code == 201
        assert missing.status_code == 404
        path.return_value.open.assert_called_once()
        with self.app.app_context():
            assert db.session.get(Word, word_id).mistake
