import os
import unittest


os.environ["DEBUG"] = "false"

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Action, Category, User, Word  # noqa: E402


class RouteMapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        with self.app.app_context():
            db.create_all()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.drop_all()

    def test_canonical_routes_and_methods_are_registered(self) -> None:
        routes = {
            (rule.rule, method)
            for rule in self.app.url_map.iter_rules()
            for method in rule.methods - {"HEAD", "OPTIONS"}
        }
        expected = {
            ("/", "GET"),
            ("/filters", "GET"),
            ("/practice/cards/next", "GET"),
            ("/profile", "GET"),
            ("/auth", "GET"),
            ("/auth/logout", "POST"),
            ("/api/v1/attempts", "POST"),
            ("/api/v1/attempts/skip", "POST"),
            ("/api/v1/swipe-permission", "GET"),
            ("/api/v1/profile/settings", "PATCH"),
            ("/api/v1/profile/background", "GET"),
            ("/api/v1/words/<int:word_id>/reports", "POST"),
            ("/api/v1/admin/words/<int:word_id>/explanation", "PATCH"),
            ("/api/v1/admin/words/<int:word_id>/answers", "DELETE"),
        }
        self.assertTrue(expected <= routes)

    def test_filter_legacy_routes_redirect_to_canonical_query(self) -> None:
        cases = {
            "/task/5": "/?task=5",
            "/category/7": "/?category=7",
            "/mistakes": "/?mode=mistakes",
            "/settings": "/profile",
        }
        for old_url, canonical_url in cases.items():
            with self.subTest(old_url=old_url):
                response = self.client.get(old_url)
                self.assertEqual(response.status_code, 308)
                self.assertEqual(response.location, canonical_url)

    def test_index_uses_canonical_card_url(self) -> None:
        response = self.client.get("/?task=5")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'/practice/cards/next?task=5', response.data)
        self.assertNotIn(b'/get_frame', response.data)

    def test_settings_are_updated_through_patch_api(self) -> None:
        response = self.client.patch(
            "/api/v1/profile/settings", json={"strike": False}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "success"})
        with self.app.app_context():
            self.assertFalse(User.query.one().settings.strike)

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

        card_response = self.client.get("/practice/cards/next?task=4")
        self.assertEqual(card_response.status_code, 200)
        self.assertIn("м".encode(), card_response.data)

        attempt_response = self.client.post(
            "/api/v1/attempts",
            json={"word_id": word_id, "answer": "о"},
        )
        self.assertEqual(attempt_response.status_code, 200)
        self.assertTrue(attempt_response.get_json()["correct"])
        with self.app.app_context():
            self.assertEqual(Action.query.count(), 1)

    def test_legacy_attempt_adapter_preserves_request_body(self) -> None:
        with self.app.app_context():
            category = Category(name="Совместимость")
            word = Word(word="д_м", answers=["о", "а"], category=category)
            db.session.add(word)
            db.session.commit()
            word_id = word.id

        response = self.client.post(
            "/check_word", json={"id": word_id, "answer": "о"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["correct"])


if __name__ == "__main__":
    unittest.main()
