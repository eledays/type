from datetime import datetime, timedelta
import pytest

from tests.base import AppTestCase

from app.extensions import db
from app.models import (
    Action,
    ErrorReport,
    GlobalPracticeStats,
    Paronym,
    ParonymExercise,
    ParonymGroup,
    PracticeProgress,
    SpellingExercise,
    User,
)
from app.services.practice import PracticeError, select_card, select_cards


class TestPracticeApi(AppTestCase):
    def test_card_pool_returns_multiple_unique_cards_in_one_request(self) -> None:
        with self.app.app_context():
            words = [
                self.make_word(word=f"сл_во{index}") for index in range(4)
            ]
            excluded_id = words[0].id

        response = self.client.get(
            f"/api/v1/practice/cards?limit=3&task=4&exclude={excluded_id}"
        )
        assert response.status_code == 200
        cards = response.get_json()["cards"]
        assert len(cards) == 3
        assert response.headers["Cache-Control"] == "private, no-store"
        assert len({card["id"] for card in cards}) == 3
        assert excluded_id not in {card["id"] for card in cards}
        assert {card["type"] for card in cards} == {"spelling"}
        assert all(
            {
                "id", "type", "prompt", "blank", "answers", "info",
                "task", "stats",
            } <= card.keys()
            for card in cards
        )

    def test_cards_include_task_and_personal_word_stats(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            word = self.make_word(task_number=4)
            db.session.add_all([
                Action(
                    user_id=user_id,
                    practice_item_id=word.id,
                    action=Action.RIGHT_ANSWER,
                ),
                Action(
                    user_id=user_id,
                    practice_item_id=word.id,
                    action=Action.WRONG_ANSWER,
                ),
                Action(
                    user_id=user_id,
                    practice_item_id=word.id,
                    action=Action.SKIP,
                ),
            ])
            db.session.commit()
            word_id = word.id

        card = self.client.get(
            "/api/v1/practice/cards?limit=1&task=4"
        ).get_json()["cards"][0]

        assert card["task"] == {"number": 4, "title": "Ударения"}
        assert card["stats"] == {
            "correct": 1,
            "mistakes": 1,
            "skips": 1,
            "correct_percent": 50.0,
        }

        with self.app.app_context():
            progress = db.session.get(
                PracticeProgress, (user_id, word_id)
            )
            global_stats = db.session.get(GlobalPracticeStats, word_id)
            assert (
                progress.right_count,
                progress.wrong_count,
                progress.skip_count,
            ) == (1, 1, 1)
            assert (
                global_stats.right_count,
                global_stats.wrong_count,
                global_stats.skip_count,
            ) == (1, 1, 1)

    def test_card_pool_validates_limit_and_exclusions(self) -> None:
        invalid_limit = self.client.get("/api/v1/practice/cards?limit=20")
        invalid_filters = self.client.get(
            "/api/v1/practice/cards?task=4&mode=mistakes"
        )
        invalid_exclude = self.client.get(
            "/api/v1/practice/cards?exclude=one,two"
        )
        assert invalid_limit.status_code == 400
        assert invalid_limit.get_json()["error"] == "invalid_limit"
        assert invalid_filters.status_code == 400
        assert invalid_filters.get_json()["error"] == "incompatible_filters"
        assert invalid_exclude.status_code == 400
        assert invalid_exclude.get_json()["error"] == "invalid_exclude"

    def test_card_pool_uses_configured_default_and_maximum(self) -> None:
        with self.app.app_context():
            for index in range(4):
                self.make_word(word=f"п_кет{index}")
        self.app.config["PRACTICE_CARD_BATCH_SIZE"] = 2
        self.app.config["PRACTICE_CARD_BATCH_MAX"] = 2

        default_pool = self.client.get("/api/v1/practice/cards?task=4")
        oversized_pool = self.client.get(
            "/api/v1/practice/cards?task=4&limit=3"
        )

        assert len(default_pool.get_json()["cards"]) == 2
        assert oversized_pool.status_code == 400
        assert oversized_pool.get_json()["error"] == "invalid_limit"

    def test_unfiltered_feed_mixes_spelling_and_paronym_exercises(self) -> None:
        with self.app.app_context():
            spelling = self.make_word()
            category_id = spelling.category_id
            group = ParonymGroup()
            correct = Paronym(word="эффективный", group=group)
            Paronym(word="эффектный", group=group)
            paronym = ParonymExercise(
                sentence="Это _______ метод",
                paronym=correct,
                word_tags="nomn,sing,masc",
                task_number=5,
            )
            db.session.add(paronym)
            db.session.commit()
            paronym_id = paronym.id

        unfiltered = self.client.get("/api/v1/practice/cards?limit=2")
        task_filter = self.client.get(
            "/api/v1/practice/cards?limit=2&task=4"
        )
        category_filter = self.client.get(
            f"/api/v1/practice/cards?limit=2&category={category_id}"
        )
        paronym_filter = self.client.get(
            "/api/v1/practice/cards?limit=2&task=5"
        )
        excluded = self.client.get(
            f"/api/v1/practice/cards?limit=2&exclude={paronym_id}"
        )

        assert {card["type"] for card in unfiltered.get_json()["cards"]} == {
            "spelling",
            "paronym",
        }
        assert {card["type"] for card in task_filter.get_json()["cards"]} == {
            "spelling"
        }
        assert {
            card["type"] for card in category_filter.get_json()["cards"]
        } == {"spelling"}
        assert {
            card["type"] for card in paronym_filter.get_json()["cards"]
        } == {"paronym"}
        assert {card["type"] for card in excluded.get_json()["cards"]} == {
            "spelling"
        }

    def test_mistakes_filter_treats_all_exercise_types_equally(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            spelling = self.make_word()
            group = ParonymGroup()
            correct = Paronym(word="адресат", group=group)
            Paronym(word="адресант", group=group)
            paronym = ParonymExercise(
                sentence="Письмо получил _______",
                paronym=correct,
                word_tags="nomn,sing,masc",
                task_number=5,
            )
            db.session.add(paronym)
            db.session.flush()
            db.session.add_all([
                Action(
                    user_id=user_id,
                    practice_item_id=spelling.id,
                    action=Action.WRONG_ANSWER,
                ),
                Action(
                    user_id=user_id,
                    practice_item_id=paronym.id,
                    action=Action.WRONG_ANSWER,
                ),
            ])
            db.session.commit()
        response = self.client.get(
            "/api/v1/practice/cards?limit=2&mode=mistakes"
        )

        assert response.status_code == 200
        assert {card["type"] for card in response.get_json()["cards"]} == {
            "spelling",
            "paronym",
        }

    def test_explicit_word_type_does_not_depend_on_answer_shape(self) -> None:
        with self.app.app_context():
            word_id = self.make_word(
                word="проверка",
                answers=["другой", "длинныйответ"],
                correct_answer="длинныйответ",
            ).id

        response = self.client.post("/api/v1/attempts", json={
            "card_id": word_id,
            "card_type": "spelling",
            "answer": "длинныйответ",
        })
        assert response.status_code == 200
        assert response.get_json()["correct"]

    def test_sentence_actions_are_counted_and_reference_sentence(self) -> None:
        with self.app.app_context():
            group = ParonymGroup()
            correct = Paronym(word="эффективный", group=group)
            Paronym(word="эффектный", group=group)
            sentence = ParonymExercise(
                sentence="Это _______ метод",
                paronym=correct,
                word_tags="nomn,sing,masc",
                task_number=5,
            )
            db.session.add(sentence)
            db.session.commit()
            sentence_id = sentence.id

        cards_response = self.client.get(
            "/api/v1/practice/cards?task=5&limit=1"
        )
        assert cards_response.get_json()["cards"][0]["type"] == "paronym"

        response = self.client.post("/api/v1/attempts", json={
            "card_id": sentence_id,
            "card_type": "paronym",
            "answer": "эффективный",
        })

        assert response.status_code == 200
        assert response.get_json()["correct"]
        assert response.get_json()["anonymous_remaining"] == 2
        with self.app.app_context():
            action = Action.query.one()
            assert action.practice_item_id == sentence_id

    def test_duplicate_sentence_skip_is_not_recorded_twice(self) -> None:
        with self.app.app_context():
            group = ParonymGroup()
            correct = Paronym(word="адресат", group=group)
            Paronym(word="адресант", group=group)
            sentence = ParonymExercise(
                sentence="Письмо получил _______",
                paronym=correct,
                word_tags="nomn,sing,masc",
                task_number=5,
            )
            db.session.add(sentence)
            db.session.commit()
            sentence_id = sentence.id

        payload = {"card_id": sentence_id, "card_type": "paronym"}
        first = self.client.post("/api/v1/attempts/skip", json=payload)
        second = self.client.post("/api/v1/attempts/skip", json=payload)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.get_json()["anonymous_remaining"] == 2
        assert second.get_json()["anonymous_remaining"] == 2
        with self.app.app_context():
            action = Action.query.one()
            assert action.practice_item_id == sentence_id

    def test_attempt_rejects_invalid_payloads_and_unknown_words(self) -> None:
        cases = [
            ({}, "invalid_attempt", 400),
            ({"card_id": "1", "answer": "о", "card_type": "spelling"}, "invalid_attempt", 400),
            ({"card_id": 999, "answer": "о", "card_type": "spelling"}, "item_not_found", 404),
            ({"card_id": 1, "answer": "о"}, "invalid_card_type", 400),
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
            "/api/v1/attempts",
            json={"card_id": word_id, "answer": "о", "card_type": "spelling"},
        ).get_json()
        wrong = self.client.post(
            "/api/v1/attempts",
            json={"card_id": word_id, "answer": "и", "card_type": "spelling"},
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

    def test_strike_is_counted_when_its_display_is_disabled(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            user = db.session.get(User, user_id)
            user.settings.strike = False
            word_id = self.make_word().id
            db.session.commit()

        response = self.client.post(
            "/api/v1/attempts",
            json={"card_id": word_id, "answer": "о", "card_type": "spelling"},
        )

        assert response.status_code == 200
        assert response.get_json()["strike"]["n"] == 1

    def test_anonymous_quota_blocks_further_attempts_and_skips(self) -> None:
        with self.app.app_context():
            word_id = self.make_word().id

        for _ in range(3):
            response = self.client.post(
                "/api/v1/attempts",
                json={"card_id": word_id, "answer": "о", "card_type": "spelling"},
            )
            assert response.status_code == 200

        blocked = self.client.post(
            "/api/v1/attempts",
            json={"card_id": word_id, "answer": "о", "card_type": "spelling"},
            headers={"Referer": "/?task=4"},
        )
        assert blocked.status_code == 403
        assert blocked.get_json()["error"] == "anonymous_limit_reached"
        assert "/auth" in blocked.get_json()["login_url"]

        blocked_skip = self.client.post(
            "/api/v1/attempts/skip",
            json={"card_id": word_id, "card_type": "spelling"},
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
                "/api/v1/attempts",
                json={"card_id": word_id, "answer": "о", "card_type": "spelling"},
            )
            assert response.status_code == 200
            assert response.get_json()["anonymous_remaining"] is None

    def test_duplicate_skip_does_not_create_another_action(self) -> None:
        with self.app.app_context():
            word_id = self.make_word().id

        first = self.client.post(
            "/api/v1/attempts/skip",
            json={"card_id": word_id, "card_type": "spelling"},
        )
        second = self.client.post(
            "/api/v1/attempts/skip",
            json={"card_id": word_id, "card_type": "spelling"},
        )
        assert first.status_code == 200
        assert second.status_code == 200
        with self.app.app_context():
            assert Action.query.filter_by(action=Action.SKIP).count() == 1

    def test_skip_validates_card_id(self) -> None:
        bad_skip = self.client.post(
            "/api/v1/attempts/skip",
            json={"card_id": "1", "card_type": "spelling"},
        )
        unknown_skip = self.client.post(
            "/api/v1/attempts/skip",
            json={"card_id": 999, "card_type": "spelling"},
        )
        assert bad_skip.status_code == 400
        assert unknown_skip.status_code == 404

    def test_swipe_is_blocked_during_a_long_streak_for_a_new_word(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            db.session.get(User, user_id).yandex_id = "registered-for-swipe"
            target_id = self.make_word(word="ц_ль").id
            previous_ids = [
                self.make_word(word=f"сл_во{index}").id for index in range(4)
            ]
            db.session.add_all([
                Action(
                    user_id=user_id,
                    practice_item_id=word_id,
                    action=Action.RIGHT_ANSWER,
                )
                for word_id in previous_ids
            ])
            db.session.commit()
        with self.client.session_transaction() as browser_session:
            browser_session["strike"] = 4

        confirmation = self.client.post("/api/v1/attempts/skip", json={
            "card_id": target_id,
            "card_type": "spelling",
        })
        assert confirmation.status_code == 409
        assert confirmation.get_json()["status"] == "confirmation_required"
        allowed_recent = self.client.post("/api/v1/attempts/skip", json={
            "card_id": previous_ids[-1],
            "card_type": "spelling",
        })
        assert allowed_recent.status_code == 200
        confirmed = self.client.post("/api/v1/attempts/skip", json={
            "card_id": target_id,
            "card_type": "spelling",
            "confirmed": True,
        })
        assert confirmed.status_code == 200

    def test_swipe_confirmation_threshold_comes_from_config(self) -> None:
        with self.app.app_context():
            word_id = self.make_word(word="п_рог").id
        self.app.config["PRACTICE_SWIPE_GRACE_STRIKE"] = 0
        with self.client.session_transaction() as browser_session:
            browser_session["strike"] = 1

        response = self.client.post("/api/v1/attempts/skip", json={
            "card_id": word_id,
            "card_type": "spelling",
        })

        assert response.status_code == 409

    def test_card_selection_supports_task_category_and_mistakes(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            first = self.make_word(word="д_м", task_number=9, category_name="Корни")
            second = self.make_word(word="л_с", task_number=10, category_name="Лес")
            db.session.add_all([
                Action(user_id=user_id, practice_item_id=second.id, action=Action.WRONG_ANSWER),
                Action(user_id=user_id, practice_item_id=second.id, action=Action.WRONG_ANSWER),
                Action(user_id=user_id, practice_item_id=second.id, action=Action.RIGHT_ANSWER),
            ])
            db.session.commit()
            user = db.session.get(User, user_id)
            assert select_card(user, task_id="9").item.id == first.id
            assert (
                select_card(user, category_id=str(second.category_id)).item.id
                == second.id
            )
            assert select_card(user, mistakes=True).item.id == second.id

    def test_adaptive_selection_uses_each_learning_zone(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            comfortable = self.make_word(word="зн_комое")
            review = self.make_word(word="тр_дное")
            learning = self.make_word(word="уч_бное")
            new = self.make_word(word="н_вое")
            started = datetime(2025, 1, 1)
            actions = [
                Action(
                    user_id=user_id,
                    practice_item_id=comfortable.id,
                    action=Action.RIGHT_ANSWER,
                    datetime=started + timedelta(minutes=index),
                )
                for index in range(5)
            ]
            actions.extend([
                Action(
                    user_id=user_id,
                    practice_item_id=review.id,
                    action=Action.WRONG_ANSWER,
                    datetime=started + timedelta(minutes=5),
                ),
                Action(
                    user_id=user_id,
                    practice_item_id=learning.id,
                    action=Action.RIGHT_ANSWER,
                    datetime=started + timedelta(minutes=6),
                ),
            ])
            db.session.add_all(actions)
            db.session.commit()
            user = db.session.get(User, user_id)

            cards = select_cards(user, 4)

            assert [card.item.id for card in cards] == [
                comfortable.id,
                review.id,
                learning.id,
                new.id,
            ]
            assert [card.info[-1] for card in cards] == [
                "Знакомое задание для закрепления",
                "Повторение задания, которое вызвало затруднение",
                "Задание из вашей зоны обучения",
                "Новое задание",
            ]

    def test_two_failures_are_followed_by_a_comfortable_card(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            comfortable = self.make_word(word="л_гкое")
            difficult = self.make_word(word="сл_жное")
            started = datetime(2025, 1, 1)
            actions = [
                Action(
                    user_id=user_id,
                    practice_item_id=comfortable.id,
                    action=Action.RIGHT_ANSWER,
                    datetime=started + timedelta(minutes=index),
                )
                for index in range(5)
            ]
            actions.extend([
                Action(
                    user_id=user_id,
                    practice_item_id=difficult.id,
                    action=Action.WRONG_ANSWER,
                    datetime=started + timedelta(minutes=5),
                ),
                Action(
                    user_id=user_id,
                    practice_item_id=difficult.id,
                    action=Action.WRONG_ANSWER,
                    datetime=started + timedelta(minutes=6),
                ),
            ])
            db.session.add_all(actions)
            db.session.commit()
            user = db.session.get(User, user_id)

            card = select_card(user)

            assert card.item.id == comfortable.id
            assert card.info[-1] == "Знакомое задание после сложной серии"

    def test_recent_card_is_spaced_when_an_alternative_exists(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            older = self.make_word(word="р_нее")
            recent = self.make_word(word="н_давнее")
            started = datetime(2025, 1, 1)
            db.session.add_all([
                Action(
                    user_id=user_id,
                    practice_item_id=older.id,
                    action=Action.RIGHT_ANSWER,
                    datetime=started,
                ),
                Action(
                    user_id=user_id,
                    practice_item_id=recent.id,
                    action=Action.RIGHT_ANSWER,
                    datetime=started + timedelta(minutes=1),
                ),
            ])
            db.session.commit()
            user = db.session.get(User, user_id)

            assert select_card(user).item.id == older.id

    def test_card_selection_returns_clear_not_found_errors(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            user = db.session.get(User, user_id)
            with pytest.raises(PracticeError, match="Category not found"):
                select_card(user, category_id="999")
            with pytest.raises(
                PracticeError, match="No practice items available"
            ):
                select_card(user)

    def test_report_is_recorded_for_an_exercise_or_as_general_feedback(self) -> None:
        with self.app.app_context():
            word_id = self.make_word().id
            group = ParonymGroup()
            correct = Paronym(word="эффективный", group=group)
            Paronym(word="эффектный", group=group)
            paronym = ParonymExercise(
                sentence="Это _______ метод",
                paronym=correct,
                word_tags="nomn,sing,masc",
                task_number=5,
            )
            db.session.add(paronym)
            db.session.commit()
            paronym_id = paronym.id

        exercise = self.client.post(
            "/api/v1/reports",
            json={
                "practice_item_id": word_id,
                "message": "В упражнении неверный ответ",
            },
        )
        general = self.client.post(
            "/api/v1/reports",
            json={"practice_item_id": None, "message": "Не работает кнопка"},
        )
        paronym_report = self.client.post(
            "/api/v1/reports",
            json={
                "practice_item_id": paronym_id,
                "message": "Неверный пароним",
            },
        )

        assert exercise.status_code == 201
        assert general.status_code == 201
        assert paronym_report.status_code == 201
        with self.app.app_context():
            reports = ErrorReport.query.order_by(ErrorReport.id).all()
            assert reports[0].practice_item_id == word_id
            assert reports[0].message == "В упражнении неверный ответ"
            assert reports[1].practice_item_id is None
            assert reports[1].message == "Не работает кнопка"
            assert reports[2].practice_item_id == paronym_id

    @pytest.mark.parametrize(
        ("payload", "error", "status"),
        [
            (None, "invalid_json", 400),
            ({"message": 3}, "invalid_message", 400),
            ({"message": "   "}, "empty_message", 400),
            (
                {"message": "Ошибка", "practice_item_id": "1"},
                "invalid_practice_item_id",
                400,
            ),
            (
                {"message": "Ошибка", "practice_item_id": 999},
                "item_not_found",
                404,
            ),
        ],
    )
    def test_report_validation(self, payload, error: str, status: int) -> None:
        response = self.client.post("/api/v1/reports", json=payload)

        assert response.status_code == status
        assert response.get_json()["error"] == error
