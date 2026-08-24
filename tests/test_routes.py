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
            ("/filters", "GET"),
            ("/profile", "GET"),
            ("/auth", "GET"),
            ("/auth/logout", "POST"),
            ("/api/v1/attempts", "POST"),
            ("/api/v1/attempts/skip", "POST"),
            ("/api/v1/practice/cards", "GET"),
            ("/api/v1/profile/settings", "PATCH"),
            ("/api/v1/profile/background", "GET"),
            ("/api/v1/words/<int:word_id>/reports", "POST"),
            ("/api/v1/admin/words/<int:word_id>/explanation", "PATCH"),
            ("/api/v1/admin/words/<int:word_id>/answers", "DELETE"),
        }
        assert expected <= routes

    def test_filter_legacy_routes_redirect_to_canonical_query(self) -> None:
        cases = {
            "/task/5": "/?task=5",
            "/category/7": "/?category=7",
            "/mistakes": "/?mode=mistakes",
            "/settings": "/profile",
        }
        for old_url, canonical_url in cases.items():
            response = self.client.get(old_url)
            assert response.status_code == 308
            assert response.location == canonical_url

    def test_index_uses_batch_feed_without_iframes(self) -> None:
        response = self.client.get("/?task=5")
        assert response.status_code == 200
        assert b'/api/v1/practice/cards' in response.data
        assert b'<iframe' not in response.data
        assert b'/get_frame' not in response.data

    def test_index_contains_inline_profile_filters_and_word_panels(self) -> None:
        response = self.client.get("/")

        assert response.status_code == 200
        assert b'id="profile-panel"' in response.data
        assert b'id="filters-panel"' in response.data
        assert b'id="word-panel"' in response.data
        assert b'data-open-panel="profile"' in response.data
        assert b'data-open-panel="filters"' in response.data
        assert b'data-open-panel="word"' in response.data
        assert b'class="info-block" aria-live="polite" hidden' in response.data

    def test_header_compacts_actions_only_for_strikes_above_five(self) -> None:
        self.client.get("/")
        with self.client.session_transaction() as browser_session:
            browser_session["strike"] = 6

        response = self.client.get("/")

        assert b'class="header has-info"' in response.data
        assert b'class="info-block" aria-live="polite" hidden' not in response.data
        assert b'id="strike-value">6<' in response.data

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
