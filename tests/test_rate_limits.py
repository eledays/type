from tests.base import AppTestCase


class TestRateLimits(AppTestCase):
    def test_routes_expose_rate_limit_headers(self) -> None:
        response = self.client.get("/filters")

        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "300"
        assert int(response.headers["X-RateLimit-Remaining"]) < 300

    def test_sensitive_api_returns_stable_json_after_limit(self) -> None:
        responses = [
            self.client.post(
                "/api/v1/reports",
                json={"message": f"Сообщение {index}"},
            )
            for index in range(6)
        ]

        assert all(response.status_code == 201 for response in responses[:5])
        limited = responses[5]
        assert limited.status_code == 429
        assert limited.get_json() == {
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
        }
        assert int(limited.headers["Retry-After"]) > 0

    def test_registered_users_have_independent_limits(self) -> None:
        first = self.client
        second = self.app.test_client()
        first_user_id = self.current_user_id()
        second.get("/")
        with self.app.app_context():
            from app.extensions import db
            from app.models import User

            db.session.get(User, first_user_id).yandex_id = "first-user"
            second_user = User.query.order_by(User.id.desc()).first()
            second_user.yandex_id = "second-user"
            db.session.commit()

        for client in (first, second):
            for index in range(5):
                response = client.post(
                    "/api/v1/reports",
                    json={"message": f"Отдельный лимит {index}"},
                )
                assert response.status_code == 201

    def test_anonymous_client_cannot_spoof_forwarded_ip(self) -> None:
        headers = [
            {"X-Forwarded-For": "198.51.100.10"},
            {"X-Forwarded-For": "203.0.113.20"},
        ]
        responses = [
            self.client.post(
                "/api/v1/reports",
                json={"message": f"Попытка {index}"},
                headers=headers[index % 2],
            )
            for index in range(6)
        ]

        assert responses[-1].status_code == 429
