from tests.base import AppTestCase

from app.extensions import db
from app.models import Action, Category, User, Word


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
            word = Word(
                word="м_локо",
                answers=["о", "а"],
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
            json={"card_id": word_id, "answer": "о", "card_type": "word"},
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
            word = Word(word="р_ка", answers=["е", "и"], category=category)
            db.session.add(word)
            db.session.commit()
            word_id = word.id

        response = self.client.post(
            "/api/v1/attempts/skip",
            json={"card_id": word_id, "card_type": "word"},
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
