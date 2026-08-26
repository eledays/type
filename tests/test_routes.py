import re

from tests.base import AppTestCase

from app.extensions import db
from app.models import Action, Category, SpellingExercise, User


class TestRouteMap(AppTestCase):

    def test_canonical_routes_and_methods_are_registered(self) -> None:
        routes = {
            (rule.rule, method)
            for rule in self.app.url_map.iter_rules()
            for method in rule.methods - {"HEAD", "OPTIONS"}
        }
        expected = {
            ("/", "GET"),
            ("/profile", "GET"),
            ("/auth", "GET"),
            ("/auth/logout", "POST"),
            ("/api/v1/attempts", "POST"),
            ("/api/v1/attempts/skip", "POST"),
            ("/api/v1/practice/cards", "GET"),
            ("/api/v1/profile/settings", "PATCH"),
            ("/api/v1/profile/background", "GET"),
            ("/api/v1/profile/stats", "GET"),
            ("/api/v1/reports", "POST"),
            ("/api/v1/admin/words/<int:word_id>/explanation", "PATCH"),
            ("/api/v1/admin/words/<int:word_id>/answers", "DELETE"),
        }
        assert expected <= routes

    def test_filter_legacy_routes_redirect_to_canonical_query(self) -> None:
        cases = {
            "/task/5": "/?task=5",
            "/category/7": "/?category=7",
            "/mistakes": "/?mode=mistakes",
        }
        for old_url, canonical_url in cases.items():
            response = self.client.get(old_url)
            assert response.status_code == 308
            assert response.location == canonical_url

    def test_obsolete_standalone_pages_are_removed(self) -> None:
        for url in ("/filters", "/settings"):
            response = self.client.get(url)
            assert response.status_code == 404

    def test_index_uses_batch_feed_without_iframes(self) -> None:
        response = self.client.get("/?task=5")
        assert response.status_code == 200
        assert b'/api/v1/practice/cards' in response.data
        assert b'<iframe' not in response.data
        assert b'/get_frame' not in response.data
        assert b'js/feed.min.js' in response.data
        assert b'fonts.googleapis.com' not in response.data
        assert b'<symbol id="icon-search"' in response.data
        assert b'"swipeGraceStrike": 3' in response.data
        assert b'/api/v1/profile/avatar' not in response.data
        assert b'/static/img/default_avatar.png?v=' in response.data

    def test_index_contains_inline_profile_filters_and_word_panels(self) -> None:
        response = self.client.get("/")

        assert response.status_code == 200
        assert b'id="profile-panel"' in response.data
        assert b'id="filters-panel"' in response.data
        assert b'id="word-panel"' in response.data
        assert b'id="report-panel"' in response.data
        assert b'data-open-panel="profile"' in response.data
        assert b'data-open-panel="filters"' in response.data
        assert b'data-open-panel="word"' in response.data
        assert b'data-open-report="exercise"' in response.data
        assert b'data-open-report="general"' in response.data
        assert b'data-state="accent"' in response.data

    def test_header_hides_strike_until_first_answer_after_page_load(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            user = db.session.get(User, user_id)
            user.yandex_id = "registered-user"
            db.session.commit()
        with self.client.session_transaction() as browser_session:
            browser_session["strike"] = 6

        response = self.client.get("/")

        assert b'class="header has-info"' not in response.data
        assert b'aria-live="polite" hidden' in response.data
        assert b'id="strike-value">6<' in response.data

    def test_strike_setting_only_hides_its_header_block(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            user = db.session.get(User, user_id)
            user.yandex_id = "registered-user"
            user.settings.strike = False
            db.session.commit()
        with self.client.session_transaction() as browser_session:
            browser_session["strike"] = 6

        response = self.client.get("/")

        assert b'class="header has-info"' not in response.data
        assert b'id="strike-value">6<' in response.data

    def test_profile_panel_has_strike_setting_for_registered_user(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            user = db.session.get(User, user_id)
            user.yandex_id = "registered-user"
            db.session.commit()

        response = self.client.get("/")

        assert b'data-strike-toggle' in response.data
        assert b'"updateSettings"' in response.data

    def test_profile_stats_are_loaded_from_panel_api(self) -> None:
        response = self.client.get("/")

        assert b'"profileStats": "/api/v1/profile/stats"' in response.data
        assert b'id="profile-correct">\xe2\x80\x94<' in response.data

        stats = self.client.get("/api/v1/profile/stats")
        assert stats.status_code == 200
        assert stats.get_json()["correct"] == 0

    def test_profile_page_has_general_error_report_form(self) -> None:
        response = self.client.get("/profile")

        assert response.status_code == 200
        assert b'id="general-report-form"' in response.data
        assert b'/api/v1/reports' in response.data

    def test_anonymous_header_shows_login_then_progress_prompt(self) -> None:
        initial = self.client.get("/")

        assert b'class="header-login"' in initial.data
        assert re.search(
            rb'<a class="info-block"[^>]*data-state="accent"[^>]* hidden>',
            initial.data,
        )
        assert "Серия".encode() not in initial.data

        user_id = self.current_user_id()
        with self.app.app_context():
            word = self.make_word()
            db.session.add(Action(
                user_id=user_id,
                practice_item_id=word.id,
                action=Action.RIGHT_ANSWER,
            ))
            db.session.commit()

        resumed = self.client.get("/")

        assert b"has-anonymous-info" in resumed.data
        assert "Войдите, чтобы сохранить прогресс".encode() in resumed.data

    def test_index_exposes_distinct_background_urls_for_cards(self) -> None:
        response = self.client.get("/")
        background_urls = set(re.findall(
            rb'/static/img/backs/dark/[^"?]+\.webp\?v=\d+',
            response.data,
        ))

        assert len(background_urls) > 1
        assert b'backgroundPools' in response.data
        assert b'/api/v1/profile/background' not in response.data

    def test_settings_are_updated_through_patch_api(self) -> None:
        response = self.client.patch(
            "/api/v1/profile/settings", json={"strike": False}
        )
        assert response.status_code == 200
        assert response.get_json() == {"status": "success"}
        with self.app.app_context():
            assert not User.query.one().settings.strike

    def test_practice_card_and_attempt_flow(self) -> None:
        with self.app.app_context():
            category = Category(name="Проверка")
            word = SpellingExercise(
                word="м_локо",
                answers=["о", "а"],
                correct_answer="о",
                task_number=4,
                category=category,
            )
            db.session.add(word)
            db.session.commit()
            word_id = word.id

        card_response = self.client.get("/api/v1/practice/cards?limit=3&task=4")
        assert card_response.status_code == 200
        assert card_response.get_json()["cards"][0]["prompt"] == "м_локо"

        attempt_response = self.client.post(
            "/api/v1/attempts",
            json={"card_id": word_id, "answer": "о", "card_type": "spelling"},
        )
        assert attempt_response.status_code == 200
        attempt = attempt_response.get_json()
        assert attempt["correct"]
        assert (
            attempt["anonymous_remaining"]
            == self.app.config["ANONYMOUS_ACTION_LIMIT"] - 1
        )
        with self.app.app_context():
            assert Action.query.count() == 1

    def test_skip_returns_updated_anonymous_limit(self) -> None:
        with self.app.app_context():
            category = Category(name="Пропуск")
            word = SpellingExercise(
                word="р_ка",
                answers=["е", "и"],
                correct_answer="е",
                category=category,
            )
            db.session.add(word)
            db.session.commit()
            word_id = word.id

        response = self.client.post(
            "/api/v1/attempts/skip",
            json={"card_id": word_id, "card_type": "spelling"},
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["status"] == "success"
        assert (
            payload["anonymous_remaining"]
            == self.app.config["ANONYMOUS_ACTION_LIMIT"] - 1
        )

    def test_optimized_backgrounds_are_immutable(self) -> None:
        response = self.client.get("/static/img/backs/dark/0.webp?v=test")
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == (
            "public, max-age=31536000, immutable"
        )
